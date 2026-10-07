"""Identificador (slug) do dashboard.

Coluna nova unidash.dashboard.slug: versão do nome em minúsculas, sem acentos, sem espaços,
só letras, números e "_". Usada na pasta do dashboard no front (src/dashboards/<slug>/) e no
schema do DW (dash_<slug>). Única, e nunca muda depois de criada (trigger, como a do hash).

Também corrige o comentário da coluna endpoint.fonte (citava unifecaf_dw; o certo é unidata_dw_*).

Revisão: 0002
Anterior: 0001
Criada em: 2026-10-07
"""

import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


# Cópia congelada da regra de app/dominios/gerador/identificador.py (migração não importa o app)
def _slug(nome: str) -> str:
    texto = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_") or "dashboard"
    if not texto[0].isalpha():
        texto = f"d_{texto}"
    return texto[:50].rstrip("_")


def upgrade() -> None:
    op.execute("ALTER TABLE unidash.dashboard ADD COLUMN slug varchar(50)")

    # Dashboards que já existam ganham o identificador a partir do nome (repetidos ganham _2, _3...)
    if not context_offline():  # na simulação (--sql) não há banco para ler
        conexao = op.get_bind()
        usados = set()
        for id_, nome in conexao.execute(sa.text("SELECT id, nome FROM unidash.dashboard ORDER BY id")):
            base = _slug(nome)
            slug, numero = base, 2
            while slug in usados:
                sufixo = f"_{numero}"
                slug, numero = base[: 50 - len(sufixo)].rstrip("_") + sufixo, numero + 1
            usados.add(slug)
            conexao.execute(sa.text("UPDATE unidash.dashboard SET slug = :s WHERE id = :i"), {"s": slug, "i": id_})

    op.execute("ALTER TABLE unidash.dashboard ALTER COLUMN slug SET NOT NULL")
    op.execute("ALTER TABLE unidash.dashboard ADD CONSTRAINT uq_dashboard_slug UNIQUE (slug)")
    op.execute(
        "ALTER TABLE unidash.dashboard ADD CONSTRAINT ck_dashboard_slug "
        "CHECK (slug ~ '^[a-z][a-z0-9_]*$')"
    )
    op.execute(
        "COMMENT ON COLUMN unidash.dashboard.slug IS "
        "'Identificador em minúsculas (pasta no front e schema dash_<slug> no DW); nunca muda'"
    )

    # Impede trocar o identificador depois de criado (igual ao hash)
    op.execute("""
        CREATE OR REPLACE FUNCTION unidash.bloquear_troca_slug()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.slug IS DISTINCT FROM OLD.slug THEN
                RAISE EXCEPTION 'O identificador do dashboard % não pode ser alterado', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER tg_dashboard_slug_fixo
            BEFORE UPDATE OF slug ON unidash.dashboard
            FOR EACH ROW EXECUTE FUNCTION unidash.bloquear_troca_slug()
    """)

    op.execute(
        "COMMENT ON COLUMN unidash.endpoint.fonte IS "
        "'De onde o endpoint lê: dw (unidata_dw_hml / unidata_dw_prd) ou bigquery'"
    )


def downgrade() -> None:
    op.execute(
        "COMMENT ON COLUMN unidash.endpoint.fonte IS 'De onde o endpoint lê: dw (unifecaf_dw) ou bigquery'"
    )
    op.execute("DROP TRIGGER IF EXISTS tg_dashboard_slug_fixo ON unidash.dashboard")
    op.execute("DROP FUNCTION IF EXISTS unidash.bloquear_troca_slug()")
    op.execute("ALTER TABLE unidash.dashboard DROP COLUMN slug")


def context_offline() -> bool:
    from alembic import context

    return context.is_offline_mode()
