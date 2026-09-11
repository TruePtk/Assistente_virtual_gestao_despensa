import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv(".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN não encontrado. Verifique seu arquivo .env.")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY não encontrada. Verifique seu arquivo .env.")