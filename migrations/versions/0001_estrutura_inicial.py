"""Estrutura inicial do schema unidash.

Reproduz o script docs/estrutura-banco.md (schema, funções, tabelas, índices, triggers
e comentários), exatamente como ele foi aplicado no unidata_hml.

- unidata_hml: tudo já existe; esta migração é só marcada como aplicada (alembic stamp 0001).
- unidata_prd (banco novo): esta migração cria tudo (alembic upgrade head).

Revisão: 0001
Anterior: nenhuma
Criada em: 2026-10-06
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


COMANDOS = [
    # ---------------------------------------------------------------- schema
    "CREATE SCHEMA IF NOT EXISTS unidash",
    "COMMENT ON SCHEMA unidash IS 'UniDash: cadastro de dashboards e registro de acessos'",
    # ---------------------------------------------------------------- funções auxiliares
    # Gera um identificador de 32 caracteres (hash do dashboard, código da página)
    """
    CREATE OR REPLACE FUNCTION unidash.novo_codigo()
    RETURNS varchar(32)
    LANGUAGE sql
    AS $$
        SELECT replace(gen_random_uuid()::text, '-', '')::varchar(32);
    $$
    """,
    # Atualiza a coluna atualizado_em a cada alteração
    """
    CREATE OR REPLACE FUNCTION unidash.marcar_atualizado_em()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        NEW.atualizado_em := now();
        RETURN NEW;
    END;
    $$
    """,
    # Impede alterar o hash do dashboard depois de criado (o Hub depende dele)
    # Na simulação (alembic upgrade --sql) o % abaixo aparece como %%; na execução real
    # ele chega ao banco como % (conferido em 06/10/2026).
    """
    CREATE OR REPLACE FUNCTION unidash.bloquear_troca_hash()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        IF NEW.hash IS DISTINCT FROM OLD.hash THEN
            RAISE EXCEPTION 'O hash do dashboard % não pode ser alterado', OLD.id;
        END IF;
        RETURN NEW;
    END;
    $$
    """,
    # ---------------------------------------------------------------- categoria
    """
    CREATE TABLE unidash.categoria (
        id          smallserial  PRIMARY KEY,
        nome        varchar(80)  NOT NULL UNIQUE,
        descricao   text,
        ordem       smallint     NOT NULL DEFAULT 0,
        ativo       boolean      NOT NULL DEFAULT true
    )
    """,
    "COMMENT ON TABLE unidash.categoria IS 'Agrupamento dos dashboards (financeiro, acadêmico...)'",
    # ---------------------------------------------------------------- dashboard
    """
    CREATE TABLE unidash.dashboard (
        id                 serial        PRIMARY KEY,
        hash               varchar(32)   NOT NULL UNIQUE DEFAULT unidash.novo_codigo(),
        nome               varchar(120)  NOT NULL,
        descricao          text,
        categoria_id       smallint      NOT NULL REFERENCES unidash.categoria (id),
        responsavel_login  varchar(80),
        status             varchar(20)   NOT NULL DEFAULT 'rascunho'
                           CHECK (status IN ('rascunho', 'publicado', 'desativado')),
        criado_em          timestamptz   NOT NULL DEFAULT now(),
        atualizado_em      timestamptz   NOT NULL DEFAULT now()
    )
    """,
    "COMMENT ON TABLE  unidash.dashboard IS 'Cadastro dos dashboards'",
    "COMMENT ON COLUMN unidash.dashboard.hash IS 'Identificador público cadastrado no Hub; nunca muda'",
    "COMMENT ON COLUMN unidash.dashboard.responsavel_login IS 'Login do dev no portal UniData'",
    "CREATE INDEX ix_dashboard_categoria ON unidash.dashboard (categoria_id)",
    """
    CREATE TRIGGER tg_dashboard_atualizado_em
        BEFORE UPDATE ON unidash.dashboard
        FOR EACH ROW EXECUTE FUNCTION unidash.marcar_atualizado_em()
    """,
    """
    CREATE TRIGGER tg_dashboard_hash_fixo
        BEFORE UPDATE OF hash ON unidash.dashboard
        FOR EACH ROW EXECUTE FUNCTION unidash.bloquear_troca_hash()
    """,
    # ---------------------------------------------------------------- pagina
    """
    CREATE TABLE unidash.pagina (
        id            serial        PRIMARY KEY,
        dashboard_id  integer       NOT NULL REFERENCES unidash.dashboard (id),
        codigo        varchar(32)   NOT NULL UNIQUE DEFAULT unidash.novo_codigo(),
        nome          varchar(120)  NOT NULL,
        ordem         smallint      NOT NULL DEFAULT 0,
        ativo         boolean       NOT NULL DEFAULT true
    )
    """,
    "COMMENT ON TABLE  unidash.pagina IS 'Páginas (abas) de cada dashboard'",
    "COMMENT ON COLUMN unidash.pagina.codigo IS 'Usado na URL /embed/{hash}/{codigo}'",
    "CREATE INDEX ix_pagina_dashboard ON unidash.pagina (dashboard_id)",
    # ---------------------------------------------------------------- endpoint
    """
    CREATE TABLE unidash.endpoint (
        id              serial        PRIMARY KEY,
        rota            varchar(160)  NOT NULL UNIQUE,
        nome            varchar(120)  NOT NULL,
        descricao       text,
        funcao          varchar(120)  NOT NULL,
        fonte           varchar(20)   NOT NULL DEFAULT 'dw'
                        CHECK (fonte IN ('dw', 'bigquery')),
        cache_segundos  integer       NOT NULL DEFAULT 3600
                        CHECK (cache_segundos >= 0),
        ativo           boolean       NOT NULL DEFAULT true
    )
    """,
    "COMMENT ON TABLE  unidash.endpoint IS 'Endpoints de dados consumidos pelos dashboards'",
    "COMMENT ON COLUMN unidash.endpoint.funcao IS 'Nome da função de consulta no código'",
    # Texto igual ao gravado no unidata_hml; o nome certo do DW (unidata_dw_*) será
    # corrigido numa migração seguinte.
    "COMMENT ON COLUMN unidash.endpoint.fonte IS 'De onde o endpoint lê: dw (unifecaf_dw) ou bigquery'",
    "COMMENT ON COLUMN unidash.endpoint.cache_segundos IS 'Tempo de vida da resposta no Redis'",
    # ---------------------------------------------------------------- pagina_endpoint
    """
    CREATE TABLE unidash.pagina_endpoint (
        pagina_id    integer  NOT NULL REFERENCES unidash.pagina (id) ON DELETE CASCADE,
        endpoint_id  integer  NOT NULL REFERENCES unidash.endpoint (id),
        PRIMARY KEY (pagina_id, endpoint_id)
    )
    """,
    "COMMENT ON TABLE unidash.pagina_endpoint IS 'Quais endpoints cada página usa'",
    "CREATE INDEX ix_pagina_endpoint_endpoint ON unidash.pagina_endpoint (endpoint_id)",
    # ---------------------------------------------------------------- acesso
    """
    CREATE TABLE unidash.acesso (
        id             bigserial     PRIMARY KEY,
        usuario_login  varchar(80)   NOT NULL,
        usuario_nome   varchar(120),
        usuario_email  varchar(160),
        dashboard_id   integer       NOT NULL REFERENCES unidash.dashboard (id),
        pagina_id      integer       REFERENCES unidash.pagina (id),
        origem         varchar(20)   NOT NULL
                       CHECK (origem IN ('hub', 'portal')),
        token_jti      varchar(64),
        acessado_em    timestamptz   NOT NULL DEFAULT now()
    )
    """,
    "COMMENT ON TABLE  unidash.acesso IS 'Quem abriu qual dashboard e página; uma linha por abertura ou troca de aba'",
    "COMMENT ON COLUMN unidash.acesso.pagina_id IS 'Vazio na abertura do dashboard; preenchido ao trocar de aba'",
    "COMMENT ON COLUMN unidash.acesso.token_jti IS 'Id do token usado, só para rastreio'",
    "CREATE INDEX ix_acesso_dashboard_data ON unidash.acesso (dashboard_id, acessado_em)",
    "CREATE INDEX ix_acesso_data           ON unidash.acesso (acessado_em)",
    # ---------------------------------------------------------------- endpoint_chamada
    """
    CREATE TABLE unidash.endpoint_chamada (
        id               bigserial    PRIMARY KEY,
        endpoint_id      integer      NOT NULL REFERENCES unidash.endpoint (id),
        dashboard_id     integer      REFERENCES unidash.dashboard (id),
        pagina_id        integer      REFERENCES unidash.pagina (id),
        usuario_login    varchar(80),
        origem_resposta  varchar(20)  NOT NULL
                         CHECK (origem_resposta IN ('redis', 'dw', 'cache_bq', 'bq')),
        bytes_cobrados   bigint,
        duracao_ms       integer,
        chamado_em       timestamptz  NOT NULL DEFAULT now()
    )
    """,
    "COMMENT ON TABLE  unidash.endpoint_chamada IS 'Cada chamada de endpoint feita por um gráfico'",
    "COMMENT ON COLUMN unidash.endpoint_chamada.bytes_cobrados IS 'Preenchido só quando a fonte é o BigQuery'",
    "CREATE INDEX ix_chamada_endpoint_data ON unidash.endpoint_chamada (endpoint_id, chamado_em)",
    "CREATE INDEX ix_chamada_data          ON unidash.endpoint_chamada (chamado_em)",
    # ---------------------------------------------------------------- endpoint_chamada_diaria
    """
    CREATE TABLE unidash.endpoint_chamada_diaria (
        data              date     NOT NULL,
        endpoint_id       integer  NOT NULL REFERENCES unidash.endpoint (id),
        chamadas          integer  NOT NULL DEFAULT 0,
        chamadas_redis    integer  NOT NULL DEFAULT 0,
        duracao_media_ms  integer,
        bytes_cobrados    bigint   NOT NULL DEFAULT 0,
        PRIMARY KEY (data, endpoint_id)
    )
    """,
    "COMMENT ON TABLE unidash.endpoint_chamada_diaria IS 'Resumo diário de chamadas por endpoint'",
]


def upgrade() -> None:
    for comando in COMANDOS:
        op.execute(comando)


def downgrade() -> None:
    # Desfazer a estrutura inicial apagaria todos os dashboards e registros de acesso.
    # Isso nunca deve acontecer por um comando automático.
    raise NotImplementedError("A estrutura inicial do UniDash não é desfeita por migração.")
