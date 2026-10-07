"""Rotas do Gerador: só para quem tem `dashboards.gerador.visualizar` (engenharia_dados e admin)."""

import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection

from app.db.sessao import obter_conexao
from app.dominios.gerador import servico
from app.dominios.gerador.modelos import (
    CategoriaAlterarIn,
    CategoriaIn,
    CategoriaOut,
    DashboardDetalhe,
    DashboardIn,
    DashboardResumo,
    IdentificadorOut,
    OrdemCategoriasIn,
)
from app.dominios.portal.dependencias import exigir
from app.dominios.portal.usuarios import UsuarioPortal

logger = logging.getLogger(__name__)

GERADOR = "dashboards.gerador.visualizar"

Usuario = Annotated[UsuarioPortal, Depends(exigir(GERADOR))]
Conexao = Annotated[Connection, Depends(obter_conexao)]

router = APIRouter(prefix="/gerador", tags=["gerador"])


def _executar(funcao: Callable, *args):
    """Roda uma operação do serviço e transforma uma regra não atendida em resposta de erro."""
    try:
        return funcao(*args)
    except servico.ErroCadastro as erro:
        raise HTTPException(erro.status, erro.mensagem) from None


# ---------------------------------------------------------------- categorias


@router.get("/categorias", response_model=list[CategoriaOut], summary="Listar categorias",
            description="Todas as categorias (ativas e desativadas), na ordem, com quantos dashboards não desativados usam cada uma.")
def categorias(_u: Usuario, conexao: Conexao):
    return servico.listar_categorias(conexao)


@router.post("/categorias", response_model=CategoriaOut, status_code=201, summary="Criar categoria",
             description="Cria uma categoria no fim da ordem. 409 se o nome já existir.")
def criar_categoria(dados: CategoriaIn, usuario: Usuario, conexao: Conexao):
    categoria = _executar(servico.criar_categoria, conexao, dados)
    logger.info("Categoria criada: %s (por %s)", categoria.nome, usuario.email)
    return categoria


@router.put("/categorias/{categoria_id}", response_model=CategoriaOut, summary="Alterar categoria",
            description="Renomeia, muda a descrição ou ativa/desativa. Categoria desativada não recebe dashboards novos.")
def alterar_categoria(categoria_id: int, dados: CategoriaAlterarIn, usuario: Usuario, conexao: Conexao):
    categoria = _executar(servico.alterar_categoria, conexao, categoria_id, dados)
    logger.info("Categoria alterada: %s (por %s)", categoria.nome, usuario.email)
    return categoria


@router.put("/categorias-ordem", response_model=list[CategoriaOut], summary="Mudar a ordem das categorias",
            description="Recebe todos os ids das categorias, na nova ordem.")
def ordenar_categorias(dados: OrdemCategoriasIn, _u: Usuario, conexao: Conexao):
    return _executar(servico.ordenar_categorias, conexao, dados.ids)


# ---------------------------------------------------------------- dashboards


@router.get("/dashboards", response_model=list[DashboardResumo], summary="Listar dashboards",
            description="Todos os dashboards, do alterado mais recentemente para o mais antigo.")
def dashboards(_u: Usuario, conexao: Conexao):
    return servico.listar_dashboards(conexao)


@router.get("/identificador", response_model=IdentificadorOut, summary="Prévia do identificador",
            description="Identificador (slug) que um dashboard novo com este nome vai receber: minúsculas, sem acento, "
            "\"_\" no lugar de espaços; com _2, _3... se já existir. Usado na prévia em tempo real do formulário.")
def identificador(nome: str, _u: Usuario, conexao: Conexao):
    return IdentificadorOut(slug=_executar(servico.proximo_slug, conexao, nome))


@router.get("/dashboards/{hash_}", response_model=DashboardDetalhe, summary="Ver um dashboard",
            description="O dashboard com as páginas: ativas primeiro, na ordem; depois as desativadas.")
def dashboard(hash_: str, _u: Usuario, conexao: Conexao):
    return _executar(servico.buscar_dashboard, conexao, hash_)


@router.post("/dashboards", response_model=DashboardDetalhe, status_code=201, summary="Criar dashboard",
             description="Cria o dashboard e as páginas na ordem enviada. O banco gera o hash e os códigos. "
             "Todo dashboard precisa de pelo menos 1 página; nome repetido entre os não desativados dá 409.")
def criar_dashboard(dados: DashboardIn, usuario: Usuario, conexao: Conexao):
    dashboard = _executar(servico.criar_dashboard, conexao, dados, usuario.email)
    logger.info("Dashboard criado: %s [%s] (por %s)", dashboard.nome, dashboard.hash, usuario.email)
    return dashboard


@router.put("/dashboards/{hash_}", response_model=DashboardDetalhe, summary="Alterar dashboard",
            description="Altera dados, status e páginas de uma vez. `paginas` é a lista completa e na ordem final: "
            "com `codigo` = página existente; sem `codigo` = página nova; existente que não veio = desativada.")
def alterar_dashboard(hash_: str, dados: DashboardIn, usuario: Usuario, conexao: Conexao):
    dashboard = _executar(servico.alterar_dashboard, conexao, hash_, dados)
    logger.info("Dashboard alterado: %s [%s] status=%s (por %s)", dashboard.nome, hash_, dashboard.status, usuario.email)
    return dashboard
