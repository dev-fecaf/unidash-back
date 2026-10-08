"""Endpoints de dados do dashboard "__NOME_TEXTO__". Criado pelo comando novo_dashboard em __DATA__.

Rota base: /api/v1/dados/__IDENTIFICADOR__/  (incluída sozinha por app/dominios/dados/__init__.py)
Cada gráfico do front chama um endpoint daqui. As consultas leem só o schema __IDENTIFICADOR__ do DW.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.db.dw import obter_engine_dw
from app.dominios.portal.dependencias import exigir
from app.dominios.portal.usuarios import UsuarioPortal

SCHEMA = "__IDENTIFICADOR__"

router = APIRouter(prefix=f"/{SCHEMA}", tags=[f"dados · {SCHEMA}"])

# Por enquanto só o time de dados (sessão do portal). Quem abre pelo Hub entra na etapa 6.
TimeDeDados = Annotated[UsuarioPortal, Depends(exigir("dashboards.gerador.visualizar"))]


@router.get("/tabelas", summary="Tabelas do schema no DW (exemplo)", response_model=list[str])
def tabelas(_u: TimeDeDados):
    """Exemplo: lista as tabelas do schema do dashboard, para conferir a ligação com o DW.

    Pode apagar quando os endpoints de verdade existirem.
    """
    engine = obter_engine_dw()
    if engine is None:
        raise HTTPException(503, "DW não configurado (DW_HOST vazio).")
    with engine.connect() as conexao:
        return list(conexao.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = :schema ORDER BY tablename"),
            {"schema": SCHEMA},
        ).scalars())
