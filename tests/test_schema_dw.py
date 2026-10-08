"""Schema do dashboard no DW: criar ao cadastrar, não mexer no que já existe, não travar o cadastro (DW simulado)."""

import pytest
from fastapi.testclient import TestClient

from app.db.sessao import obter_conexao
from app.dominios.gerador import schema_dw, servico
from app.dominios.portal import usuarios
from app.main import app
from tests.apoio import ingresso, usuario
from tests.test_gerador import DETALHE, _dados


class DwSimulado:
    """Faz o papel do DW: guarda os schemas que existem e os comandos recebidos."""

    def __init__(self, schemas=(), falhar=False):
        self.schemas = set(schemas)
        self.comandos = []
        self.falhar = falhar

    def connect(self):
        if self.falhar:
            raise ConnectionError("DW fora do ar")
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, parametros=None):
        sql = str(sql)
        self.comandos.append(sql)
        if sql.startswith("CREATE SCHEMA"):
            self.schemas.add(sql.split('"')[1])
            return None
        existe = parametros["nome"] in self.schemas
        return type("Resultado", (), {"first": lambda _self: (1,) if existe else None})()

    def commit(self):
        pass


@pytest.fixture
def dw(monkeypatch):
    simulado = DwSimulado(schemas={"financeiro"})
    monkeypatch.setattr(schema_dw, "obter_engine_dw", lambda: simulado)
    return simulado


# ---------------------------------------------------------------- regra


def test_cria_o_schema_com_o_nome_do_identificador(dw):
    assert schema_dw.criar("executivo") == "criado"
    assert 'CREATE SCHEMA "executivo"' in dw.comandos
    assert schema_dw.consultar("executivo") == "existe"


def test_schema_que_ja_existe_nao_e_mexido(dw):
    assert schema_dw.criar("financeiro") == "ja_existia"
    assert not any(c.startswith("CREATE") for c in dw.comandos)


@pytest.mark.parametrize("slug", ["public", "pg_catalog", "fat", "Executivo", "exec-utivo", 'x"; DROP SCHEMA y; --'])
def test_nome_fora_da_regra_nunca_vira_sql(dw, slug):
    assert schema_dw.criar(slug) == "erro"
    assert not any(c.startswith("CREATE") for c in dw.comandos)


def test_dw_desligado_ou_fora_do_ar(monkeypatch):
    monkeypatch.setattr(schema_dw, "obter_engine_dw", lambda: None)
    assert schema_dw.criar("executivo") == "desligado"
    assert schema_dw.consultar("executivo") == "desligado"
    monkeypatch.setattr(schema_dw, "obter_engine_dw", lambda: DwSimulado(falhar=True))
    assert schema_dw.criar("executivo") == "erro"
    assert schema_dw.consultar("executivo") == "erro"


# ---------------------------------------------------------------- rotas


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(usuarios, "carregar_usuario", lambda _c, _id: usuario())
    monkeypatch.setattr(servico, "criar_dashboard", lambda *_a: DETALHE)
    monkeypatch.setattr(servico, "buscar_dashboard", lambda *_a: DETALHE)
    app.dependency_overrides[obter_conexao] = lambda: None
    c = TestClient(app)
    assert c.post("/api/v1/portal/entrar", json={"ingresso": ingresso()}).status_code == 200
    yield c
    app.dependency_overrides.clear()


def test_criar_dashboard_ja_cria_o_schema(cliente, dw):
    resposta = cliente.post("/api/v1/gerador/dashboards", json=_dados().model_dump())
    assert resposta.status_code == 201
    assert resposta.json()["schema_dw"] == {"nome": "executivo", "situacao": "criado"}
    assert "executivo" in dw.schemas


def test_dw_fora_do_ar_nao_impede_o_cadastro(cliente, monkeypatch):
    monkeypatch.setattr(schema_dw, "obter_engine_dw", lambda: DwSimulado(falhar=True))
    resposta = cliente.post("/api/v1/gerador/dashboards", json=_dados().model_dump())
    assert resposta.status_code == 201
    assert resposta.json()["schema_dw"]["situacao"] == "erro"


def test_ver_dashboard_mostra_o_schema_e_criar_agora_cria(cliente, dw, monkeypatch):
    gravados = []
    monkeypatch.setattr(servico, "gravar_schema_dw", lambda _c, hash_, nome: gravados.append(nome))
    caminho = f"/api/v1/gerador/dashboards/{'h' * 32}"
    assert cliente.get(caminho).json()["schema_dw"]["situacao"] == "nao_existe"
    assert cliente.post(f"{caminho}/schema-dw").json() == {"nome": "executivo", "situacao": "criado"}
    assert cliente.get(caminho).json()["schema_dw"]["situacao"] == "existe"
    assert gravados == ["executivo"]  # dashboard antigo (sem schema_dw) passa a apontar para o schema
