import pytest

from app.core.config import obter_config


def test_le_as_variaveis():
    config = obter_config()
    assert config.db_host == "banco-de-teste"
    assert config.db_port == 5432


def test_avisa_qual_variavel_falta(monkeypatch):
    monkeypatch.delenv("DB_HOST")
    with pytest.raises(RuntimeError, match="DB_HOST"):
        obter_config()


def test_senha_nao_aparece_ao_imprimir_a_config():
    assert "teste" not in repr(obter_config().db_password)
