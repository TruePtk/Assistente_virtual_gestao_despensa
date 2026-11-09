"""Leitura do QR Code e consulta pública de NFC-e."""

from html.parser import HTMLParser
from io import BytesIO
import re
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image, UnidentifiedImageError
import zxingcpp


TIMEOUT = (4, 12)
MAX_RESPONSE_BYTES = 5_000_000
MAX_REDIRECTS = 5
HEADERS = {"User-Agent": "AssistenteDespensa/1.0 (consulta de NFC-e)"}


def _validar_url_oficial(url: str) -> str | None:
    url = url.strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    try:
        porta = parsed.port
    except ValueError:
        return None
    if (parsed.scheme not in {"http", "https"}
            or not (host == "gov.br" or host.endswith(".gov.br"))
            or parsed.username or parsed.password
            or porta not in {None, 80, 443}):
        return None
    return url


def _validar_url_nfce(url: str) -> str | None:
    url = _validar_url_oficial(url)
    if not url:
        return None
    # NFC-e versions 2/3 commonly carry the 44-digit key inside `p`; newer
    # layouts may expose it as a named query parameter.
    if not re.search(r"(?<!\d)\d{44}(?!\d)", url):
        return None
    return url


def decodificar_qrcode_nfce(imagem_bytes: bytes) -> str | None:
    """Retorna a URL de consulta se a imagem contiver QR de NFC-e reconhecível."""
    try:
        with Image.open(BytesIO(imagem_bytes)) as imagem:
            imagem.load()
            codigos = zxingcpp.read_barcodes(
                imagem.convert("RGB"), formats=zxingcpp.BarcodeFormat.QRCode
            )
    except (UnidentifiedImageError, OSError, ValueError):
        return None

    for codigo in codigos:
        url = _validar_url_nfce(codigo.text)
        if url:
            return url
    return None


class _TextoVisivelHTML(HTMLParser):
    """Extrai texto da página sem scripts, estilos ou conteúdo executável."""

    _IGNORAR = {"head", "script", "style", "noscript", "svg"}
    _QUEBRA = {"br", "div", "li", "p", "td", "th", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._ignorar = 0
        self.partes = []

    def handle_starttag(self, tag, attrs):
        if tag in self._IGNORAR:
            self._ignorar += 1
        elif not self._ignorar and tag in self._QUEBRA:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in self._IGNORAR and self._ignorar:
            self._ignorar -= 1
        elif not self._ignorar and tag in self._QUEBRA:
            self.partes.append("\n")

    def handle_data(self, data):
        if not self._ignorar:
            self.partes.append(data)


def _obter_url_segura(url: str) -> str:
    """Baixa somente consultas em domínios oficiais e valida cada redirecionamento."""
    atual = _validar_url_nfce(url)
    if not atual:
        raise ValueError("O QR Code não contém uma URL oficial de consulta NFC-e válida.")

    for _ in range(MAX_REDIRECTS + 1):
        resposta = requests.get(
            atual, headers=HEADERS, timeout=TIMEOUT, allow_redirects=False, stream=True
        )
        if resposta.is_redirect:
            destino = resposta.headers.get("Location")
            resposta.close()
            if not destino:
                raise ValueError("A SEFAZ retornou um redirecionamento sem destino.")
            atual = _validar_url_oficial(urljoin(atual, destino))
            if not atual:
                raise ValueError("A consulta tentou redirecionar para um endereço não oficial.")
            continue

        resposta.raise_for_status()
        if int(resposta.headers.get("Content-Length", 0) or 0) > MAX_RESPONSE_BYTES:
            resposta.close()
            raise ValueError("A página da SEFAZ excede o tamanho máximo aceito.")

        conteudo = bytearray()
        for bloco in resposta.iter_content(65536):
            conteudo.extend(bloco)
            if len(conteudo) > MAX_RESPONSE_BYTES:
                resposta.close()
                raise ValueError("A página da SEFAZ excede o tamanho máximo aceito.")
        encoding = resposta.encoding or "utf-8"
        resposta.close()
        html = bytes(conteudo).decode(encoding, errors="replace")

        parser = _TextoVisivelHTML()
        parser.feed(html)
        texto = re.sub(r"[ \t\r]+", " ", "".join(parser.partes))
        texto = re.sub(r"\n\s*\n+", "\n", texto).strip()
        if not texto:
            raise ValueError("A consulta da SEFAZ não trouxe texto legível para extrair os itens.")
        return texto[:50_000]

    raise ValueError("A consulta da SEFAZ excedeu o limite de redirecionamentos.")


def obter_texto_consulta(imagem_bytes: bytes) -> str | None:
    """Retorna texto da consulta SEFAZ ou None quando a imagem não é QR de NFC-e."""
    url = decodificar_qrcode_nfce(imagem_bytes)
    if not url:
        return None
    return _obter_url_segura(url)
