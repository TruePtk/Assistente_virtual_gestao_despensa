"""Adaptador dos comandos para o Telegram."""

import asyncio
import json
from collections import defaultdict
from urllib.parse import urlencode

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from handlers import core
from config import IOS_SHORTCUT_INSTALL_URL, SHORTCUT_API_BASE_URL
from site_web import tokens

URL_SITE = "http://localhost:8000"

_locks_por_usuario = defaultdict(asyncio.Lock)


def _obter_lock_usuario(user_id: int) -> asyncio.Lock:
    return _locks_por_usuario[user_id]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = (
        "Olá! Sou seu assistente de despensa inteligente. 🥫\n\n"
        "Envie a foto de uma nota fiscal de supermercado para eu cadastrar seus itens, "
        "ou me pergunte o que podemos cozinhar com o que tem guardado."
    )
    await update.message.reply_text(mensagem)


async def atalho_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia o link de instalação e um link para vincular o ID do Telegram."""
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text("Use este comando em uma conversa privada com o bot.")
        return
    if not IOS_SHORTCUT_INSTALL_URL or not SHORTCUT_API_BASE_URL:
        await update.message.reply_text(
            "A instalação ou a API do Atalho para iPhone ainda não foi configurada."
        )
        return

    user_id = update.effective_user.id
    botoes = [
        [InlineKeyboardButton("Instalar Atalho", url=IOS_SHORTCUT_INSTALL_URL)],
        [InlineKeyboardButton("Autenticar neste iPhone", url=_url_autenticacao_atalho(user_id))],
    ]
    await update.effective_message.reply_text(
        "Para configurar o Atalho no iPhone:\n"
        "1. Instale pelo botão abaixo.\n"
        "2. Toque em *Autenticar neste iPhone* e abra o link enviado. O Atalho usará o "
        "código temporário para vincular sua conta e salvar o token de acesso para as próximas solicitações.",
        reply_markup=InlineKeyboardMarkup(botoes),
        parse_mode="Markdown",
    )


def _url_autenticacao_atalho(user_id: int) -> str:
    codigo = core.gerar_codigo_vinculacao_atalho(user_id)
    entrada = json.dumps({
        "api_url": SHORTCUT_API_BASE_URL,
        "telegram_id": user_id,
        "pairing_code": codigo,
    }, separators=(",", ":"), ensure_ascii=False)
    return f"{SHORTCUT_API_BASE_URL}/api/shortcut/open?{urlencode({'text': entrada})}"


async def site_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gera um link pessoal para consultar e editar a despensa no site."""
    token = tokens.criar_token(update.effective_user.id)
    await update.effective_message.reply_text(
        f"Seu link pessoal (não compartilhe):\n{URL_SITE}/#t={token}"
    )


async def listar_despensa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    async with _obter_lock_usuario(user_id):
        await _listar_despensa(update)


async def _listar_despensa(update: Update):
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


async def verificar_lembretes(context: ContextTypes.DEFAULT_TYPE):
    """Envia no máximo um lembrete por usuário em cada rodada."""
    from datetime import datetime

    if not 9 <= datetime.now().hour < 20:
        return

    for user_id in core.obter_usuarios():
        async with _obter_lock_usuario(user_id):
            item = core.obter_proximo_lembrete(user_id)
            if not item:
                continue

            item_id, _, nome, qtd, unidade, *_ = item
            botoes = [[
                InlineKeyboardButton("Ainda tenho", callback_data=f"lembrete_ok_{item_id}"),
                InlineKeyboardButton("Usei um pouco", callback_data=f"lembrete_usado_{item_id}"),
            ], [
                InlineKeyboardButton("Acabou", callback_data=f"baixar_{item_id}_TUDO"),
                InlineKeyboardButton("Lembrar depois", callback_data=f"lembrete_adiar_{item_id}"),
            ]]
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"Faz alguns dias que você não atualiza o *{nome}*. "
                        f"Ainda tem aproximadamente {qtd:g} {unidade} na despensa?"
                    ),
                    reply_markup=InlineKeyboardMarkup(botoes),
                    parse_mode="Markdown",
                )
                core.registrar_lembrete(item_id, user_id)
            except Exception as erro:
                print(f"Erro ao enviar lembrete para {user_id}: {erro}")


async def lidar_com_botoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    async with _obter_lock_usuario(user_id):
        await _lidar_com_botoes(update, context)


async def _lidar_com_botoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dados = query.data
    user_id = query.from_user.id
    print(f"Botão pressionado por {user_id}: {dados}")

    if dados == "atalho_autenticar":
        await query.message.reply_text(
            "Toque no botão abaixo para abrir o Atalho e vincular sua conta.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Abrir Atalho e autenticar",
                    url=_url_autenticacao_atalho(user_id),
                )
            ]]),
        )
    elif dados.startswith("remover_"):
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
    elif dados.startswith("lembrete_ok_"):
        item_id = int(dados.rsplit("_", 1)[1])
        core.registrar_lembrete(item_id, user_id)
        await query.edit_message_text("Perfeito, mantive essa quantidade registrada. Vou perguntar novamente mais adiante.")
    elif dados.startswith("lembrete_usado_"):
        item_id = int(dados.rsplit("_", 1)[1])
        item = core.selecionar_item(user_id, str(item_id))
        if not item:
            await query.edit_message_text("Esse item não está mais na sua despensa.")
            return
        _, nome, qtd, unid = item
        botoes = [
            [
                InlineKeyboardButton("-1", callback_data=f"baixar_{item_id}_1"),
                InlineKeyboardButton("-0.5", callback_data=f"baixar_{item_id}_0.5"),
            ],
            [InlineKeyboardButton("Acabou Tudo!", callback_data=f"baixar_{item_id}_TUDO")],
        ]
        await query.edit_message_text(
            f"Quanto você utilizou de {nome}?\nEstoque atual: {qtd} {unid}",
            reply_markup=InlineKeyboardMarkup(botoes),
        )
    elif dados.startswith("lembrete_adiar_"):
        item_id = int(dados.rsplit("_", 1)[1])
        core.adiar_lembrete(item_id, user_id)
        await query.edit_message_text("Tudo bem. Vou lembrar você novamente daqui a alguns dias.")
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
    async with _obter_lock_usuario(user_id):
        resultado = await asyncio.to_thread(
            core.interpretar_mensagem,
            update.message.text,
            user_id,
            user_nome,
        )

        if resultado["acao"] == "consultar":
            if resultado.get("resposta"):
                await mensagem_espera.edit_text(resultado["resposta"])
            else:
                await mensagem_espera.delete()
            await _listar_despensa(update)
        else:
            await mensagem_espera.edit_text(resultado["resposta"])


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    mensagem_espera = await update.message.reply_text("Recebi a nota! 🔍 Lendo os itens...")
    async with _obter_lock_usuario(user_id):
        foto = update.message.photo[-1]
        arquivo_foto = await context.bot.get_file(foto.file_id)
        foto_bytes = await arquivo_foto.download_as_bytearray()
        user = update.message.from_user
        resultado = await asyncio.to_thread(
            core.processar_nota,
            foto_bytes,
            user.id,
            user.first_name,
        )

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
