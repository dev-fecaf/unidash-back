"""Travas das rotas da área do time de dados.

Toda rota protegida usa `UsuarioDoTime` (ou `exigir(...)` para uma tela específica).
A cada pedido, o UniDash relê a pessoa e as permissões no banco: se o admin desativar
alguém ou tirar uma permissão no UniData, vale na hora, sem esperar a sessão vencer.
"""

import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import Connection

from app.db.sessao import obter_conexao
from app.dominios.portal import tokens, usuarios
from app.dominios.portal.usuarios import ACESSAR, UsuarioPortal

logger = logging.getLogger(__name__)

COOKIE_SESSAO = "unidash_sessao"


def _nao_autenticado() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Entre pelo portal UniData para continuar.")


def obter_usuario_do_time(
    request: Request, conexao: Annotated[Connection, Depends(obter_conexao)]
) -> UsuarioPortal:
    token = request.cookies.get(COOKIE_SESSAO)
    if not token:
        raise _nao_autenticado()
    try:
        usu_id = tokens.ler_sessao(token)
    except tokens.EntradaIndisponivel:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "A entrada pelo portal ainda não foi configurada.")
    except tokens.TokenInvalido as erro:
        logger.info("Sessão recusada: %s", erro)
        raise _nao_autenticado()

    usuario = usuarios.carregar_usuario(conexao, usu_id)
    if usuario is None or not usuario.pode_entrar:
        logger.info("Sessão de usuário inexistente, inativo ou com troca de senha pendente: %s", usu_id)
        raise _nao_autenticado()
    if not usuario.tem(ACESSAR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Você não tem acesso ao módulo Dashboards.")
    return usuario


UsuarioDoTime = Annotated[UsuarioPortal, Depends(obter_usuario_do_time)]


def exigir(permissao: str) -> Callable[..., UsuarioPortal]:
    """Trava de uma tela: 403 se a pessoa não tem a permissão (o admin sempre tem)."""

    def _verificar(usuario: UsuarioDoTime) -> UsuarioPortal:
        if not usuario.tem(permissao):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Você não tem permissão para esta tela.")
        return usuario

    return _verificar
