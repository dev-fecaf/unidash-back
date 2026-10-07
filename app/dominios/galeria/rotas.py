"""Galeria: lista dos dashboards cadastrados, para o time de dados navegar e pré-visualizar."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Connection, text

from app.db.sessao import obter_conexao
from app.dominios.portal.dependencias import exigir
from app.dominios.portal.usuarios import UsuarioPortal

router = APIRouter(prefix="/galeria", tags=["galeria"])

GALERIA = "dashboards.galeria.visualizar"


class DashboardResumo(BaseModel):
    hash: str
    nome: str
    descricao: str | None
    status: str
    categoria: str
    paginas: int
    responsavel_login: str | None
    atualizado_em: datetime


_SQL_DASHBOARDS = text("""
    SELECT d.hash, d.nome, d.descricao, d.status, d.responsavel_login, d.atualizado_em,
           c.nome AS categoria,
           count(p.id) FILTER (WHERE p.ativo) AS paginas
    FROM unidash.dashboard d
    JOIN unidash.categoria c ON c.id = d.categoria_id
    LEFT JOIN unidash.pagina p ON p.dashboard_id = d.id
    GROUP BY d.id, c.id
    ORDER BY c.ordem, c.nome, d.nome
""")


def listar_dashboards(conexao: Connection) -> list[DashboardResumo]:
    return [DashboardResumo(**linha) for linha in conexao.execute(_SQL_DASHBOARDS).mappings()]


@router.get("/dashboards", response_model=list[DashboardResumo])
def dashboards(
    _usuario: Annotated[UsuarioPortal, Depends(exigir(GALERIA))],
    conexao: Annotated[Connection, Depends(obter_conexao)],
) -> list[DashboardResumo]:
    return listar_dashboards(conexao)
