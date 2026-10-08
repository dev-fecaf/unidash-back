"""Configuração do UniDash.

Lê as variáveis do arquivo .env (no computador) ou do painel do app (no CapRover).
Se faltar alguma variável obrigatória, o back não liga e avisa qual é.
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # dev (computador), hml (homologação) ou prd (produção)
    ambiente: Literal["dev", "hml", "prd"] = "dev"

    # Banco de aplicação (schema unidash). Cada campo lê a variável de mesmo nome
    # em maiúsculas: db_host <- DB_HOST, e assim por diante.
    db_host: str
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: SecretStr  # SecretStr evita que a senha apareça em logs e mensagens

    # DW do UniData (unidata_dw_hml / unidata_dw_prd). Vazio (DW_HOST) = DW desligado.
    # Hoje é usado pelo Gerador para criar o schema de cada dashboard novo; por isso o usuário
    # precisa ter permissão para criar schemas (CREATE no banco).
    dw_host: str = ""
    dw_port: int = 5432
    dw_name: str = ""
    dw_user: str = ""
    dw_password: SecretStr = SecretStr("")

    # Entrada pelo portal UniData (área do time de dados).
    # Segredo combinado com o UniData: assina o "ingresso" de 60 s gerado pelo portal.
    portal_ingresso_secret: SecretStr = SecretStr("")
    # Endereço do portal UniData (link "Voltar ao portal" e mensagens de entrada)
    portal_url: str = ""
    # Segredo próprio do UniDash: assina a sessão de trabalho do time de dados
    sessao_secret: SecretStr = SecretStr("")
    sessao_horas: int = 8

    # Integração com o Hub (link de embed). Vazio = embed desligado.
    # Origem do Hub (só ela pode abrir o dashboard em iframe; também usada no nginx do front)
    embed_hub_origin: str = ""
    # Segredo combinado com o Hub: o Hub assina o token de 60 s com ele. Um por ambiente.
    embed_hub_secret: SecretStr = SecretStr("")
    # Duração da sessão de um dashboard aberto pelo Hub
    embed_sessao_minutos: int = 30

    @field_validator("portal_ingresso_secret", "sessao_secret", "embed_hub_secret")
    @classmethod
    def _segredo_forte(cls, valor: SecretStr) -> SecretStr:
        # Vazio = recurso desligado. Preenchido = no mínimo 32 caracteres.
        if valor.get_secret_value() and len(valor.get_secret_value()) < 32:
            raise ValueError("o segredo precisa ter pelo menos 32 caracteres")
        return valor


@lru_cache
def obter_config() -> Config:
    """Devolve a configuração, lida uma única vez."""
    try:
        return Config()
    except ValidationError as erro:
        variaveis = sorted({str(e["loc"][0]).upper() for e in erro.errors()})
        raise RuntimeError(
            "Configuração inválida ou incompleta. Confira no .env: " + ", ".join(variaveis)
        ) from None
