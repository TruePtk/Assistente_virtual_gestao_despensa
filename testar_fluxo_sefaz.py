"""
Script de validação técnica do fluxo SEFAZ (QR Code -> resposta da consulta de NFC-e).

CONTEXTO IMPORTANTE
--------------------
A consulta pública de NFC-e (a que abre quando você escaneia o QR Code de uma
nota) foi feita para EXIBIÇÃO em navegador, não como uma API limpa. Na prática,
isso costuma significar:

  - A maioria dos estados retorna uma página HTML (às vezes .aspx), não um XML
    "cru" pronto para dar parse com xmltodict.
  - O XML oficial completo e assinado normalmente só é liberado para quem tem
    certificado digital (e-CNPJ/e-CPF) vinculado à operação — não para o
    consumidor comum via QR Code.
  - Alguns estados podem exigir JavaScript, ter captcha, ou aplicar rate limit
    por IP.

Isso NÃO inviabiliza o projeto — só significa que o módulo de extração
provavelmente vai precisar de parsing de HTML (ex: BeautifulSoup) além de (ou
em vez de) xmltodict, dependendo do estado. Este script existe justamente para
descobrir, empiricamente, o que cada estado retorna, e documentar isso como
parte da validação técnica pedida pelo orientador.

COMO USAR
---------
1. Escaneie o QR Code de uma nota fiscal pelo navegador do celular (como o
   próprio projeto prevê).
2. Copie a URL completa que abrir no navegador.
3. Rode este script uma vez (ele vai criar um arquivo "urls.txt" com um
   modelo, se ainda não existir).
4. Edite "urls.txt" e adicione suas URLs, uma por linha, no formato:
       UF;URL
5. Rode o script de novo: python3 testar_fluxo_sefaz.py
6. Resultados aparecem no terminal e são salvos/acumulados em
   "sefaz_test_log.csv" (útil para depois tabular por categoria no TCC).

Dependência: pip install requests
"""

import csv
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

URLS_FILE = Path("urls.txt")
LOG_FILE = Path("sefaz_test_log.csv")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

TIMEOUT = 15  # segundos por requisição
DELAY_BETWEEN_REQUESTS = 2  # segundos, para não sobrecarregar o servidor da SEFAZ

TEMPLATE_URLS_FILE = """# Arquivo de URLs para teste do fluxo SEFAZ (NFC-e)
# Formato: UF;URL   (uma nota por linha)
#
# Como preencher:
#   1. Escaneie o QR Code de uma nota fiscal com a camera/navegador do celular.
#   2. Copie a URL completa que abrir no navegador.
#   3. Adicione uma linha abaixo no formato UF;URL
#      (UF = estado que emitiu a nota, ex: SP, RJ, MG, PE...)
#
# Exemplo (troque pela URL real da sua nota - isto abaixo é so ilustrativo):
# SP;https://www.fazenda.sp.gov.br/nfce/qrcode?p=35240112345678000199650010000012345123456789|2|1|1
#
# Dica: teste notas de pelo menos 2-3 estados diferentes, se tiver acesso,
# porque cada UF pode se comportar de um jeito.
"""


def extrair_chave_acesso(url: str) -> Optional[str]:
    """Tenta extrair a chave de acesso (44 digitos) da URL do QR Code."""
    match = re.search(r"\b\d{44}\b", url)
    return match.group(0) if match else None


def classificar_resposta(status_code: int, content_type: str, body_amostra: str) -> str:
    """Classifica o resultado em categorias uteis para o TCC (accesibilidade,
    formato, bloqueios). Isso é o dado que vira tabela/gráfico na seção de
    validação técnica.
    """
    body_lower = body_amostra.lower()

    if status_code in (401, 403):
        return "BLOQUEADO_AUTENTICACAO"
    if status_code == 429:
        return "RATE_LIMIT"
    if status_code >= 500:
        return "ERRO_SERVIDOR"
    if status_code >= 400:
        return f"ERRO_HTTP_{status_code}"

    if "captcha" in body_lower or "recaptcha" in body_lower or "g-recaptcha" in body_lower:
        return "BLOQUEADO_CAPTCHA"
    if "xml" in content_type:
        return "XML_DIRETO"
    if "json" in content_type:
        return "JSON_DIRETO"
    if "<nfeproc" in body_lower or "<nfe " in body_lower or "<nfe>" in body_lower:
        return "XML_EMBUTIDO_EM_HTML"
    if "html" in content_type or "<html" in body_lower:
        return "HTML_APENAS"

    return "FORMATO_DESCONHECIDO"


def testar_url(uf: str, url: str) -> dict:
    """Faz a requisição e monta um registro com todos os dados relevantes
    para a validação técnica (status, tipo, tempo, classificação, erro)."""
    resultado = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "uf": uf,
        "url": url,
        "chave_acesso": extrair_chave_acesso(url) or "",
        "status_code": None,
        "content_type": "",
        "tempo_resposta_s": None,
        "tamanho_resposta_bytes": None,
        "classificacao": "",
        "erro": "",
    }

    inicio = time.monotonic()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        resultado["tempo_resposta_s"] = round(time.monotonic() - inicio, 2)
        resultado["status_code"] = resp.status_code
        resultado["content_type"] = resp.headers.get("Content-Type", "")
        resultado["tamanho_resposta_bytes"] = len(resp.content)
        resultado["classificacao"] = classificar_resposta(
            resp.status_code, resultado["content_type"], resp.text[:5000]
        )
    except requests.exceptions.Timeout:
        resultado["tempo_resposta_s"] = round(time.monotonic() - inicio, 2)
        resultado["erro"] = "TIMEOUT"
        resultado["classificacao"] = "TIMEOUT"
    except requests.exceptions.ConnectionError as e:
        resultado["erro"] = f"ERRO_CONEXAO: {e}"
        resultado["classificacao"] = "ERRO_CONEXAO"
    except requests.exceptions.RequestException as e:
        resultado["erro"] = str(e)
        resultado["classificacao"] = "ERRO_DESCONHECIDO"

    return resultado


def carregar_urls() -> list:
    """Lê urls.txt. Se o arquivo nao existir, cria um modelo e encerra,
    pedindo para o usuario preencher antes de rodar de novo."""
    if not URLS_FILE.exists():
        URLS_FILE.write_text(TEMPLATE_URLS_FILE, encoding="utf-8")
        print(f"Criei o arquivo '{URLS_FILE}' com um modelo (nenhuma URL real ainda).")
        print("Edite esse arquivo adicionando suas URLs (formato UF;URL) e rode o script de novo.")
        sys.exit(0)

    urls = []
    for linha in URLS_FILE.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if ";" not in linha:
            print(f"Linha ignorada (formato invalido, use 'UF;URL'): {linha}")
            continue
        uf, url = linha.split(";", 1)
        urls.append((uf.strip().upper(), url.strip()))

    if not urls:
        print(f"'{URLS_FILE}' existe mas nao tem nenhuma URL valida ainda. Adicione linhas 'UF;URL'.")
        sys.exit(0)

    return urls


def salvar_log(resultados: list) -> None:
    """Acumula os resultados em um CSV (append), para dar pra juntar testes
    de dias/notas diferentes numa tabela só depois."""
    novo_arquivo = not LOG_FILE.exists()
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        campos = list(resultados[0].keys())
        writer = csv.DictWriter(f, fieldnames=campos)
        if novo_arquivo:
            writer.writeheader()
        writer.writerows(resultados)


def main():
    urls = carregar_urls()
    print(f"{len(urls)} URL(s) carregada(s) de '{URLS_FILE}'\n")

    resultados = []
    for i, (uf, url) in enumerate(urls, start=1):
        print(f"[{i}/{len(urls)}] Testando {uf}: {url[:90]}")
        resultado = testar_url(uf, url)
        resultados.append(resultado)

        print(
            f"    Status: {resultado['status_code']} | "
            f"Content-Type: {resultado['content_type'] or '(vazio)'} | "
            f"Tempo: {resultado['tempo_resposta_s']}s | "
            f"Classificacao: {resultado['classificacao']}"
        )
        if resultado["erro"]:
            print(f"    Erro: {resultado['erro']}")
        print()

        if i < len(urls):
            time.sleep(DELAY_BETWEEN_REQUESTS)

    salvar_log(resultados)

    print("=" * 70)
    print("RESUMO")
    print("=" * 70)
    for r in resultados:
        print(f"{r['uf']:>4} | {r['classificacao']:<25} | {r['url'][:65]}")
    print(f"\nResultados salvos/acumulados em: {LOG_FILE.resolve()}")
    print(
        "\nDica: se a classificacao vier HTML_APENAS, isso é esperado em vários "
        "estados — o proximo passo é ver se dá pra extrair os produtos direto "
        "do HTML (ex: BeautifulSoup) em vez de esperar um XML puro."
    )


if __name__ == "__main__":
    main()
