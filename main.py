import logging
from threading import Thread
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import TELEGRAM_BOT_TOKEN, SHORTCUT_API_HOST, SHORTCUT_API_PORT
import handlers.telegram as handlers
from telegram.ext import CallbackQueryHandler
import shortcut_api

# Configuração de logs para facilitar o debug
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

def main():

    api = shortcut_api.iniciar(SHORTCUT_API_HOST, SHORTCUT_API_PORT)
    Thread(target=api.serve_forever, daemon=True).start()
    logging.info("API do Atalho ouvindo em %s:%s", SHORTCUT_API_HOST, SHORTCUT_API_PORT)

    # Inicializa a aplicação do bot
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # Registra os manipuladores (Handlers)
    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CommandHandler("despensa", handlers.listar_despensa))
    app.add_handler(CommandHandler("atalho", handlers.atalho_command))
    app.job_queue.run_repeating(handlers.verificar_lembretes, interval=3600, first=60)
    
    # Filtra mensagens que contêm fotos
    app.add_handler(MessageHandler(filters.PHOTO, handlers.handle_photo))
    
    # Filtra mensagens de texto comuns (ignorando comandos)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text))

    # Registra o manipulador para os botões flutuantes
    app.add_handler(CallbackQueryHandler(handlers.lidar_com_botoes))


    print("Bot rodando! Pressione Ctrl+C para parar.")
    
    # Mantém o bot escutando por novas mensagens
    try:
        app.run_polling()
    finally:
        api.shutdown()
        api.server_close()

if __name__ == '__main__':
    main()
