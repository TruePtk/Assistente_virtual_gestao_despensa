"""Adaptador dos comandos para o Telegram."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from handlers import core

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = (
        "Olá! Sou seu assistente de despensa inteligente. 🥫\n\n"
        "Envie a foto de uma nota fiscal de supermercado para eu cadastrar seus itens, "
        "ou me pergunte o que podemos cozinhar com o que tem guardado."
    )
    await update.message.reply_text(mensagem)


async def listar_despensa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    itens = core.obter_itens_despensa(user_id)
    botoes = []
    texto = "🥫 *Sua Despensa:*\n\n"

    for item_id, nome, qtd, unid in itens:
        texto += f"• {qtd} {unid} de {nome}\n"
        botoes.append([InlineKeyboardButton(f"❌ Consumi: {nome}", callback_data=f"remover_{item_id}")])

    await update.message.reply_text(
        texto,
        reply_markup=InlineKeyboardMarkup(botoes),
        parse_mode="Markdown",
    )


async def lidar_com_botoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dados = query.data
    user_id = query.from_user.id

    if dados.startswith("remover_"):
        item_id = dados.split("_", 1)[1]
        item = core.selecionar_item(user_id, item_id)
        if not item:
            await query.edit_message_text("❌ Item não encontrado.")
            return

        _, nome, qtd, unid = item
        botoes = [
            [
                InlineKeyboardButton("-1", callback_data=f"baixar_{item_id}_1"),
                InlineKeyboardButton("-0.5", callback_data=f"baixar_{item_id}_0.5"),
            ],
            [InlineKeyboardButton("Acabou Tudo!", callback_data=f"baixar_{item_id}_TUDO")],
            [InlineKeyboardButton("🔙 Cancelar", callback_data="cancelar_baixa")],
        ]
        texto = f"🥫 **Consumindo: {nome}**\nEstoque atual: {qtd} {unid}\n\nQuanto você utilizou?"
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botoes), parse_mode="Markdown")
    elif dados.startswith("baixar_"):
        _, item_id, quantidade = dados.split("_", 2)
        resposta = core.consumir_item(int(item_id), user_id, quantidade)
        await query.edit_message_text(f"✅ {resposta}")
    elif dados == "cancelar_baixa":
        await query.edit_message_text("Operação cancelada. Digite /despensa para ver a lista novamente.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_nome = update.message.from_user.first_name
    mensagem_espera = await update.message.reply_text("Entendi! Deixe-me analisar sua mensagem... 🤖")
    resultado = core.interpretar_mensagem(update.message.text, user_id, user_nome)

    if resultado["acao"] == "consultar":
        await mensagem_espera.delete()
        await listar_despensa(update, context)
    else:
        await mensagem_espera.edit_text(resultado["resposta"])


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem_espera = await update.message.reply_text("Recebi a nota! 🔍 Lendo os itens...")
    foto = update.message.photo[-1]
    arquivo_foto = await context.bot.get_file(foto.file_id)
    foto_bytes = await arquivo_foto.download_as_bytearray()
    user = update.message.from_user
    resultado = core.processar_nota(foto_bytes, user.id, user.first_name)

    if "erro" in resultado:
        print(f"\n[ERRO NA IA]: {resultado['erro']}\n")
        await mensagem_espera.edit_text("Putz, não consegui ler essa nota com clareza. Pode mandar outra foto?")
        return

    texto = "✅ *Itens adicionados à sua despensa:*\n\n"
    for item in resultado.get("itens", []):
        texto += f"• {item['quantidade']} {item['unidade_medida']} de {item['nome']} ({item['categoria']})\n"
    if resultado.get("avisos"):
        texto += "\n⚠️ " + "\n⚠️ ".join(resultado["avisos"])
    await mensagem_espera.edit_text(texto, parse_mode="Markdown")
