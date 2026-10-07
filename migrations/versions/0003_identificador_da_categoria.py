"""Identificador (slug) da categoria.

Mesma regra do identificador do dashboard (0002): minúsculas, sem acentos, "_" no lugar de espaços,
começa com letra, até 50 caracteres; único e nunca muda depois de criado (trigger).
Fica só no banco: a tela continua mostrando o nome como foi digitado.

Revisão: 0003
Anterior: 0002
Criada em: 2026-10-07
"""

import re
import unicodedata

import sqlalchemy as sa
from alembic import context, op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


# Cópia congelada da regra de app/dominios/gerador/identificador.py (migração não importa o app)
def _slug(nome: str) -> str:
    texto = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_") or "categoria"
    if not texto[0].isalpha():
        texto = f"d_{texto}"
    return texto[:50].rstrip("_")


def upgrade() -> None:
    op.execute("ALTER TABLE unidash.categoria ADD COLUMN slug varchar(50)")

    # Categorias que já existam ganham o identificador a partir do nome (repetidos ganham _2, _3...)
    if not context.is_offline_mode():  # na simulação (--sql) não há banco para ler
        conexao = op.get_bind()
        usados = set()
        for id_, nome in conexao.execute(sa.text("SELECT id, nome FROM unidash.categoria ORDER BY id")):
            base = _slug(nome)
            slug, numero = base, 2
            while slug in usados:
                sufixo = f"_{numero}"
                slug, numero = base[: 50 - len(sufixo)].rstrip("_") + sufixo, numero + 1
            usados.add(slug)
            conexao.execute(sa.text("UPDATE unidash.categoria SET slug = :s WHERE id = :i"), {"s": slug, "i": id_})

    op.execute("ALTER TABLE unidash.categoria ALTER COLUMN slug SET NOT NULL")
    op.execute("ALTER TABLE unidash.categoria ADD CONSTRAINT uq_categoria_slug UNIQUE (slug)")
    op.execute(
        "ALTER TABLE unidash.categoria ADD CONSTRAINT ck_categoria_slug "
        "CHECK (slug ~ '^[a-z][a-z0-9_]*$')"
    )
    op.execute(
        "COMMENT ON COLUMN unidash.categoria.slug IS "
        "'Identificador em minúsculas, gerado do nome na criação; nunca muda'"
    )

    # Impede trocar o identificador depois de criado (igual ao do dashboard)
    op.execute("""
        CREATE OR REPLACE FUNCTION unidash.bloquear_troca_slug_categoria()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.slug IS DISTINCT FROM OLD.slug THEN
                RAISE EXCEPTION 'O identificador da categoria % não pode ser alterado', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER tg_categoria_slug_fixo
            BEFORE UPDATE OF slug ON unidash.categoria
            FOR EACH ROW EXECUTE FUNCTION unidash.bloquear_troca_slug_categoria()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tg_categoria_slug_fixo ON unidash.categoria")
    op.execute("DROP FUNCTION IF EXISTS unidash.bloquear_troca_slug_categoria()")
    op.execute("ALTER TABLE unidash.categoria DROP COLUMN slug")
