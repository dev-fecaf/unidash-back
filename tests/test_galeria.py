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
    hash="a" * 32, nome="Executivo", descricao=None, status="rascunho", categoria="Gestão",
    paginas=2, responsavel_login="leticia.dias", atualizado_em=datetime(2026, 10, 6, tzinfo=timezone.utc),
)


@pytest.fixture
def cliente(monkeypatch):
    estado = {"usuario": usuario()}
    monkeypatch.setattr(usuarios, "carregar_usuario", lambda _c, _id: estado["usuario"])
    monkeypatch.setattr(galeria, "listar_dashboards", lambda _c: [EXEMPLO])
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
