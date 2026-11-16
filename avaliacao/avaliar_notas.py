"""Executa a extração visual das notas sem gravar itens na despensa.

Uso na raiz do repositório:
    python avaliacao/avaliar_notas.py caminho/para/fotos_anonimizadas

Aceita imagens JPEG. Os arquivos devem ter nomes anônimos (por exemplo, NF01.jpg).
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ai_config.ai_service import processar_nota_fiscal


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("imagens", type=Path, help="Pasta com fotos JPEG previamente anonimizadas")
    parser.add_argument("--saida", type=Path, help="CSV de saída (padrão: avaliacao/resultados)")
    args = parser.parse_args()

    pasta = args.imagens.resolve()
    if not pasta.is_dir():
        parser.error(f"Pasta de imagens não encontrada: {pasta}")

    imagens = sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg"})
    if not imagens:
        parser.error("A pasta não contém imagens .jpg ou .jpeg.")

    saida = args.saida or RAIZ / "avaliacao" / "resultados" / f"fotos_{datetime.now():%Y%m%d_%H%M%S}.csv"
    saida = saida.resolve()
    saida.parent.mkdir(parents=True, exist_ok=True)

    with saida.open("w", newline="", encoding="utf-8-sig") as arquivo:
        campos = ["imagem_id", "status", "itens_extraidos", "erro"]
        escritor = csv.DictWriter(arquivo, fieldnames=campos, delimiter=";")
        escritor.writeheader()

        for indice, imagem in enumerate(imagens, start=1):
            print(f"[{indice}/{len(imagens)}] Extraindo {imagem.name}...")
            try:
                resultado = processar_nota_fiscal(bytearray(imagem.read_bytes()))
                erro = resultado.get("erro", "") if isinstance(resultado, dict) else "resposta inválida"
                itens = resultado.get("itens", []) if isinstance(resultado, dict) else []
                status = "erro" if erro else "ok"
                escritor.writerow({
                    "imagem_id": imagem.stem,
                    "status": status,
                    "itens_extraidos": json.dumps(itens, ensure_ascii=False),
                    # Não registra a resposta bruta da IA em caso de erro.
                    "erro": str(erro)[:250],
                })
            except Exception as erro:
                escritor.writerow({
                    "imagem_id": imagem.stem,
                    "status": "excecao",
                    "itens_extraidos": "[]",
                    "erro": f"{type(erro).__name__}: {erro}"[:250],
                })

    print(f"Resultado salvo em: {saida}")
    print("Compare os itens extraídos com o gabarito manual; não ajuste o sistema durante a avaliação.")


if __name__ == "__main__":
    main()
