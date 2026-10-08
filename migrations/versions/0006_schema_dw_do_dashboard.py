"""Schema do dashboard no DW (coluna schema_dw).

Cada dashboard aponta para um schema do DW (unidata_dw_hml / unidata_dw_prd) com o mesmo nome
do identificador (slug), sem prefixo. Único entre os dashboards e nunca um schema reservado do DW.
O Gerador grava a coluna e cria o schema vazio no DW ao cadastrar (app/dominios/gerador/schema_dw.py).

Em hml a coluna, a trava de único e o check foram criados à mão em 08/10/2026, antes desta migração:
por isso tudo aqui usa "se não existir" (rodar em hml não muda nada; em prd cria igual).

Revisão: 0006
Anterior: 0005
Criada em: 2026-10-08
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE unidash.dashboard ADD COLUMN IF NOT EXISTS schema_dw varchar(63)")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'dashboard_schema_dw_key'
                           AND conrelid = 'unidash.dashboard'::regclass) THEN
                ALTER TABLE unidash.dashboard ADD CONSTRAINT dashboard_schema_dw_key UNIQUE (schema_dw);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'dashboard_schema_dw_check'
                           AND conrelid = 'unidash.dashboard'::regclass) THEN
                ALTER TABLE unidash.dashboard ADD CONSTRAINT dashboard_schema_dw_check CHECK (
                    schema_dw ~ '^[a-z][a-z0-9_]*$'
                    AND schema_dw <> ALL (ARRAY['stg', 'dim', 'fat', 'dataw', 'public']::varchar[])
                );
            END IF;
        END $$
    """)
    op.execute(
        "COMMENT ON COLUMN unidash.dashboard.schema_dw IS "
        "'Schema do dashboard no DW (mesmo nome do slug, sem prefixo); único; o Gerador cria o schema vazio no DW'"
    )
    op.execute(
        "COMMENT ON COLUMN unidash.dashboard.slug IS "
        "'Identificador em minúsculas (pasta no front e no back; nome do schema no DW, coluna schema_dw); nunca muda'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE unidash.dashboard DROP COLUMN IF EXISTS schema_dw")
    op.execute(
        "COMMENT ON COLUMN unidash.dashboard.slug IS "
        "'Identificador em minúsculas (pasta no front e schema dash_<slug> no DW); nunca muda'"
    )
