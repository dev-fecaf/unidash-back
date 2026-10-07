"""Início: permissões, período e montagem dos rankings (banco simulado)."""

import pytest
from fastapi.testclient import TestClient

from app.db.sessao import obter_conexao
from app.dominios.inicio import rotas as inicio
from app.dominios.portal import usuarios
from app.main import app
from tests.apoio import ingresso, usuario


class _ResultadoSimulado:
    def __init__(self, linhas):
        self._linhas = linhas

    def mappings(self):
        return self

    def one(self):
        return self._linhas[0]

    def __iter__(self):
        return iter(self._linhas)


class _ConexaoSimulada:
    """Devolve os totais na primeira consulta e a lista por dashboard na segunda."""

    def __init__(self, totais, por_dashboard):
        self._respostas = [[totais], por_dashboard]
        self.parametros = []

    def execute(self, _sql, parametros):
        self.parametros.append(parametros)
        return _ResultadoSimulado(self._respostas.pop(0))


def _dash(nome, acessos):
    return {"hash": nome.lower() * 4, "nome": nome, "categoria": "Gestão", "acessos": acessos}


TOTAIS = {"acessos": 10, "acessos_periodo_anterior": 8, "pessoas": 4, "publicados": 7, "ja_houve_acesso": True}
POR_DASHBOARD = [  # já em ordem decrescente de acessos, como o SQL devolve
    _dash("A", 5), _dash("B", 3), _dash("C", 2), _dash("D", 0), _dash("E", 0), _dash("F", 0), _dash("G", 0),
]


@pytest.fixture
def cliente(monkeypatch):
    estado = {"usuario": usuario()}
    monkeypatch.setattr(usuarios, "carregar_usuario", lambda _c, _id: estado["usuario"])
    app.dependency_overrides[obter_conexao] = lambda: _ConexaoSimulada(TOTAIS, list(POR_DASHBOARD))
    c = TestClient(app)
    c.estado = estado
    assert c.post("/api/v1/portal/entrar", json={"ingresso": ingresso()}).status_code == 200
    yield c
    app.dependency_overrides.clear()


def test_sem_permissao_do_inicio_responde_403(cliente):
    cliente.estado["usuario"] = usuario(permissoes=frozenset({"hub.dashboards.acessar"}))
    assert cliente.get("/api/v1/inicio/resumo").status_code == 403


def test_periodo_padrao_e_30_dias(cliente):
    assert cliente.get("/api/v1/inicio/resumo").json()["periodo_dias"] == 30


@pytest.mark.parametrize("dias", [7, 30, 90])
def test_periodos_validos_escritos_no_endereco(cliente, dias):
    # O período chega como texto no endereço; precisa ser aceito (erro real de 06/10/2026)
    resposta = cliente.get(f"/api/v1/inicio/resumo?dias={dias}")
    assert resposta.status_code == 200
    assert resposta.json()["periodo_dias"] == dias


def test_periodo_fora_das_opcoes_e_recusado(cliente):
    assert cliente.get("/api/v1/inicio/resumo?dias=15").status_code == 422


def test_rankings_e_totais():
    corpo = inicio.calcular_resumo(_ConexaoSimulada(TOTAIS, list(POR_DASHBOARD)), 30)
    assert [d.nome for d in corpo.mais_acessados] == ["A", "B", "C"]  # só quem teve acesso
    assert [d.nome for d in corpo.menos_acessados] == ["G", "F", "E", "D"]  # sem repetir os mais acessados
    assert corpo.publicados_sem_acesso == 4
    assert corpo.acessos == 10 and corpo.pessoas == 4


def test_informa_se_ja_houve_acesso_em_qualquer_data():
    # Período vazio, mas já houve acessos antes: a tela mostra "nenhum acesso no período"
    totais = {**TOTAIS, "acessos": 0, "ja_houve_acesso": True}
    assert inicio.calcular_resumo(_ConexaoSimulada(totais, []), 7).ja_houve_acesso is True
    # Nunca houve acesso: a tela explica que os números aparecem depois do primeiro acesso
    totais = {**TOTAIS, "acessos": 0, "ja_houve_acesso": False}
    assert inicio.calcular_resumo(_ConexaoSimulada(totais, []), 7).ja_houve_acesso is False


def test_ranking_limita_a_5():
    muitos = [_dash(f"X{i}", 100 - i) for i in range(12)]
    corpo = inicio.calcular_resumo(_ConexaoSimulada(TOTAIS, muitos), 7)
    assert len(corpo.mais_acessados) == 5
    assert len(corpo.menos_acessados) == 5
    assert corpo.menos_acessados[0].nome == "X11"
