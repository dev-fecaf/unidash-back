"""Embed (dashboard aberto pelo Hub): token, status, páginas liberadas e sessão (banco simulado)."""

import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from app.db.sessao import obter_conexao
from app.dominios.embed import servico
from app.main import app

SEGREDO_HUB = "segredo-do-hub-de-teste-com-pelo-menos-32-caracteres"  # igual ao conftest
HASH = "a" * 32
OUTRO_HASH = "b" * 32
PAGINAS = [{"codigo": "p1" * 16, "nome": "Visão geral"}, {"codigo": "p2" * 16, "nome": "Financeiro"}]


def token_hub(segredo=SEGREDO_HUB, dash=HASH, validade=60, algoritmo="HS256", sem=(), **extras):
    dados = {
        "dash": dash, "sub": "pessoa.teste", "name": "Pessoa Teste", "email": "pessoa@fecaf.com.br",
        "setores": ["Financeiro", "Secretaria"], "exp": int(time.time()) + validade, "jti": uuid.uuid4().hex, **extras,
    }
    for campo in sem:
        dados.pop(campo)
    return jwt.encode(dados, segredo, algorithm=algoritmo)


@pytest.fixture
def cliente(monkeypatch):
    estado = {"status": "publicado", "existe": True, "acessos": []}

    def buscar(_conexao, hash_):
        if not estado["existe"]:
            return None
        return {"id": 7, "hash": hash_, "nome": "Executivo", "status": estado["status"], "paginas": PAGINAS}

    monkeypatch.setattr(servico, "buscar_dashboard", buscar)
    monkeypatch.setattr(servico, "registrar_acesso", lambda _c, dash_id, pessoa: estado["acessos"].append((dash_id, pessoa)))
    app.dependency_overrides[obter_conexao] = lambda: None
    c = TestClient(app)
    c.estado = estado
    yield c
    app.dependency_overrides.clear()


def entrar(cliente, token, hash_=HASH):
    return cliente.post("/api/v1/embed/entrar", json={"hash": hash_, "token": token})


# ---------------------------------------------------------------- token


def test_token_valido_libera_e_grava_o_acesso_com_setores(cliente):
    resposta = entrar(cliente, token_hub())
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["situacao"] == "liberado"
    assert corpo["expira_em_segundos"] == 30 * 60
    assert [p["nome"] for p in corpo["dashboard"]["paginas"]] == ["Visão geral", "Financeiro"]
    (dash_id, pessoa), = cliente.estado["acessos"]
    assert dash_id == 7 and pessoa.login == "pessoa.teste" and pessoa.setores == ["Financeiro", "Secretaria"]


@pytest.mark.parametrize(
    "extras, esperado",
    [
        ({"sem": ("setores", "email")}, None),  # o Hub ainda não tem e-mail; setores é opcional
        ({"setores": "Financeiro"}, ["Financeiro"]),  # um texto só também serve
        ({"setores": [" Financeiro ", "Financeiro", "", 3]}, ["Financeiro"]),  # limpa, sem repetir
        ({"setores": {"x": 1}}, None),  # fora do formato: ignora, não bloqueia
    ],
)
def test_setores_opcionais_e_limpos(cliente, extras, esperado):
    assert entrar(cliente, token_hub(**extras)).json()["situacao"] == "liberado"
    assert cliente.estado["acessos"][0][1].setores == esperado


@pytest.mark.parametrize(
    "token",
    [
        token_hub(segredo="outro-segredo-qualquer-com-mais-de-32-caracteres"),  # assinatura errada
        token_hub(validade=-30),  # vencido
        token_hub(validade=600),  # validade maior que 60 s
        token_hub(dash=OUTRO_HASH),  # token de outro dashboard
        token_hub(sem=("jti",)),  # sem id único
        token_hub(algoritmo="HS512"),  # só HS256
        token_hub(paginas="p1"),  # paginas fora do formato
        "isto-nao-e-um-token",
    ],
)
def test_token_invalido_recebe_mensagem_neutra(cliente, token):
    resposta = entrar(cliente, token)
    assert resposta.status_code == 401
    assert resposta.json()["detail"].startswith("Não foi possível validar o acesso")
    assert cliente.estado["acessos"] == []


def test_token_nao_pode_ser_usado_duas_vezes(cliente):
    token = token_hub()
    assert entrar(cliente, token).status_code == 200
    assert entrar(cliente, token).status_code == 401


def test_sem_segredo_configurado_responde_indisponivel(cliente, monkeypatch):
    from app.core.config import obter_config

    monkeypatch.setenv("EMBED_HUB_SECRET", "")
    obter_config.cache_clear()
    assert entrar(cliente, token_hub()).status_code == 503


# ---------------------------------------------------------------- status do dashboard


@pytest.mark.parametrize(
    "status, situacao", [("rascunho", "em_construcao"), ("desativado", "indisponivel")]
)
def test_so_publicado_abre_e_os_outros_nao_gravam_acesso(cliente, status, situacao):
    cliente.estado["status"] = status
    corpo = entrar(cliente, token_hub()).json()
    assert corpo == {"situacao": situacao, "sessao": None, "expira_em_segundos": None, "dashboard": None}
    assert cliente.estado["acessos"] == []


def test_hash_inexistente_responde_indisponivel(cliente):
    cliente.estado["existe"] = False
    assert entrar(cliente, token_hub()).json()["situacao"] == "indisponivel"


# ---------------------------------------------------------------- páginas liberadas


def test_hub_libera_so_algumas_paginas(cliente):
    corpo = entrar(cliente, token_hub(paginas=[PAGINAS[1]["codigo"], "codigo-que-nao-existe"])).json()
    assert [p["nome"] for p in corpo["dashboard"]["paginas"]] == ["Financeiro"]


@pytest.mark.parametrize("paginas", [[], ["codigo-que-nao-existe"]])
def test_nenhuma_pagina_liberada(cliente, paginas):
    assert entrar(cliente, token_hub(paginas=paginas)).json()["situacao"] == "sem_paginas"
    assert cliente.estado["acessos"] == []


# ---------------------------------------------------------------- sessão


def _sessao(cliente, **extras):
    return entrar(cliente, token_hub(**extras)).json()["sessao"]


def test_sessao_libera_a_pagina_e_o_back_recusa_a_nao_liberada(cliente):
    sessao = _sessao(cliente, paginas=[PAGINAS[0]["codigo"]])
    cabecalho = {"Authorization": f"Bearer {sessao}"}
    liberada = cliente.get(f"/api/v1/embed/{HASH}/paginas/{PAGINAS[0]['codigo']}", headers=cabecalho)
    bloqueada = cliente.get(f"/api/v1/embed/{HASH}/paginas/{PAGINAS[1]['codigo']}", headers=cabecalho)
    assert liberada.status_code == 200
    assert bloqueada.status_code == 403


def test_sessao_de_um_dashboard_nao_vale_em_outro(cliente):
    sessao = _sessao(cliente)
    resposta = cliente.get(
        f"/api/v1/embed/{OUTRO_HASH}/paginas/{PAGINAS[0]['codigo']}", headers={"Authorization": f"Bearer {sessao}"}
    )
    assert resposta.status_code == 401


@pytest.mark.parametrize("cabecalho", [None, "Bearer invalida", "Basic abc"])
def test_sem_sessao_valida_nao_entra(cliente, cabecalho):
    headers = {"Authorization": cabecalho} if cabecalho else {}
    assert cliente.get(f"/api/v1/embed/{HASH}/paginas/{PAGINAS[0]['codigo']}", headers=headers).status_code == 401
