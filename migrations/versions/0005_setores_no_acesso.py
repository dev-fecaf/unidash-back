"""Setores de quem acessou (lista).

O Hub manda os setores da pessoa que dão acesso ao dashboard como lista (uma pessoa pode
estar em mais de um setor). A coluna da 0004 (usuario_setor, texto) vira usuario_setores (text[]).
Quem já tinha um setor gravado fica com uma lista de um item.

Revisão: 0005
Anterior: 0004
Criada em: 2026-10-07
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE unidash.acesso RENAME COLUMN usuario_setor TO usuario_setores")
    op.execute(
        "ALTER TABLE unidash.acesso ALTER COLUMN usuario_setores TYPE text[] "
        "USING CASE WHEN usuario_setores IS NULL THEN NULL ELSE ARRAY[usuario_setores] END"
    )
    op.execute(
        "COMMENT ON COLUMN unidash.acesso.usuario_setores IS "
        "'Campo setores do token do Hub (setores que dão acesso ao dashboard), como estava no dia do acesso'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE unidash.acesso ALTER COLUMN usuario_setores TYPE varchar(120) "
        "USING left(array_to_string(usuario_setores, ', '), 120)"
    )
    op.execute("ALTER TABLE unidash.acesso RENAME COLUMN usuario_setores TO usuario_setor")
    op.execute(
        "COMMENT ON COLUMN unidash.acesso.usuario_setor IS "
        "'Campo setor do token do Hub, como estava no dia do acesso'"
    )
