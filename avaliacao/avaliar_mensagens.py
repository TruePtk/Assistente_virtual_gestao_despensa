"""Avaliação do assistente: roda as perguntas de perguntas.csv contra o core.py.

Uso (a partir da raiz do repositório, com o .env preenchido):
    python avaliacao/avaliar_mensagens.py --repeticoes 3

Cada pergunta roda sobre uma despensa de teste idêntica (banco separado,
avaliacao/despensa_teste.db), então o banco real não é tocado. Os resultados
detalhados vão para avaliacao/resultados/ e o resumo é impresso no terminal.
"""

import argparse
import csv
import json
import sqlite3
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)  # o config.py lê o .env a partir daqui

import ai_config.ai_service as ai_service
import database.database as database
from handlers import core

USER_ID = 999999999
DB_TESTE = str(RAIZ / "avaliacao" / "despensa_teste.db")

SEED = [
    ("Arroz", 2, "kg", "Mercearia"),
    ("Feijão", 1, "kg", "Mercearia"),
    ("Macarrão", 3, "pacote", "Mercearia"),
    ("Leite", 4, "litro", "Laticínios"),
    ("Leite Condensado", 2, "unidade", "Laticínios"),
    ("Ovos", 12, "unidade", "Outros"),
    ("Queijo Mussarela", 1, "kg", "Laticínios"),
    ("Queijo Prato", 1, "kg", "Laticínios"),
    ("Iogurte Natural", 6, "unidade", "Laticínios"),
    ("Banana", 6, "unidade", "Hortifruti"),
    ("Tomate", 5, "unidade", "Hortifruti"),
    ("Cebola", 3, "unidade", "Hortifruti"),
    ("Detergente", 2, "unidade", "Limpeza"),
    ("Sabão em Pó", 1, "kg", "Limpeza"),
    ("Chocolate", 3, "unidade", "Doces e Guloseimas"),
    ("Biscoito Recheado", 2, "pacote", "Doces e Guloseimas"),
]
norm = core._normalizar_nome
ESTADO_INICIAL = {norm(n): float(q) for n, q, _, _ in SEED}

# Captura o JSON de intenção devolvido pela IA, sem chamar a API duas vezes.
_original = ai_service.interpretar_intencao_usuario
_ultima = {}


def _interpretar_registrando(texto):
    _ultima["intencao"] = _original(texto)
    return _ultima["intencao"]


ai_service.interpretar_intencao_usuario = _interpretar_registrando


def resetar_banco():
    # No Windows não dá pra apagar o .db (o database.py deixa conexões abertas),
    # então o arquivo fica e só as tabelas são esvaziadas.
    database.DB_FILE = DB_TESTE
    database.inicializar_banco()
    conn = sqlite3.connect(DB_TESTE)
    try:
        conn.execute("DELETE FROM itens_despensa")
        conn.execute("DELETE FROM usuarios")
        conn.commit()
    finally:
        conn.close()
    database.cadastrar_usuario(USER_ID, "Teste")
    for nome, qtd, unidade, categoria in SEED:
        database.salvar_item_despensa(USER_ID, nome, qtd, unidade, categoria)


def estado_atual():
    estado = defaultdict(float)
    for _, nome, qtd, _ in database.obter_despensa(USER_ID):
        estado[norm(nome)] += qtd
    return dict(estado)


def achar(estado, nome):
    """Chave igual (normalizada); itens novos aceitam também nome contido no outro."""
    if nome in estado:
        return nome
    if nome in ESTADO_INICIAL:
        return None
    palavras = set(nome.split())
    for chave in estado:
        if chave in ESTADO_INICIAL:
            continue
        p = set(chave.split())
        if palavras <= p or p <= palavras:
            return chave
    return None


def estado_esperado(overrides):
    estado = dict(ESTADO_INICIAL)
    for nome, valor in overrides.items():
        chave = achar(estado, norm(nome)) or norm(nome)
        if valor is None:
            estado.pop(chave, None)
        else:
            estado[chave] = float(valor)
    return estado


def comparar(esperado, obtido):
    extras, faltando, divergentes = [], [], []
    for nome, qtd in obtido.items():
        chave = achar(esperado, nome)
        if chave is None:
            extras.append(nome)
        elif abs(esperado[chave] - qtd) > 1e-6:
            divergentes.append(f"{nome}: esperado {esperado[chave]:g}, obtido {qtd:g}")
    faltando = [n for n in esperado if achar(obtido, n) is None]
    return extras, faltando, divergentes


def acoes_da_intencao(intencao):
    ops = intencao.get("operacoes") or ([intencao] if intencao.get("acao") else [])
    return sorted(str(op.get("acao", "?")) for op in ops if isinstance(op, dict))


def rodar_uma(linha):
    resetar_banco()
    _ultima.clear()
    esperado_acoes = sorted(linha["acoes_esperadas"].split("|"))
    esperado = estado_esperado(json.loads(linha["estado_esperado"]))
    r = {"acoes_obtidas": "", "divergencias": "", "item_inventado": False,
         "tipo_erro": "", "resposta_bot": ""}
    inicio = time.perf_counter()
    try:
        saida = core.interpretar_mensagem(linha["mensagem"], USER_ID, "Teste")
    except Exception as erro:
        r["tempo_s"] = round(time.perf_counter() - inicio, 2)
        r.update(intencao_ok=False, estado_ok=False, acerto=False,
                 tipo_erro="excecao", resposta_bot=f"{type(erro).__name__}: {erro}"[:200])
        return r
    r["tempo_s"] = round(time.perf_counter() - inicio, 2)

    intencao = _ultima.get("intencao", {})
    obtidas = acoes_da_intencao(intencao)
    r["acoes_obtidas"] = "|".join(obtidas)
    if saida.get("acao") == "consultar":
        r["resposta_bot"] = f"[lista com {len(saida['itens'])} itens]"
    else:
        r["resposta_bot"] = str(saida.get("resposta", ""))[:200].replace("\n", " / ")

    extras, faltando, divergentes = comparar(esperado, estado_atual())
    r["intencao_ok"] = obtidas == esperado_acoes
    r["estado_ok"] = not (extras or faltando or divergentes)
    r["acerto"] = r["intencao_ok"] and r["estado_ok"]
    r["item_inventado"] = bool(extras)
    r["divergencias"] = "; ".join(
        [f"item extra: {n}" for n in extras]
        + [f"item sumiu: {n}" for n in faltando] + divergentes)
    if intencao.get("acao") == "erro":
        r["tipo_erro"] = "ia_indisponivel"
    elif not r["intencao_ok"]:
        r["tipo_erro"] = "intencao"
    elif not r["estado_ok"]:
        r["tipo_erro"] = "estado"
    return r


def pct(parte, total):
    return f"{100 * parte / total:5.1f}%" if total else "   -  "


def resumo(resultados, n_rep):
    total = len(resultados)
    print("\n" + "=" * 60)
    print(f"RESUMO ({total} execuções, {n_rep} repetição(ões) por pergunta)")
    print("=" * 60)
    print(f"Acerto geral:            {pct(sum(r['acerto'] for r in resultados), total)}")
    print(f"  intenção correta:      {pct(sum(r['intencao_ok'] for r in resultados), total)}")
    print(f"  estado final correto:  {pct(sum(r['estado_ok'] for r in resultados), total)}")
    print(f"Item inventado (proxy de alucinação): "
          f"{pct(sum(r['item_inventado'] for r in resultados), total)}")
    print(f"Falhas de IA/exceções:   "
          f"{pct(sum(r['tipo_erro'] in ('ia_indisponivel', 'excecao') for r in resultados), total)}")
    tempos = [r["tempo_s"] for r in resultados]
    p95 = sorted(tempos)[max(0, int(len(tempos) * 0.95) - 1)]
    print(f"Tempo: média {statistics.mean(tempos):.2f}s | "
          f"mediana {statistics.median(tempos):.2f}s | p95 {p95:.2f}s")

    por_cat = defaultdict(list)
    por_pergunta = defaultdict(list)
    for r in resultados:
        por_cat[r["categoria"]].append(r["acerto"])
        por_pergunta[r["id"]].append(r["acerto"])
    print("\nAcerto por categoria:")
    for cat, v in por_cat.items():
        print(f"  {cat:<10} {pct(sum(v), len(v))}  ({sum(v)}/{len(v)})")
    if n_rep > 1:
        estaveis = sum(len(set(v)) == 1 for v in por_pergunta.values())
        print(f"\nConsistência: {pct(estaveis, len(por_pergunta))} das perguntas "
              f"tiveram o mesmo resultado em todas as repetições")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--perguntas", default=str(RAIZ / "avaliacao" / "perguntas.csv"))
    ap.add_argument("--repeticoes", type=int, default=3)
    ap.add_argument("--pausa", type=float, default=1.0, help="segundos entre chamadas (limite da API)")
    ap.add_argument("--limite", type=int, default=0, help="roda só as N primeiras perguntas (piloto)")
    args = ap.parse_args()

    with open(args.perguntas, newline="", encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    if args.limite:
        linhas = linhas[: args.limite]

    resultados = []
    total = len(linhas) * args.repeticoes
    for rep in range(1, args.repeticoes + 1):
        for linha in linhas:
            r = rodar_uma(linha)
            r.update(execucao=rep, id=linha["id"], categoria=linha["categoria"],
                     mensagem=linha["mensagem"], acoes_esperadas=linha["acoes_esperadas"])
            resultados.append(r)
            marca = "OK " if r["acerto"] else "ERRO"
            print(f"[{len(resultados)}/{total}] {marca} #{linha['id']} {linha['mensagem'][:45]}"
                  + (f"  -> {r['divergencias'] or r['tipo_erro']}" if not r["acerto"] else ""))
            time.sleep(args.pausa)

    pasta = RAIZ / "avaliacao" / "resultados"
    pasta.mkdir(exist_ok=True)
    arquivo = pasta / f"resultados_{datetime.now():%Y%m%d_%H%M%S}.csv"
    campos = ["execucao", "id", "categoria", "mensagem", "acoes_esperadas", "acoes_obtidas",
              "intencao_ok", "estado_ok", "acerto", "item_inventado", "divergencias",
              "tipo_erro", "tempo_s", "resposta_bot"]
    with open(arquivo, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(resultados)

    resumo(resultados, args.repeticoes)
    print(f"\nResultados detalhados: {arquivo}")


if __name__ == "__main__":
    main()
