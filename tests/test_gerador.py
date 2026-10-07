"""Gerador: regras do cadastro e travas das rotas (banco simulado)."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.sessao import obter_conexao
from app.dominios.gerador import servico
from app.dominios.gerador.modelos import DashboardDetalhe, DashboardIn, PaginaIn
from app.dominios.portal import usuarios
from app.main import app
from tests.apoio import ingresso, usuario

AGORA = datetime(2026, 10, 6, tzinfo=timezone.utc)
DETALHE = DashboardDetalhe(
    hash="h" * 32, slug="executivo", nome="Executivo", descricao=None, categoria_id=1, categoria="Gestão", status="rascunho",
    responsavel_login="pessoa@fecaf.com.br", criado_em=AGORA, atualizado_em=AGORA, paginas=[],
)


# ---------------------------------------------------------------- regras sem banco


def _dados(**mudancas):
    base = {"nome": "Executivo", "categoria_id": 1, "status": "rascunho", "paginas": [{"nome": "Visão geral"}]}
    base.update(mudancas)
    return DashboardIn(**base)


@pytest.mark.parametrize("status", ["rascunho", "publicado", "desativado"])
def test_todo_dashboard_precisa_de_pelo_menos_uma_pagina(status):
    with pytest.raises(servico.ErroCadastro) as erro:
        servico.conferir_regras_do_dashboard(_dados(status=status, paginas=[]))
    assert erro.value.status == 422


def test_com_uma_pagina_passa():
    servico.conferir_regras_do_dashboard(_dados(paginas=[PaginaIn(nome="Visão geral")]))


def test_paginas_com_nome_repetido_sao_recusadas():
    paginas = [PaginaIn(nome="Visão geral"), PaginaIn(nome="visão  GERAL")]
    with pytest.raises(servico.ErroCadastro):
        servico.conferir_regras_do_dashboard(_dados(paginas=paginas))


def test_mesma_pagina_duas_vezes_e_recusada():
    paginas = [PaginaIn(codigo="c" * 32, nome="A"), PaginaIn(codigo="c" * 32, nome="B")]
    with pytest.raises(servico.ErroCadastro):
        servico.conferir_regras_do_dashboard(_dados(paginas=paginas))


def test_nomes_sao_limpos():
    assert _dados(nome="  Executivo   2026 ").nome == "Executivo 2026"


# ---------------------------------------------------------------- rotas


@pytest.fixture
def cliente(monkeypatch):
    estado = {"usuario": usuario(), "criado_por": None}
    monkeypatch.setattr(usuarios, "carregar_usuario", lambda _c, _id: estado["usuario"])

    def criar(_conexao, _dados, responsavel):
        estado["criado_por"] = responsavel
        return DETALHE

    monkeypatch.setattr(servico, "criar_dashboard", criar)
    app.dependency_overrides[obter_conexao] = lambda: None
    c = TestClient(app)
    c.estado = estado
    assert c.post("/api/v1/portal/entrar", json={"ingresso": ingresso()}).status_code == 200
    yield c
    app.dependency_overrides.clear()


def test_sem_permissao_do_gerador_nao_grava(cliente):
    # analista_bi: tem a galeria, mas não o gerador
    cliente.estado["usuario"] = usuario(
        perfil="analista_bi", permissoes=frozenset({"hub.dashboards.acessar", "dashboards.galeria.visualizar"})
    )
    assert cliente.post("/api/v1/gerador/dashboards", json=_dados().model_dump()).status_code == 403
    assert cliente.get("/api/v1/gerador/categorias").status_code == 403


def test_criar_registra_o_email_de_quem_criou(cliente):
    resposta = cliente.post("/api/v1/gerador/dashboards", json=_dados().model_dump())
    assert resposta.status_code == 201
    assert resposta.json()["hash"] == "h" * 32
    assert cliente.estado["criado_por"] == "pessoa@fecaf.com.br"


@pytest.mark.parametrize("status_erro", [404, 409, 422])
def test_regra_nao_atendida_vira_a_resposta_certa(cliente, monkeypatch, status_erro):
    def falhar(*_args):
        raise servico.ErroCadastro(status_erro, "mensagem da regra")

    monkeypatch.setattr(servico, "alterar_dashboard", falhar)
    resposta = cliente.put(f"/api/v1/gerador/dashboards/{'h' * 32}", json=_dados().model_dump())
    assert resposta.status_code == status_erro
    assert resposta.json()["detail"] == "mensagem da regra"


def test_nome_vazio_e_recusado_antes_de_chegar_ao_banco(cliente):
    resposta = cliente.post("/api/v1/gerador/dashboards", json=_dados().model_dump() | {"nome": "   "})
    assert resposta.status_code == 422


def test_previa_do_identificador(cliente, monkeypatch):
    monkeypatch.setattr(servico, "proximo_slug", lambda _c, nome: "executivo_financeiro_2")
    resposta = cliente.get("/api/v1/gerador/identificador", params={"nome": "Executivo Financeiro"})
    assert resposta.status_code == 200
    assert resposta.json() == {"slug": "executivo_financeiro_2"}


def test_identificador_so_aceita_tabelas_conhecidas():
    # O nome da tabela entra no SQL: só "dashboard" e "categoria" são aceitas
    with pytest.raises(KeyError):
        servico.proximo_slug(None, "Qualquer", tabela="app.tb_usuarios")
