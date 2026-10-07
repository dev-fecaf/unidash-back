"""Ajudantes comuns dos testes: usuário simulado e ingresso do portal."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.dominios.portal.usuarios import PERMISSOES_UNIDASH, UsuarioPortal

SEGREDO_INGRESSO = "segredo-do-ingresso-de-teste-com-32-caracteres"  # igual ao conftest
USU_ID = uuid.uuid4()


def usuario(**mudancas) -> UsuarioPortal:
    base = dict(
        usu_id=USU_ID, nome="Pessoa Teste", email="pessoa@fecaf.com.br", perfil="engenharia_dados",
        ativo=True, perfil_ativo=True, deve_trocar_senha=False, permissoes=frozenset(PERMISSOES_UNIDASH),
    )
    base.update(mudancas)
    return UsuarioPortal(**base)


def ingresso(segredo=SEGREDO_INGRESSO, validade=60, aud="unidash", sub=None, jti=None, algoritmo="HS256", **extras):
    agora = datetime.now(timezone.utc)
    dados = {
        "sub": str(sub or USU_ID), "aud": aud, "iat": agora,
        "exp": agora + timedelta(seconds=validade), "jti": jti or uuid.uuid4().hex, **extras,
    }
    return jwt.encode(dados, segredo, algorithm=algoritmo)
