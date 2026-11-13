"""API HTTP enxuta para vinculação e uso do Atalho do iOS."""

import hashlib
import json
import logging
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

from config import IOS_SHORTCUT_NAME, SHORTCUT_API_BASE_URL
import database.database as database
from handlers import core

logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 16_384


def _hash(valor: str) -> str:
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


class ShortcutRequestHandler(BaseHTTPRequestHandler):
    server_version = "DespensaShortcutAPI/1.0"

    def log_message(self, format, *args):
        logger.info("Shortcut API: %s %s", self.command, urlparse(self.path).path)

    def _json(self, status: int, dados: dict):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _body(self):
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if not 0 < tamanho <= MAX_BODY_BYTES:
            return None
        try:
            dados = json.loads(self.rfile.read(tamanho))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return dados if isinstance(dados, dict) else None

    def _telegram_id(self):
        cabecalho = self.headers.get("Authorization", "")
        esquema, _, token = cabecalho.partition(" ")
        if esquema.lower() != "bearer" or not token or len(token) > 256:
            return None
        return database.usuario_por_token_atalho(_hash(token))

    def do_GET(self):
        requisicao = urlparse(self.path)
        caminho = requisicao.path
        if caminho == "/health":
            self._json(200, {"status": "ok"})
            return
        if caminho == "/api/shortcut/open":
            entrada_texto = parse_qs(requisicao.query).get("text", [""])[0]
            try:
                entrada = json.loads(entrada_texto)
            except (json.JSONDecodeError, TypeError):
                entrada = None
            if (not isinstance(entrada, dict)
                    or isinstance(entrada.get("telegram_id"), bool)
                    or not isinstance(entrada.get("telegram_id"), int)
                    or not isinstance(entrada.get("pairing_code"), str)
                    or not entrada["pairing_code"]
                    or entrada.get("api_url") != SHORTCUT_API_BASE_URL
                    or len(entrada_texto) > 8192):
                self._json(400, {"error": "invalid_shortcut_input"})
                return
            atalho_url = "shortcuts://run-shortcut?" + urlencode({
                "name": IOS_SHORTCUT_NAME,
                "input": "text",
                "text": entrada_texto,
            })
            self.send_response(302)
            self.send_header("Location", atalho_url)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if caminho != "/api/shortcut/pantry":
            self._json(404, {"error": "not_found"})
            return
        telegram_id = self._telegram_id()
        if telegram_id is None:
            self._json(401, {"error": "unauthorized"})
            return
        itens = core.obter_itens_despensa(telegram_id)
        self._json(200, {"items": [
            {"id": item_id, "name": nome, "quantity": quantidade, "unit": unidade}
            for item_id, nome, quantidade, unidade in itens
        ]})

    def do_POST(self):
        caminho = urlparse(self.path).path
        dados = self._body()
        if dados is None:
            self._json(400, {"error": "invalid_json"})
            return

        if caminho == "/api/shortcut/link":
            telegram_id = dados.get("telegram_id")
            codigo = dados.get("pairing_code")
            id_valido = (
                isinstance(telegram_id, int) and not isinstance(telegram_id, bool)
            )
            if isinstance(telegram_id, str):
                telegram_id = telegram_id.strip()
            if (isinstance(telegram_id, str) and 0 < len(telegram_id) <= 19
                    and telegram_id.isascii() and telegram_id.isdecimal()):
                telegram_id = int(telegram_id)
                id_valido = True
            codigo = codigo.strip() if isinstance(codigo, str) else ""
            campos_invalidos = []
            if not id_valido or not 0 < telegram_id <= 9_223_372_036_854_775_807:
                campos_invalidos.append("telegram_id")
            if not codigo or len(codigo) > 128:
                campos_invalidos.append("pairing_code")
            if campos_invalidos:
                self._json(400, {
                    "error": "invalid_pairing_data",
                    "invalid_fields": campos_invalidos,
                })
                return
            token = secrets.token_urlsafe(32)
            if not database.trocar_codigo_atalho_por_token(
                _hash(codigo), telegram_id, _hash(token)
            ):
                self._json(401, {"error": "pairing_code_invalid_or_expired"})
                return
            self._json(200, {"access_token": token, "token_type": "Bearer"})
            return

        if caminho != "/api/shortcut/message":
            self._json(404, {"error": "not_found"})
            return
        telegram_id = self._telegram_id()
        if telegram_id is None:
            self._json(401, {"error": "unauthorized"})
            return
        mensagem = dados.get("message")
        if not isinstance(mensagem, str) or not mensagem.strip() or len(mensagem) > 2000:
            self._json(400, {"error": "invalid_message"})
            return
        try:
            resultado = core.interpretar_mensagem(mensagem.strip(), telegram_id)
        except Exception:
            logger.exception("Falha ao processar solicitação do Atalho")
            self._json(502, {"error": "request_failed"})
            return

        resposta = {"action": resultado.get("acao"), "reply": resultado.get("resposta", "")}
        if resultado.get("acao") == "consultar":
            resposta["items"] = [
                {"id": item_id, "name": nome, "quantity": quantidade, "unit": unidade}
                for item_id, nome, quantidade, unidade in resultado.get("itens", [])
            ]
        self._json(200, resposta)

    def do_DELETE(self):
        if urlparse(self.path).path != "/api/shortcut/token":
            self._json(404, {"error": "not_found"})
            return
        cabecalho = self.headers.get("Authorization", "")
        esquema, _, token = cabecalho.partition(" ")
        if esquema.lower() != "bearer" or not token or len(token) > 256:
            self._json(401, {"error": "unauthorized"})
            return
        if not database.revogar_token_atalho(_hash(token)):
            self._json(401, {"error": "unauthorized"})
            return
        self._json(200, {"status": "revoked"})


def iniciar(host: str, porta: int) -> ThreadingHTTPServer:
    servidor = ThreadingHTTPServer((host, porta), ShortcutRequestHandler)
    servidor.daemon_threads = True
    return servidor
