from telegram import Update
from telegram.ext import ContextTypes
import ai_config.ai_service as ai_service

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde ao comando /start"""
    mensagem = (
        "Olá! Sou seu assistente de despensa inteligente. 🥫\n\n"
        "Envie a foto de uma nota fiscal de supermercado para eu cadastrar seus itens, "
        "ou me pergunte o que podemos cozinhar com o que tem guardado."
    )
    await update.message.reply_text(mensagem)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captura mensagens de texto comuns (Dúvidas, receitas, consumo)"""
    texto_usuario = update.message.text
    
    # Placeholder: Aqui entrará a chamada para a IA entender a intenção do usuário
    # (ex: dar baixa em itens, pedir receita, etc).
    resposta = f"Você disse: '{texto_usuario}'. Em breve, a IA processará isso!"
    
    await update.message.reply_text(resposta)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captura a Nota Fiscal e manda para o Gemini"""
    mensagem_espera = await update.message.reply_text("Recebi a nota! 🔍 Lendo os itens...")
    
    foto = update.message.photo[-1]
    arquivo_foto = await context.bot.get_file(foto.file_id)
    foto_bytes = await arquivo_foto.download_as_bytearray()
    
    # Chama o cérebro
    resultado = ai_service.processar_nota_fiscal(foto_bytes)
    
    if "erro" in resultado:
        # Imprime o erro técnico no terminal para nos ajudar a debugar
        print(f"\n[ERRO NA IA]: {resultado['erro']}\n") 
        
        await mensagem_espera.edit_text("Putz, não consegui ler essa nota com clareza. Pode mandar outra foto?")
        return

    # Formata a resposta para ficar bonita no Telegram
    texto_resposta = "✅ *Itens adicionados à sua despensa:*\n\n"
    for item in resultado.get("itens", []):
        texto_resposta += f"• {item['quantidade']} {item['unidade_medida']} de {item['nome']} ({item['categoria']})\n"
        
    await mensagem_espera.edit_text(texto_resposta, parse_mode='Markdown')