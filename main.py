import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import TELEGRAM_BOT_TOKEN
import handlers.telegram as handlers
from telegram.ext import CallbackQueryHandler

# Configuração de logs para facilitar o debug
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():

    # Inicializa a aplicação do bot
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Registra os manipuladores (Handlers)
    app.add_handler(CommandHandler("start", handlers.start_command))
    
    # Filtra mensagens que contêm fotos
    app.add_handler(MessageHandler(filters.PHOTO, handlers.handle_photo))
    
    # Filtra mensagens de texto comuns (ignorando comandos)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text))

    # Registra o manipulador para os botões flutuantes
    app.add_handler(CallbackQueryHandler(handlers.lidar_com_botoes))


    print("Bot rodando! Pressione Ctrl+C para parar.")
    
    # Mantém o bot escutando por novas mensagens
    app.run_polling()

if __name__ == '__main__':
    main()