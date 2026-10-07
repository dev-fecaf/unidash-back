"""Link de embed (dashboard aberto pelo Hub): entrar com o token do Hub e conferir a página.

Fluxo completo em docs/integracao-hub.md. Resumo:
1. A página /embed/{hash} recebe do Hub o token (postMessage) e chama POST /embed/entrar.
2. O back confere o token, o status do dashboard e as páginas liberadas, grava o acesso
   e devolve a sessão (só daquele dashboard e daquelas páginas).
3. A página manda a sessão no cabeçalho "Authorization: Bearer ..." nas chamadas seguintes.
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Connection

from app.db.sessao import obter_conexao
from app.dominios.embed import servico, tokens

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embed", tags=["embed (Hub)"])

# Mensagem única para qualquer falha de token: o motivo real fica só no log
MENSAGEM_NEUTRA = "Não foi possível validar o acesso a este dashboard. Recarregue a página e tente novamente."


class EntrarIn(BaseModel):
    hash: str
    token: str


class PaginaOut(BaseModel):
    codigo: str
    nome: str


class DashboardOut(BaseModel):
    hash: str
    nome: str
    paginas: list[PaginaOut]


class EntrarOut(BaseModel):
    # liberado: abre. em_construcao: rascunho. indisponivel: desativado.
    # sem_paginas: o Hub não liberou nenhuma página ativa para a pessoa.
    situacao: Literal["liberado", "em_construcao", "indisponivel", "sem_paginas"]
    sessao: str | None = None
    expira_em_segundos: int | None = None
    dashboard: DashboardOut | None = None


@router.post("/entrar", response_model=EntrarOut, summary="Abrir o dashboard com o token do Hub")
def entrar(dados: EntrarIn, conexao: Annotated[Connection, Depends(obter_conexao)]) -> EntrarOut:
    try:
        pessoa = tokens.validar_token_hub(dados.token, dados.hash)
    except tokens.EmbedIndisponivel as erro:
        logger.error("Embed indisponível: %s", erro)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MENSAGEM_NEUTRA)
    except tokens.TokenInvalido as erro:
        logger.warning("Embed recusado (%s): %s", dados.hash[:40], erro)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAGEM_NEUTRA)

    dashboard = servico.buscar_dashboard(conexao, dados.hash)
    if dashboard is None:
        logger.warning("Embed recusado: token válido para um hash que não existe (%s)", dados.hash[:40])
        return EntrarOut(situacao="indisponivel")
    if dashboard["status"] == "rascunho":
        return EntrarOut(situacao="em_construcao")
    if dashboard["status"] != "publicado":
        return EntrarOut(situacao="indisponivel")

    # Páginas: todas as ativas, ou só as que o Hub liberou (códigos desconhecidos são ignorados)
    paginas = dashboard["paginas"]
    if pessoa.paginas is not None:
        liberadas = set(pessoa.paginas)
        paginas = [p for p in paginas if p["codigo"] in liberadas]
    if not paginas:
        logger.info("Embed sem página liberada: %s em %s", pessoa.login, dados.hash)
        return EntrarOut(situacao="sem_paginas")

    try:
        sessao, duracao = tokens.criar_sessao_embed(dados.hash, pessoa.login, [p["codigo"] for p in paginas])
    except tokens.EmbedIndisponivel as erro:
        logger.error("Embed indisponível: %s", erro)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MENSAGEM_NEUTRA)

    servico.registrar_acesso(conexao, dashboard["id"], pessoa)
    logger.info("Embed aberto: %s em %s (%s páginas)", pessoa.login, dados.hash, len(paginas))
    return EntrarOut(
        situacao="liberado",
        sessao=sessao,
        expira_em_segundos=duracao,
        dashboard=DashboardOut(hash=dashboard["hash"], nome=dashboard["nome"], paginas=paginas),
    )


def sessao_do_embed(hash: str, authorization: Annotated[str | None, Header()] = None) -> dict:
    """Trava das rotas do embed: sessão válida e do mesmo dashboard do endereço.

    Os endpoints de dados (etapa 3) usam esta trava e, depois, `conferir_pagina`.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAGEM_NEUTRA)
    try:
        sessao = tokens.ler_sessao_embed(authorization.removeprefix("Bearer ").strip())
    except tokens.EmbedIndisponivel as erro:
        logger.error("Embed indisponível: %s", erro)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MENSAGEM_NEUTRA)
    except tokens.TokenInvalido as erro:
        logger.info("Sessão do embed recusada: %s", erro)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAGEM_NEUTRA)
    if sessao["dash"] != hash:
        logger.warning("Sessão do dashboard %s usada no %s", sessao["dash"], hash[:40])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAGEM_NEUTRA)
    return sessao


SessaoEmbed = Annotated[dict, Depends(sessao_do_embed)]


def conferir_pagina(sessao: dict, codigo: str) -> None:
    """403 se a página não está entre as liberadas na sessão (o back não entrega os dados)."""
    if codigo not in sessao["pags"]:
        logger.warning("Página não liberada: %s pediu %s", sessao["sub"], codigo[:40])
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Você não tem acesso a esta página.")


class PaginaLiberadaOut(BaseModel):
    codigo: str
    liberada: bool


@router.get(
    "/{hash}/paginas/{codigo}",
    response_model=PaginaLiberadaOut,
    summary="Conferir se a página está liberada na sessão",
)
def pagina(hash: str, codigo: str, sessao: SessaoEmbed) -> PaginaLiberadaOut:
    conferir_pagina(sessao, codigo)
    return PaginaLiberadaOut(codigo=codigo, liberada=True)
