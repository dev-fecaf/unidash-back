"""Preparação comum dos testes.

Os testes nunca usam o banco de verdade nem o seu .env: cada teste roda numa pasta
temporária, com variáveis de mentira, e o banco é simulado quando preciso.
"""

import pytest

from app.core.config import obter_config
from app.db.dw import obter_engine_dw
from app.db.sessao import obter_engine
from app.dominios.embed.tokens import uso_unico_hub
from app.dominios.portal.tokens import uso_unico

VARIAVEIS_DE_TESTE = {
    "AMBIENTE": "dev",
    "DB_HOST": "banco-de-teste",
    "DB_PORT": "5432",
    "DB_NAME": "teste",
    "DB_USER": "teste",
    "DB_PASSWORD": "teste",
    "PORTAL_INGRESSO_SECRET": "segredo-do-ingresso-de-teste-com-32-caracteres",
    "SESSAO_SECRET": "segredo-da-sessao-de-teste-com-pelo-menos-32-caracteres",
    "EMBED_HUB_SECRET": "segredo-do-hub-de-teste-com-pelo-menos-32-caracteres",
    "EMBED_HUB_ORIGIN": "https://hub.teste",
    "DW_HOST": "",  # DW desligado; os testes do schema simulam o DW
}


@pytest.fixture(autouse=True)
def ambiente_isolado(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # pasta sem .env: o .env real nunca é lido
    for nome, valor in VARIAVEIS_DE_TESTE.items():
        monkeypatch.setenv(nome, valor)
    obter_config.cache_clear()
    obter_engine.cache_clear()
    obter_engine_dw.cache_clear()
    uso_unico.limpar()
    uso_unico_hub.limpar()
    yield
    obter_config.cache_clear()
    obter_engine.cache_clear()
    obter_engine_dw.cache_clear()
