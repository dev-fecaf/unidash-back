"""Conexão com o DW do UniData (unidata_dw_hml / unidata_dw_prd).

Separada do banco de aplicação: outro servidor/banco e outro usuário (variáveis DW_*).
Sem DW_HOST, o DW fica desligado e quem usa recebe None.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL

from app.core.config import obter_config


@lru_cache
def obter_engine_dw() -> Engine | None:
    """Cria a conexão com o DW uma única vez. None se o DW não estiver configurado."""
    config = obter_config()
    if not config.dw_host:
        return None
    url = URL.create(
        "postgresql+psycopg",
        username=config.dw_user,
        password=config.dw_password.get_secret_value(),
        host=config.dw_host,
        port=config.dw_port,
        database=config.dw_name,
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "application_name": "unidash"},
    )
