"""Entrada pelo portal UniData: entrar (com o ingresso), quem sou eu, sair."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import Connection

from app.core.config import obter_config
from app.db.sessao import obter_conexao
from app.dominios.portal import tokens, usuarios
from app.dominios.portal.dependencias import COOKIE_SESSAO, UsuarioDoTime
from app.dominios.portal.usuarios import ACESSAR, UsuarioPortal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portal", tags=["entrada pelo portal"])

MENSAGEM_ENTRADA_RECUSADA = (
    "Não foi possível validar a sua entrada. Volte ao portal UniData e clique em Dashboards novamente."
)


class EntrarIn(BaseModel):
    ingresso: str


class EuOut(BaseModel):
    nome: str
    email: str
    perfil: str
    permissoes: list[str]
    portal_url: str


def _eu(usuario: UsuarioPortal) -> EuOut:
    return EuOut(
        nome=usuario.nome,
        email=usuario.email,
        perfil=usuario.perfil,
        permissoes=sorted(usuario.permissoes),
        portal_url=obter_config().portal_url,
    )


@router.post("/entrar", response_model=EuOut)
def entrar(
    dados: EntrarIn, resposta: Response, conexao: Annotated[Connection, Depends(obter_conexao)]
) -> EuOut:
    try:
        usu_id = tokens.validar_ingresso(dados.ingresso)
    except tokens.EntradaIndisponivel as erro:
        logger.error("Entrada pelo portal indisponível: %s", erro)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "A entrada pelo portal ainda não foi configurada.")
    except tokens.TokenInvalido as erro:
        # O motivo real fica só no log; quem tentou recebe a mensagem neutra
        logger.warning("Entrada recusada: %s", erro)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAGEM_ENTRADA_RECUSADA)

    usuario = usuarios.carregar_usuario(conexao, usu_id)
    if usuario is None or not usuario.ativo or not usuario.perfil_ativo:
        logger.warning("Entrada recusada: usuário inexistente ou inativo (%s)", usu_id)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAGEM_ENTRADA_RECUSADA)
    if usuario.deve_trocar_senha:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Troque a sua senha temporária no portal UniData antes de entrar no UniDash.",
        )
    if not usuario.tem(ACESSAR):
        logger.warning("Entrada recusada: sem %s (%s)", ACESSAR, usu_id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Você não tem acesso ao módulo Dashboards.")

    sessao, duracao = tokens.criar_sessao(usu_id)
    resposta.set_cookie(
        COOKIE_SESSAO,
        sessao,
        max_age=duracao,
        httponly=True,  # o JavaScript da página não consegue ler o cookie
        secure=obter_config().ambiente != "dev",  # fora do computador, só por HTTPS
        samesite="strict",  # outros sites não conseguem usar a sessão
        path="/api",
    )
    logger.info("Entrada pelo portal: %s (%s)", usuario.email, usuario.perfil)
    return _eu(usuario)


@router.get("/eu", response_model=EuOut)
def eu(usuario: UsuarioDoTime) -> EuOut:
    return _eu(usuario)


@router.post("/sair", status_code=status.HTTP_204_NO_CONTENT)
def sair(resposta: Response) -> None:
    resposta.delete_cookie(COOKIE_SESSAO, path="/api")
