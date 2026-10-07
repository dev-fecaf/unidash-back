"""Início: indicadores de acesso aos dashboards (só acessos vindos do Hub).

Regra de contagem (decidida): 1 acesso por pessoa, por dashboard, a cada 30 minutos.
Na prática: um registro de `unidash.acesso` só conta se a mesma pessoa não abriu o mesmo
dashboard nos 30 minutos anteriores. Assim, recarregar a página ou trocar de aba não infla o número.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Connection, text

from app.db.sessao import obter_conexao
from app.dominios.portal.dependencias import exigir
from app.dominios.portal.usuarios import UsuarioPortal

router = APIRouter(prefix="/inicio", tags=["início"])

INICIO = "dashboards.visao-geral.visualizar"
TAMANHO_RANKING = 5
PERIODOS = (7, 30, 90)

# Acessos do Hub dos dois últimos períodos (atual + anterior, para comparar), já com a regra
# dos 30 minutos aplicada. "atual" = dentro do período escolhido.
_ACESSOS_CONTADOS = """
    WITH base AS (
        SELECT dashboard_id, usuario_login, acessado_em,
               lag(acessado_em) OVER (
                   PARTITION BY usuario_login, dashboard_id ORDER BY acessado_em
               ) AS anterior
        FROM unidash.acesso
        WHERE origem = 'hub'
          AND acessado_em >= now() - make_interval(days => :dias * 2)
    ),
    contados AS (
        SELECT dashboard_id, usuario_login,
               acessado_em >= now() - make_interval(days => :dias) AS atual
        FROM base
        WHERE anterior IS NULL OR acessado_em - anterior > interval '30 minutes'
    )
"""

_SQL_TOTAIS = text(_ACESSOS_CONTADOS + """
    SELECT
        count(*) FILTER (WHERE atual) AS acessos,
        count(*) FILTER (WHERE NOT atual) AS acessos_periodo_anterior,
        count(DISTINCT usuario_login) FILTER (WHERE atual) AS pessoas,
        (SELECT count(*) FROM unidash.dashboard WHERE status = 'publicado') AS publicados,
        -- Já existiu algum acesso pelo Hub, em qualquer data? (muda o aviso da tela)
        EXISTS (SELECT 1 FROM unidash.acesso WHERE origem = 'hub') AS ja_houve_acesso
    FROM contados
""")

_SQL_POR_DASHBOARD = text(_ACESSOS_CONTADOS + """
    SELECT d.hash, d.nome, c.nome AS categoria,
           count(x.dashboard_id) AS acessos
    FROM unidash.dashboard d
    JOIN unidash.categoria c ON c.id = d.categoria_id
    LEFT JOIN contados x ON x.dashboard_id = d.id AND x.atual
    WHERE d.status = 'publicado'
    GROUP BY d.id, c.id
    ORDER BY acessos DESC, d.nome
""")


class DashboardAcessos(BaseModel):
    hash: str
    nome: str
    categoria: str
    acessos: int


class ResumoInicio(BaseModel):
    periodo_dias: int
    ja_houve_acesso: bool
    acessos: int
    acessos_periodo_anterior: int
    pessoas: int
    publicados: int
    publicados_sem_acesso: int
    mais_acessados: list[DashboardAcessos]
    menos_acessados: list[DashboardAcessos]


def calcular_resumo(conexao: Connection, dias: int) -> ResumoInicio:
    totais = conexao.execute(_SQL_TOTAIS, {"dias": dias}).mappings().one()
    por_dashboard = [
        DashboardAcessos(**linha) for linha in conexao.execute(_SQL_POR_DASHBOARD, {"dias": dias}).mappings()
    ]

    mais = [d for d in por_dashboard if d.acessos > 0][:TAMANHO_RANKING]
    # Menos acessados: do fim para o começo, sem repetir quem já está entre os mais acessados
    ja_listados = {d.hash for d in mais}
    menos = [d for d in reversed(por_dashboard) if d.hash not in ja_listados][:TAMANHO_RANKING]

    return ResumoInicio(
        periodo_dias=dias,
        ja_houve_acesso=totais["ja_houve_acesso"],
        acessos=totais["acessos"],
        acessos_periodo_anterior=totais["acessos_periodo_anterior"],
        pessoas=totais["pessoas"],
        publicados=totais["publicados"],
        publicados_sem_acesso=sum(1 for d in por_dashboard if d.acessos == 0),
        mais_acessados=mais,
        menos_acessados=menos,
    )


@router.get("/resumo", response_model=ResumoInicio)
def resumo(
    _usuario: Annotated[UsuarioPortal, Depends(exigir(INICIO))],
    conexao: Annotated[Connection, Depends(obter_conexao)],
    dias: Annotated[int, Query(description="Período em dias: 7, 30 ou 90")] = 30,
) -> ResumoInicio:
    # O número chega como texto no endereço (?dias=30); o FastAPI converte para int,
    # e aqui conferimos se é um dos períodos permitidos.
    if dias not in PERIODOS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "O período precisa ser 7, 30 ou 90 dias.")
    return calcular_resumo(conexao, dias)
