"""Conexão com o banco de aplicação (unidata_hml / unidata_prd)."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.engine import URL

from app.core.config import obter_config


@lru_cache
def obter_engine() -> Engine:
    """Cria a conexão com o banco uma única vez e a reaproveita.

    A conexão é montada a partir das cinco variáveis DB_*, nunca de uma DATABASE_URL.
    """
    config = obter_config()
    url = URL.create(
        "postgresql+psycopg",
        username=config.db_user,
        password=config.db_password.get_secret_value(),
        host=config.db_host,
        port=config.db_port,
        database=config.db_name,
    )
    return create_engine(
        url,
        pool_pre_ping=True,  # testa a conexão antes de usar (o servidor pode tê-la fechado)
        connect_args={"connect_timeout": 5, "application_name": "unidash"},
    )


def obter_conexao() -> Iterator[Connection]:
    """Dependência das rotas: uma conexão por pedido, devolvida ao final."""
    with obter_engine().connect() as conexao:
        yield conexao
