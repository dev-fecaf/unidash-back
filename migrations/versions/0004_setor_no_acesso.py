"""Setor de quem acessou.

Coluna nova unidash.acesso.usuario_setor: campo `setor` do token do Hub, guardado como
estava no dia do acesso (se a pessoa mudar de setor, o histórico continua com o antigo).
Opcional: se o Hub não mandar, fica vazio.

Revisão: 0004
Anterior: 0003
Criada em: 2026-10-07
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE unidash.acesso ADD COLUMN usuario_setor varchar(120)")
    op.execute(
        "COMMENT ON COLUMN unidash.acesso.usuario_setor IS "
        "'Campo setor do token do Hub, como estava no dia do acesso'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE unidash.acesso DROP COLUMN usuario_setor")
