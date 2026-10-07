"""Análises (aba Atenção): permissão e montagem da resposta (banco simulado)."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.sessao import obter_conexao
from app.dominios.analises import rotas as analises
from app.dominios.portal import usuarios
from app.main import app
from tests.apoio import ingresso, usuario

AGORA = datetime(2026, 10, 6, tzinfo=timezone.utc)


class _Resultado:
    def __init__(self, linhas):
        self._linhas = linhas

    def mappings(self):
        return iter(self._linhas)


class _ConexaoSimulada:
    """Responde as 4 consultas da aba Atenção, na ordem em que são feitas."""

    def __init__(self):
        self.parametros = []
        self._respostas = [
            [{"hash": "r" * 32, "nome": "Rascunho velho", "categoria": "Gestão", "responsavel_login": "ana",
              "atualizado_em": AGORA, "dias_parado": 20}],
            [{"hash": "p" * 32, "nome": "Esquecido", "categoria": "Gestão", "ultimo_acesso": None}],
            [{"hash": "p" * 32, "nome": "Esquecido", "categoria": "Gestão", "status": "publicado"}],
            [{"hash": "p" * 32, "nome": "Esquecido", "categoria": "Gestão", "status": "publicado",
              "responsavel_login": "ana", "criado_em": AGORA, "atualizado_em": AGORA}],
        ]

    def execute(self, _sql, parametros):
        self.parametros.append(parametros)
        return _Resultado(self._respostas.pop(0))


@pytest.fixture
def cliente(monkeypatch):
    estado = {"usuario": usuario()}
    monkeypatch.setattr(usuarios, "carregar_usuario", lambda _c, _id: estado["usuario"])
    app.dependency_overrides[obter_conexao] = _ConexaoSimulada
    c = TestClient(app)
    c.estado = estado
    assert c.post("/api/v1/portal/entrar", json={"ingresso": ingresso()}).status_code == 200
    yield c
    app.dependency_overrides.clear()


def test_sem_permissao_de_analises_responde_403(cliente):
    cliente.estado["usuario"] = usuario(permissoes=frozenset({"hub.dashboards.acessar"}))
    assert cliente.get("/api/v1/analises/atencao").status_code == 403


def test_atencao_traz_as_listas_e_as_regras(cliente):
    corpo = cliente.get("/api/v1/analises/atencao").json()
    assert corpo["dias_rascunho_parado"] == 14 and corpo["dias_sem_acesso"] == 30
    assert corpo["rascunhos_parados"][0]["dias_parado"] == 20
    assert corpo["publicados_sem_acesso"][0]["ultimo_acesso"] is None
    assert len(corpo["cadastrados"]) == 1 and len(corpo["recentes"]) == 1


def test_consultas_recebem_os_limites_certos():
    conexao = _ConexaoSimulada()
    analises.calcular_atencao(conexao)
    assert conexao.parametros == [{"dias": 14}, {"dias": 30}, {}, {"limite": 8}]
