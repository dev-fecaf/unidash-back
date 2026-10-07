"""Galeria: lista dos dashboards cadastrados, para o time de dados navegar e pré-visualizar.

A pré-visualização usa o nome e as páginas do banco (como o embed do Hub), em qualquer status,
e não grava acesso.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Connection, text

from app.db.sessao import obter_conexao
from app.dominios.portal.dependencias import exigir
from app.dominios.portal.usuarios import UsuarioPortal

router = APIRouter(prefix="/galeria", tags=["galeria"])

GALERIA = "dashboards.galeria.visualizar"


class DashboardResumo(BaseModel):
    hash: str
    slug: str  # identificador: pasta src/dashboards/<slug>/ no front
    nome: str
    descricao: str | None
    status: str
    categoria: str
    paginas: int
    responsavel_login: str | None
    atualizado_em: datetime


_SQL_DASHBOARDS = text("""
    SELECT d.hash, d.slug, d.nome, d.descricao, d.status, d.responsavel_login, d.atualizado_em,
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


class PaginaPrevia(BaseModel):
    codigo: str
    nome: str


class DashboardPrevia(BaseModel):
    hash: str
    slug: str
    nome: str
    status: str
    paginas: list[PaginaPrevia]  # só as ativas, na ordem do Gerador


def buscar_para_previa(conexao: Connection, hash_: str) -> DashboardPrevia | None:
    dashboard = conexao.execute(
        text("SELECT id, hash, slug, nome, status FROM unidash.dashboard WHERE hash = :hash"), {"hash": hash_}
    ).mappings().first()
    if dashboard is None:
        return None
    paginas = conexao.execute(
        text("SELECT codigo, nome FROM unidash.pagina WHERE dashboard_id = :id AND ativo ORDER BY ordem, id"),
        {"id": dashboard["id"]},
    ).mappings().all()
    return DashboardPrevia(**{k: v for k, v in dashboard.items() if k != "id"}, paginas=[dict(p) for p in paginas])


@router.get("/dashboards", response_model=list[DashboardResumo])
def dashboards(
    _usuario: Annotated[UsuarioPortal, Depends(exigir(GALERIA))],
    conexao: Annotated[Connection, Depends(obter_conexao)],
) -> list[DashboardResumo]:
    return listar_dashboards(conexao)


@router.get("/dashboards/{hash}", response_model=DashboardPrevia, summary="Dashboard para a pré-visualização")
def dashboard_previa(
    hash: str,
    _usuario: Annotated[UsuarioPortal, Depends(exigir(GALERIA))],
    conexao: Annotated[Connection, Depends(obter_conexao)],
) -> DashboardPrevia:
    dashboard = buscar_para_previa(conexao, hash)
    if dashboard is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dashboard não encontrado.")
    return dashboard
