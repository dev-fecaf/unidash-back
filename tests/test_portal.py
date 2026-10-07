"""Entrada pelo portal: ingresso, sessão e permissões (banco simulado)."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.db.sessao import obter_conexao
from app.dominios.portal import usuarios
from app.dominios.portal.dependencias import COOKIE_SESSAO
from app.dominios.portal.usuarios import ACESSAR
from app.main import app
from tests.apoio import USU_ID
from tests.apoio import ingresso as _ingresso
from tests.apoio import usuario as _usuario


@pytest.fixture
def cliente(monkeypatch):
    """Cliente com o banco simulado: carregar_usuario devolve o usuário que o teste definir."""
    estado = {"usuario": _usuario()}
    monkeypatch.setattr(usuarios, "carregar_usuario", lambda _conexao, _usu_id: estado["usuario"])
    app.dependency_overrides[obter_conexao] = lambda: None
    c = TestClient(app)
    c.estado = estado
    yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------- entrar


def test_ingresso_valido_abre_a_sessao(cliente):
    resposta = cliente.post("/api/v1/portal/entrar", json={"ingresso": _ingresso()})
    assert resposta.status_code == 200
    assert resposta.json()["email"] == "pessoa@fecaf.com.br"
    cookie = resposta.headers["set-cookie"]
    assert COOKIE_SESSAO in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie


@pytest.mark.parametrize(
    "ingresso",
    [
        _ingresso(segredo="outro-segredo-qualquer-com-mais-de-32-caracteres"),  # assinatura falsa
        _ingresso(validade=-30),  # vencido
        _ingresso(validade=600),  # validade maior que 60 s
        _ingresso(aud="outro-sistema"),  # feito para outro sistema
        _ingresso(sub="nao-e-um-uuid"),
        "isto-nao-e-um-token",
    ],
    ids=["assinatura", "vencido", "validade-longa", "aud", "sub", "lixo"],
)
def test_ingresso_invalido_e_recusado_com_mensagem_neutra(cliente, ingresso):
    resposta = cliente.post("/api/v1/portal/entrar", json={"ingresso": ingresso})
    assert resposta.status_code == 401
    assert "Volte ao portal" in resposta.json()["detail"]
    assert "set-cookie" not in resposta.headers


def test_ingresso_com_outro_algoritmo_e_recusado(cliente):
    # "none" = token sem assinatura; precisa ser recusado mesmo com o resto certo
    agora = datetime.now(timezone.utc)
    sem_assinatura = jwt.encode(
        {"sub": str(USU_ID), "aud": "unidash", "iat": agora, "exp": agora + timedelta(seconds=60), "jti": "x"},
        key=None, algorithm="none",
    )
    assert cliente.post("/api/v1/portal/entrar", json={"ingresso": sem_assinatura}).status_code == 401


def test_ingresso_so_pode_ser_usado_uma_vez(cliente):
    ingresso = _ingresso()
    assert cliente.post("/api/v1/portal/entrar", json={"ingresso": ingresso}).status_code == 200
    assert cliente.post("/api/v1/portal/entrar", json={"ingresso": ingresso}).status_code == 401


def test_usuario_inativo_nao_entra(cliente):
    cliente.estado["usuario"] = _usuario(ativo=False)
    assert cliente.post("/api/v1/portal/entrar", json={"ingresso": _ingresso()}).status_code == 401


def test_usuario_inexistente_nao_entra(cliente):
    cliente.estado["usuario"] = None
    assert cliente.post("/api/v1/portal/entrar", json={"ingresso": _ingresso()}).status_code == 401


def test_sem_permissao_do_modulo_nao_entra(cliente):
    cliente.estado["usuario"] = _usuario(permissoes=frozenset({"dashboards.galeria.visualizar"}))
    resposta = cliente.post("/api/v1/portal/entrar", json={"ingresso": _ingresso()})
    assert resposta.status_code == 403


def test_senha_temporaria_pede_troca_no_portal(cliente):
    cliente.estado["usuario"] = _usuario(deve_trocar_senha=True)
    resposta = cliente.post("/api/v1/portal/entrar", json={"ingresso": _ingresso()})
    assert resposta.status_code == 403
    assert "senha" in resposta.json()["detail"]


def test_sem_segredo_configurado_responde_indisponivel(cliente, monkeypatch):
    from app.core.config import obter_config

    monkeypatch.setenv("PORTAL_INGRESSO_SECRET", "")
    obter_config.cache_clear()
    assert cliente.post("/api/v1/portal/entrar", json={"ingresso": _ingresso()}).status_code == 503


# ---------------------------------------------------------------- sessão


def test_eu_sem_sessao_responde_401(cliente):
    assert cliente.get("/api/v1/portal/eu").status_code == 401


def test_eu_com_sessao_mostra_a_pessoa_e_as_permissoes(cliente):
    cliente.post("/api/v1/portal/entrar", json={"ingresso": _ingresso()})
    resposta = cliente.get("/api/v1/portal/eu")
    assert resposta.status_code == 200
    assert ACESSAR in resposta.json()["permissoes"]


def test_permissao_retirada_vale_na_hora(cliente):
    cliente.post("/api/v1/portal/entrar", json={"ingresso": _ingresso()})
    # o admin tirou o acesso no UniData depois da entrada
    cliente.estado["usuario"] = _usuario(permissoes=frozenset())
    assert cliente.get("/api/v1/portal/eu").status_code == 403


def test_sessao_falsificada_e_recusada(cliente):
    cliente.cookies.set(COOKIE_SESSAO, _ingresso(segredo="qualquer-outro-segredo-com-mais-de-32-letras"), path="/api")
    assert cliente.get("/api/v1/portal/eu").status_code == 401


def test_sair_apaga_a_sessao(cliente):
    cliente.post("/api/v1/portal/entrar", json={"ingresso": _ingresso()})
    resposta = cliente.post("/api/v1/portal/sair")
    assert resposta.status_code == 204
    assert COOKIE_SESSAO in resposta.headers["set-cookie"]
    assert cliente.get("/api/v1/portal/eu").status_code == 401
