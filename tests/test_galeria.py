"""Galeria: só para quem tem a permissão da tela (banco simulado)."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.sessao import obter_conexao
from app.dominios.galeria import rotas as galeria
from app.dominios.portal import usuarios
from app.main import app
from tests.apoio import ingresso, usuario

EXEMPLO = galeria.DashboardResumo(
    hash="a" * 32, slug="executivo", nome="Executivo", descricao=None, status="rascunho", categoria="Gestão",
    paginas=2, responsavel_login="leticia.dias", atualizado_em=datetime(2026, 10, 6, tzinfo=timezone.utc),
)

PREVIA = galeria.DashboardPrevia(
    hash="a" * 32, slug="executivo", nome="Executivo", status="rascunho",
    paginas=[galeria.PaginaPrevia(codigo="c" * 32, nome="Visão geral")],
)


@pytest.fixture
def cliente(monkeypatch):
    estado = {"usuario": usuario()}
    monkeypatch.setattr(usuarios, "carregar_usuario", lambda _c, _id: estado["usuario"])
    monkeypatch.setattr(galeria, "listar_dashboards", lambda _c: [EXEMPLO])
    monkeypatch.setattr(galeria, "buscar_para_previa", lambda _c, h: PREVIA if h == PREVIA.hash else None)
    app.dependency_overrides[obter_conexao] = lambda: None
    c = TestClient(app)
    c.estado = estado
    yield c
    app.dependency_overrides.clear()


def _entrar(cliente):
    assert cliente.post("/api/v1/portal/entrar", json={"ingresso": ingresso()}).status_code == 200


def test_sem_sessao_responde_401(cliente):
    assert cliente.get("/api/v1/galeria/dashboards").status_code == 401


def test_sem_permissao_da_galeria_responde_403(cliente):
    _entrar(cliente)
    cliente.estado["usuario"] = usuario(permissoes=frozenset({"hub.dashboards.acessar"}))
    assert cliente.get("/api/v1/galeria/dashboards").status_code == 403


def test_lista_os_dashboards(cliente):
    _entrar(cliente)
    resposta = cliente.get("/api/v1/galeria/dashboards")
    assert resposta.status_code == 200
    assert resposta.json()[0]["nome"] == "Executivo"
    assert resposta.json()[0]["paginas"] == 2


def test_lista_traz_o_identificador_da_pasta(cliente):
    _entrar(cliente)
    assert cliente.get("/api/v1/galeria/dashboards").json()[0]["slug"] == "executivo"


def test_previa_traz_paginas_do_banco_em_qualquer_status(cliente):
    _entrar(cliente)
    resposta = cliente.get(f"/api/v1/galeria/dashboards/{'a' * 32}")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "rascunho"
    assert [p["nome"] for p in resposta.json()["paginas"]] == ["Visão geral"]
    # DW desligado nos testes: o painel "Onde editar" mostra o nome do schema e a situação
    assert resposta.json()["schema_dw"] == {"nome": "executivo", "situacao": "desligado"}
    assert "schema_nome" not in resposta.json()


def test_previa_de_hash_inexistente_responde_404(cliente):
    _entrar(cliente)
    assert cliente.get(f"/api/v1/galeria/dashboards/{'b' * 32}").status_code == 404


def test_previa_exige_a_permissao_da_galeria(cliente):
    _entrar(cliente)
    cliente.estado["usuario"] = usuario(permissoes=frozenset({"hub.dashboards.acessar"}))
    assert cliente.get(f"/api/v1/galeria/dashboards/{'a' * 32}").status_code == 403
