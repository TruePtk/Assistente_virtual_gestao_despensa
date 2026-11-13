import os
from urllib.parse import urlsplit
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv(".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
IOS_SHORTCUT_INSTALL_URL = os.getenv("IOS_SHORTCUT_INSTALL_URL", "").strip()
IOS_SHORTCUT_NAME = os.getenv("IOS_SHORTCUT_NAME", "Despensa").strip() or "Despensa"
# O launcher do Quick Tunnel injeta essa URL no ambiente antes de iniciar o Python.
SHORTCUT_API_BASE_URL = os.getenv("SHORTCUT_API_BASE_URL", "").rstrip("/")
SHORTCUT_API_HOST = os.getenv("SHORTCUT_API_HOST", "127.0.0.1")
SHORTCUT_API_PORT = int(os.getenv("SHORTCUT_API_PORT", "8765"))

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN não encontrado. Verifique seu arquivo .env.")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY não encontrada. Verifique seu arquivo .env.")

if SHORTCUT_API_BASE_URL:
    api_url = urlsplit(SHORTCUT_API_BASE_URL)
    if (api_url.scheme != "https" or not api_url.hostname or api_url.username
            or api_url.password or api_url.path or api_url.query or api_url.fragment):
        raise ValueError("SHORTCUT_API_BASE_URL deve conter apenas a origem HTTPS pública da API.")
