from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.dominios.saude import rotas
from app.main import app


class _BancoSimulado:
    """Imita a conexão com o banco: funciona ou falha, conforme o teste pedir."""

    def __init__(self, funciona: bool):
        self.funciona = funciona

    @contextmanager
    def connect(self):
        if not self.funciona:
            raise OperationalError("SELECT 1", {}, Exception("banco fora do ar"))
        yield self

    def execute(self, _consulta):
        return None


def test_saude_com_banco_ok(monkeypatch):
    monkeypatch.setattr(rotas, "obter_engine", lambda: _BancoSimulado(funciona=True))
    resposta = TestClient(app).get("/api/v1/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "ambiente": "dev", "banco": "ok"}
    assert resposta.headers["X-Trace-Id"]


def test_saude_com_banco_fora(monkeypatch):
    monkeypatch.setattr(rotas, "obter_engine", lambda: _BancoSimulado(funciona=False))
    resposta = TestClient(app).get("/api/v1/saude")
    assert resposta.status_code == 503
    assert resposta.json()["banco"] == "falha"
