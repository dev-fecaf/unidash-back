"""Análises: o que precisa de atenção, uso e desempenho dos dashboards.

Exige a permissão `dashboards.uso.visualizar` (a antiga tela "Uso").
Por enquanto: a aba Atenção. As abas Uso e Desempenho entram nos próximos passos.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Connection, text

from app.db.sessao import obter_conexao
from app.dominios.portal.dependencias import exigir
from app.dominios.portal.usuarios import UsuarioPortal

router = APIRouter(prefix="/analises", tags=["análises"])

ANALISES = "dashboards.uso.visualizar"

# Regras da aba Atenção (aparecem na tela, para quem lê saber o critério)
DIAS_RASCUNHO_PARADO = 14  # rascunho sem nenhuma alteração há esse tempo
DIAS_SEM_ACESSO = 30  # publicado sem acesso pelo Hub há esse tempo (e cadastrado há mais tempo que isso)
TAMANHO_RECENTES = 8


class DashboardBasico(BaseModel):
    hash: str
    nome: str
    categoria: str
    status: str


class RascunhoParado(BaseModel):
    hash: str
    nome: str
    categoria: str
    responsavel_login: str | None
    atualizado_em: datetime
    dias_parado: int


class PublicadoSemAcesso(BaseModel):
    hash: str
    nome: str
    categoria: str
    ultimo_acesso: datetime | None  # None = nunca acessado pelo Hub


class AlteracaoRecente(BaseModel):
    hash: str
    nome: str
    categoria: str
    status: str
    responsavel_login: str | None
    criado_em: datetime
    atualizado_em: datetime


class Atencao(BaseModel):
    dias_rascunho_parado: int
    dias_sem_acesso: int
    rascunhos_parados: list[RascunhoParado]
    publicados_sem_acesso: list[PublicadoSemAcesso]
    # Cadastrados (não desativados): o front confere quais ainda não têm configuração no código
    cadastrados: list[DashboardBasico]
    recentes: list[AlteracaoRecente]


_SQL_RASCUNHOS_PARADOS = text("""
    SELECT d.hash, d.nome, c.nome AS categoria, d.responsavel_login, d.atualizado_em,
           (current_date - d.atualizado_em::date) AS dias_parado
    FROM unidash.dashboard d
    JOIN unidash.categoria c ON c.id = d.categoria_id
    WHERE d.status = 'rascunho'
      AND d.atualizado_em < now() - make_interval(days => :dias)
    ORDER BY d.atualizado_em
""")

_SQL_PUBLICADOS_SEM_ACESSO = text("""
    SELECT d.hash, d.nome, c.nome AS categoria, max(a.acessado_em) AS ultimo_acesso
    FROM unidash.dashboard d
    JOIN unidash.categoria c ON c.id = d.categoria_id
    LEFT JOIN unidash.acesso a ON a.dashboard_id = d.id AND a.origem = 'hub'
    WHERE d.status = 'publicado'
      AND d.criado_em < now() - make_interval(days => :dias)
    GROUP BY d.id, c.id
    HAVING max(a.acessado_em) IS NULL OR max(a.acessado_em) < now() - make_interval(days => :dias)
    ORDER BY max(a.acessado_em) NULLS FIRST, d.nome
""")

_SQL_CADASTRADOS = text("""
    SELECT d.hash, d.nome, c.nome AS categoria, d.status
    FROM unidash.dashboard d
    JOIN unidash.categoria c ON c.id = d.categoria_id
    WHERE d.status <> 'desativado'
    ORDER BY d.nome
""")

_SQL_RECENTES = text("""
    SELECT d.hash, d.nome, c.nome AS categoria, d.status, d.responsavel_login, d.criado_em, d.atualizado_em
    FROM unidash.dashboard d
    JOIN unidash.categoria c ON c.id = d.categoria_id
    ORDER BY d.atualizado_em DESC
    LIMIT :limite
""")


def calcular_atencao(conexao: Connection) -> Atencao:
    def linhas(sql, **parametros):
        return conexao.execute(sql, parametros).mappings()

    return Atencao(
        dias_rascunho_parado=DIAS_RASCUNHO_PARADO,
        dias_sem_acesso=DIAS_SEM_ACESSO,
        rascunhos_parados=[RascunhoParado(**l) for l in linhas(_SQL_RASCUNHOS_PARADOS, dias=DIAS_RASCUNHO_PARADO)],
        publicados_sem_acesso=[
            PublicadoSemAcesso(**l) for l in linhas(_SQL_PUBLICADOS_SEM_ACESSO, dias=DIAS_SEM_ACESSO)
        ],
        cadastrados=[DashboardBasico(**l) for l in linhas(_SQL_CADASTRADOS)],
        recentes=[AlteracaoRecente(**l) for l in linhas(_SQL_RECENTES, limite=TAMANHO_RECENTES)],
    )


@router.get("/atencao", response_model=Atencao)
def atencao(
    _usuario: Annotated[UsuarioPortal, Depends(exigir(ANALISES))],
    conexao: Annotated[Connection, Depends(obter_conexao)],
) -> Atencao:
    return calcular_atencao(conexao)
