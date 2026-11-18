"""API HTTP enxuta para vinculação e uso do Atalho do iOS."""

import hashlib
import json
import logging
import math
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from config import IOS_SHORTCUT_NAME, SHORTCUT_API_BASE_URL, SHORTCUT_API_PORT
import database.database as database
from handlers import core
from site_web import tokens as site_tokens

logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 16_384
SITE_HTML = Path(__file__).parent / "site_web" / "index.html"


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

    def _usuario_site(self):
        token = self.headers.get("X-Token", "")
        if not token or len(token) > 256:
            return None
        return site_tokens.usuario_do_token(token)

    def _erro_site_nao_autorizado(self):
        self._json(401, {"detail": "Link inválido. Peça um novo com /site no bot."})

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
        if caminho == "/":
            try:
                corpo = SITE_HTML.read_bytes()
            except OSError:
                logger.exception("Não foi possível carregar a página do site")
                self._json(500, {"detail": "Não foi possível carregar o site."})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)
            return
        if caminho == "/api/despensa":
            telegram_id = self._usuario_site()
            if telegram_id is None:
                self._erro_site_nao_autorizado()
                return
            self._json(200, [
                {"id": item_id, "nome": nome, "quantidade": quantidade, "unidade": unidade}
                for item_id, nome, quantidade, unidade in core.obter_itens_despensa(telegram_id)
            ])
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
            {"id": item_id, "name": nome, "quantity": round(quantidade, 3), "unit": unidade}
            for item_id, nome, quantidade, unidade in itens
        ]})

    def do_POST(self):
        caminho = urlparse(self.path).path
        dados = self._body()
        if dados is None:
            self._json(400, {"error": "invalid_json"})
            return

        if caminho in ("/api/adicionar", "/api/consumir"):
            telegram_id = self._usuario_site()
            if telegram_id is None:
                self._erro_site_nao_autorizado()
                return

            if caminho == "/api/consumir":
                item_id = dados.get("item_id")
                quantidade = dados.get("quantidade")
                if (isinstance(item_id, bool) or not isinstance(item_id, int) or item_id <= 0
                        or not isinstance(quantidade, str) or not 0 < len(quantidade) <= 20):
                    self._json(422, {"detail": "Dados de consumo inválidos."})
                    return
                quantidade = quantidade.strip()
                if quantidade.upper() != "TUDO":
                    try:
                        valor = float(quantidade)
                    except ValueError:
                        self._json(422, {"detail": "Quantidade inválida."})
                        return
                    if not math.isfinite(valor) or valor <= 0:
                        self._json(422, {"detail": "A quantidade deve ser maior que zero."})
                        return
                    quantidade = str(valor)
                self._json(200, {"mensagem": core.consumir_item(item_id, telegram_id, quantidade)})
                return

            nome = dados.get("nome")
            quantidade = dados.get("quantidade")
            unidade = dados.get("unidade", "unidade")
            categoria = dados.get("categoria", "Outros")
            if isinstance(quantidade, bool):
                quantidade = None
            try:
                quantidade = float(quantidade)
            except (TypeError, ValueError, OverflowError):
                quantidade = float("nan")
            if (not isinstance(nome, str) or not isinstance(unidade, str)
                    or not isinstance(categoria, str) or not nome.strip()
                    or len(nome) > 100 or not 0 < len(unidade.strip()) <= 20
                    or unidade not in ("unidade", "kg", "L")
                    or not 0 < len(categoria.strip()) <= 40
                    or not math.isfinite(quantidade) or quantidade <= 0):
                self._json(422, {"detail": "Preencha os dados do item corretamente."})
                return
            nome_adicionado, erro = core._adicionar_item(telegram_id, {
                "item_alvo": nome.strip(),
                "quantidade": quantidade,
                "unidade_medida": unidade,
                "categoria": categoria.strip(),
            })
            if erro:
                self._json(400, {"detail": erro})
                return
            self._json(200, {"mensagem": f"Adicionado: {nome_adicionado}"})
            return

        if caminho == "/api/shortcut/site":
            telegram_id = self._telegram_id()
            if telegram_id is None:
                self._json(401, {"error": "unauthorized"})
                return
            token = site_tokens.criar_token(telegram_id)
            base_url = SHORTCUT_API_BASE_URL or f"http://localhost:{SHORTCUT_API_PORT}"
            self._json(200, {"site_url": f"{base_url}/#t={token}"})
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
                {"id": item_id, "name": nome, "quantity": round(quantidade, 3), "unit": unidade}
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
