"""Confere o padrão de erros (RFC 9457) com uma aplicação pequena, só para teste."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.erros import registrar_tratadores_de_erro
from app.core.rastreio import MiddlewareRastreio


def _cliente() -> TestClient:
    app = FastAPI()
    app.add_middleware(MiddlewareRastreio)
    registrar_tratadores_de_erro(app)

    @app.get("/quebra")
    def quebra():
        raise ValueError("detalhe interno que não pode vazar")

    @app.get("/numero/{valor}")
    def numero(valor: int):
        return {"valor": valor}

    # raise_server_exceptions=False: o teste recebe a resposta 500, como um navegador receberia
    return TestClient(app, raise_server_exceptions=False)


def test_rota_inexistente_volta_404_no_padrao():
    resposta = _cliente().get("/nao-existe")
    assert resposta.status_code == 404
    assert resposta.headers["content-type"] == "application/problem+json"
    corpo = resposta.json()
    assert corpo["title"] == "Não encontrado"
    assert corpo["status"] == 404
    assert corpo["trace_id"] == resposta.headers["X-Trace-Id"]


def test_dado_invalido_volta_422_dizendo_o_campo():
    resposta = _cliente().get("/numero/abc")
    assert resposta.status_code == 422
    corpo = resposta.json()
    assert corpo["title"] == "Dados inválidos"
    assert corpo["erros"][0]["campo"] == "path.valor"


def test_erro_inesperado_volta_500_sem_vazar_detalhe():
    resposta = _cliente().get("/quebra")
    assert resposta.status_code == 500
    corpo = resposta.json()
    assert corpo["title"] == "Erro interno"
    assert "detalhe interno" not in resposta.text
    assert corpo["trace_id"]


def test_cada_pedido_ganha_um_trace_id_diferente():
    cliente = _cliente()
    primeiro = cliente.get("/nao-existe").json()["trace_id"]
    segundo = cliente.get("/nao-existe").json()["trace_id"]
    assert primeiro != segundo
