"""API e página do site da despensa, usando as regras do bot."""

from math import isfinite
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from handlers import core
from site_web import tokens

app = FastAPI(title="Minha despensa")
PASTA = Path(__file__).parent


def usuario(x_token: str | None = Header(default=None)) -> int:
    user_id = tokens.usuario_do_token(x_token) if x_token else None
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Link inválido. Peça um novo com /site no bot.",
        )
    return user_id


class Consumo(BaseModel):
    item_id: int = Field(gt=0)
    quantidade: str = Field(min_length=1, max_length=20)


class NovoItem(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    quantidade: float = Field(gt=0)
    unidade: Literal["unidade", "kg", "L"] = "unidade"
    categoria: str = Field(default="Outros", min_length=1, max_length=40)


@app.get("/")
def pagina():
    return FileResponse(PASTA / "index.html")


@app.middleware("http")
async def impedir_cache(request, call_next):
    resposta = await call_next(request)
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


@app.get("/api/despensa")
def listar(user_id: int = Depends(usuario)):
    return [
        {"id": item_id, "nome": nome, "quantidade": quantidade, "unidade": unidade}
        for item_id, nome, quantidade, unidade in core.obter_itens_despensa(user_id)
    ]


@app.post("/api/consumir")
def consumir(corpo: Consumo, user_id: int = Depends(usuario)):
    quantidade = corpo.quantidade.strip()
    if quantidade.upper() != "TUDO":
        try:
            valor = float(quantidade)
        except ValueError as erro:
            raise HTTPException(status_code=422, detail="Quantidade inválida.") from erro
        if not isfinite(valor) or valor <= 0:
            raise HTTPException(status_code=422, detail="A quantidade deve ser maior que zero.")
        quantidade = str(valor)
    else:
        quantidade = "TUDO"

    return {"mensagem": core.consumir_item(corpo.item_id, user_id, quantidade)}


@app.post("/api/adicionar")
def adicionar(corpo: NovoItem, user_id: int = Depends(usuario)):
    nome = corpo.nome.strip()
    unidade = corpo.unidade.strip()
    categoria = corpo.categoria.strip()
    if not nome or not unidade or not categoria or not isfinite(corpo.quantidade):
        raise HTTPException(status_code=422, detail="Preencha os dados do item corretamente.")

    nome_adicionado, erro = core._adicionar_item(user_id, {
        "item_alvo": nome,
        "quantidade": corpo.quantidade,
        "unidade_medida": unidade,
        "categoria": categoria,
    })
    if erro:
        raise HTTPException(status_code=400, detail=erro)
    return {"mensagem": f"Adicionado: {nome_adicionado}"}
