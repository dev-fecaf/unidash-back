"""Rota de saúde: diz se o back está no ar e se consegue falar com o banco."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import obter_config
from app.db.sessao import obter_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saude", tags=["saúde"])


@router.get("")
def saude() -> JSONResponse:
    try:
        with obter_engine().connect() as conexao:
            conexao.execute(text("SELECT 1"))
        banco = "ok"
    except SQLAlchemyError:
        # O motivo real fica só no log do servidor
        logger.exception("Rota de saúde: falha ao conectar no banco")
        banco = "falha"

    tudo_ok = banco == "ok"
    return JSONResponse(
        status_code=200 if tudo_ok else 503,
        content={
            "status": "ok" if tudo_ok else "com_problema",
            "ambiente": obter_config().ambiente,
            "banco": banco,
        },
    )
