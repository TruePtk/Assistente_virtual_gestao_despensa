"""Casos de uso da despensa, sem dependência de uma plataforma de mensagens."""

import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher

import ai_config.ai_service as ai_service
import database.database as database

CADENCIA_LEMBRETES_DIAS = {
    "Laticínios": 5,
    "Hortifruti": 5,
    "Outros": 7,
    "Mercearia": 15,
    "Doces e Guloseimas": 15,
    "Limpeza": 30,
}


def obter_itens_despensa(user_id: int):
    """Retorna os itens da despensa de um usuário."""
    return database.obter_despensa(user_id)


def obter_proximo_lembrete(user_id: int):
    """Escolhe o item mais antigo que já pode gerar um lembrete."""
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    for item in database.obter_itens_para_lembrete(user_id):
        data_base = item[6] or item[5]
        try:
            data_base = datetime.fromisoformat(data_base)
        except (TypeError, ValueError):
            continue

        categoria = item[9] or "Outros"
        dias = CADENCIA_LEMBRETES_DIAS.get(categoria, 7)
        if (agora - data_base).days < dias:
            continue

        ultimo_lembrete = item[7]
        if ultimo_lembrete:
            try:
                ultimo_lembrete = datetime.fromisoformat(ultimo_lembrete)
            except ValueError:
                continue
            if (agora - ultimo_lembrete).days < 14:
                continue
        return item
    return None


def registrar_lembrete(item_id: int, user_id: int) -> bool:
    return database.registrar_lembrete(item_id, user_id)


def adiar_lembrete(item_id: int, user_id: int) -> bool:
    return database.adiar_lembrete(item_id, user_id)


def obter_usuarios():
    return database.obter_usuarios()


def _normalizar_nome(nome: str) -> str:
    """Normaliza acentos, pontuação e plural para comparar nomes locais."""
    sem_acentos = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    nome_normalizado = re.sub(r"[^a-z0-9 ]", " ", sem_acentos.lower())
    palavras = [palavra[:-1] if len(palavra) > 3 and palavra.endswith("s") else palavra
                for palavra in nome_normalizado.split()]
    return " ".join(palavras)


def _encontrar_candidatos(user_id: int, nome: str):
    """Retorna os itens que podem corresponder ao nome informado."""
    itens = obter_itens_despensa(user_id)
    nome_normalizado = _normalizar_nome(nome)
    exatos = [item for item in itens if _normalizar_nome(item[1]) == nome_normalizado]
    if exatos:
        return exatos

    palavras_nome = set(nome_normalizado.split())
    candidatos = []
    for item in itens:
        nome_item_normalizado = _normalizar_nome(item[1])
        palavras_item = set(nome_item_normalizado.split())
        palavras_contidas = palavras_nome <= palavras_item or palavras_item <= palavras_nome
        similaridade = SequenceMatcher(None, nome_normalizado, nome_item_normalizado).ratio()
        if palavras_contidas or similaridade >= 0.82:
            candidatos.append(item)
    return candidatos


def _encontrar_item(user_id: int, nome: str):
    """Retorna um item único correspondente ou ``None`` quando não é seguro decidir."""
    candidatos = _encontrar_candidatos(user_id, nome)
    return candidatos[0] if len(candidatos) == 1 else None


def _adicionar_item(user_id: int, operacao: dict):
    """Soma um item existente ou cria um novo, recusando nomes ambíguos."""
    nome = operacao["item_alvo"]
    quantidade = float(operacao["quantidade"])
    candidatos = _encontrar_candidatos(user_id, nome)
    if len(candidatos) > 1:
        return None, f"Encontrei mais de um item parecido com {nome}. Seja mais específico."

    if candidatos:
        item = candidatos[0]
        database.adicionar_quantidade_item(item[0], user_id, quantidade)
        return item[1], None

    database.salvar_item_despensa(
        telegram_id=user_id,
        nome_produto=nome,
        quantidade=quantidade,
        unidade_medida=operacao.get("unidade_medida", "unidade"),
        nome_categoria=operacao.get("categoria", "Outros"),
    )
    return nome, None


def interpretar_mensagem(texto: str, user_id: int, user_nome: str = "") -> dict:
    """Interpreta e executa todas as operações de uma mensagem de texto."""
    intencao = ai_service.interpretar_intencao_usuario(texto)
    operacoes = intencao.get("operacoes", [])

    # Aceita temporariamente o formato antigo para não quebrar integrações existentes.
    if not operacoes and intencao.get("acao"):
        operacoes = [intencao]

    if not operacoes:
        return {"acao": "erro", "resposta": "Não consegui entender sua solicitação."}

    respostas = []
    for operacao in operacoes:
        acao = operacao.get("acao")

        if acao == "erro":
            return {"acao": "erro", "resposta": "Não consegui entender sua solicitação."}
        if acao == "consumir":
            nome = operacao.get("item_alvo", "")
            if _normalizar_nome(nome) == "tudo":
                itens_removidos = database.esvaziar_despensa(user_id)
                respostas.append(
                    "Despensa esvaziada. "
                    f"{itens_removidos} item(ns) removido(s)."
                )
                continue
            candidatos = _encontrar_candidatos(user_id, nome)
            if len(candidatos) > 1:
                respostas.append(f"Encontrei mais de um item parecido com {nome}. Seja mais específico.")
                continue
            item = candidatos[0] if candidatos else None
            if not item:
                respostas.append(f"Não encontrei {nome} na sua despensa.")
                continue
            quantidade = operacao.get("quantidade", operacao.get("quantidade_mencionada", 1))
            respostas.append(database.consumir_quantidade_item(item[0], user_id, quantidade))
        elif acao == "adicionar":
            try:
                nome, erro = _adicionar_item(user_id, operacao)
                if erro:
                    respostas.append(erro)
                    continue
                respostas.append(
                    f"Adicionado: {float(operacao['quantidade']):g} "
                    f"{operacao.get('unidade_medida', 'unidade')} de {nome}."
                )
            except (KeyError, TypeError, ValueError):
                respostas.append(f"Não consegui adicionar {operacao.get('item_alvo', 'o item')}.")
        elif acao == "duvida_geral":
            respostas.append(intencao.get("resposta", intencao.get("Obs", "Não consegui entender sua dúvida.")))
        elif acao == "consultar":
            return {"acao": "consultar", "itens": obter_itens_despensa(user_id)}
        else:
            respostas.append("Não reconheci essa operação.")

    if user_nome:
        database.cadastrar_usuario(user_id, user_nome)
    return {"acao": "resposta", "resposta": "\n".join(respostas)}


def processar_nota(foto_bytes: bytearray, user_id: int, user_nome: str) -> dict:
    """Processa uma nota e salva os itens extraídos."""
    resultado = ai_service.processar_nota_fiscal(foto_bytes)
    if "erro" in resultado:
        return resultado

    database.cadastrar_usuario(user_id, user_nome)
    avisos = []
    for item in resultado.get("itens", []):
        _, erro = _adicionar_item(
            user_id,
            {
                "item_alvo": item["nome"],
                "quantidade": item["quantidade"],
                "unidade_medida": item["unidade_medida"],
                "categoria": item["categoria"],
            },
        )
        if erro:
            avisos.append(erro)
    if avisos:
        resultado["avisos"] = avisos
    return resultado


def selecionar_item(user_id: int, item_id: str):
    """Busca um item pelo identificador, validando o dono da despensa."""
    return next((item for item in obter_itens_despensa(user_id) if str(item[0]) == item_id), None)


def consumir_item(item_id: int, user_id: int, quantidade: str) -> str:
    """Registra o consumo de uma quantidade."""
    return database.consumir_quantidade_item(item_id, user_id, quantidade)