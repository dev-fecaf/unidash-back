"""Ambiente do Alembic do UniDash.

Regras (o banco é dividido com o UniData):
- o Alembic do UniDash só enxerga o schema "unidash";
- o controle de versões fica em unidash.alembic_version, nunca em public.alembic_version
  (essa é do UniData);
- a conexão vem das variáveis DB_* do .env, a mesma usada pela API.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from app.db.sessao import obter_engine

SCHEMA = "unidash"

# Mostra no terminal o que o Alembic está fazendo (configuração em alembic.ini)
if context.config.config_file_name:
    fileConfig(context.config.config_file_name, disable_existing_loggers=False)

# Ainda não há modelos do SQLAlchemy; quando houver, apontar aqui o metadata deles.
target_metadata = None


def incluir_nome(nome, tipo, _pais) -> bool:
    """Na comparação automática, considera só o schema unidash."""
    if tipo == "schema":
        return nome == SCHEMA
    return True


OPCOES_COMUNS = {
    "target_metadata": target_metadata,
    "version_table_schema": SCHEMA,
    "include_schemas": True,
    "include_name": incluir_nome,
}


def rodar_simulacao() -> None:
    """Modo simulação (--sql): só imprime o SQL, sem conectar no banco."""
    context.configure(dialect_name="postgresql", literal_binds=True, **OPCOES_COMUNS)
    with context.begin_transaction():
        context.run_migrations()


def rodar_no_banco() -> None:
    with obter_engine().connect() as conexao:
        # Em um banco novo (produção), o schema ainda não existe, e o Alembic precisa
        # dele para criar a tabela de controle de versões.
        existe = conexao.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = :schema"), {"schema": SCHEMA}
        ).scalar()
        if not existe:
            conexao.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        # Fecha a transação aberta pela consulta acima. Sem isso, o Alembic acha que a
        # transação é de outra pessoa, não confirma nada e tudo é desfeito no final.
        conexao.commit()

        context.configure(connection=conexao, **OPCOES_COMUNS)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    rodar_simulacao()
else:
    rodar_no_banco()
