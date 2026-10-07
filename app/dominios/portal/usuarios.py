"""Leitura do usuário e das permissões no schema app do UniData (SÓ LEITURA).

Repete a regra do UniData (app/dominios/acesso/services/autorizacao.py):
- perfil admin tem todas as permissões, sem precisar de linhas no banco;
- os demais somam as permissões ativas do perfil e as individuais ainda válidas.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import Connection, text

PERFIL_ADMIN = "admin"

# Permissões do UniData que o UniDash usa (módulo Dashboards + documentação de dashboards)
ACESSAR = "hub.dashboards.acessar"
PERMISSOES_UNIDASH = (
    ACESSAR,
    "dashboards.visao-geral.visualizar",
    "dashboards.galeria.visualizar",
    "dashboards.gerador.visualizar",
    "dashboards.uso.visualizar",
    "dashboards.favoritos.visualizar",
    "dashboards.templates.visualizar",
    "documentacao.dashboards.visualizar",
)


@dataclass(frozen=True)
class UsuarioPortal:
    usu_id: uuid.UUID
    nome: str
    email: str
    perfil: str
    ativo: bool
    perfil_ativo: bool
    deve_trocar_senha: bool
    permissoes: frozenset[str] = field(default_factory=frozenset)

    @property
    def pode_entrar(self) -> bool:
        return self.ativo and self.perfil_ativo and not self.deve_trocar_senha

    def tem(self, permissao: str) -> bool:
        return permissao in self.permissoes


_SQL_USUARIO = text("""
    SELECT u.usu_id, u.usu_nome, u.usu_email, u.usu_ativo, u.usu_deve_trocar_senha,
           u.usu_perfil_id, p.prf_codigo, p.prf_ativo
    FROM app.tb_usuarios u
    JOIN app.tb_perfis p ON p.prf_id = u.usu_perfil_id
    WHERE u.usu_id = :usu_id
""")

_SQL_PERMISSOES = text("""
    SELECT m.prm_codigo
    FROM app.tb_perfil_permissao pp
    JOIN app.tb_permissoes m ON m.prm_id = pp.ppr_permissao_id
    WHERE pp.ppr_perfil_id = :perfil_id AND pp.ppr_ativo AND m.prm_ativo
    UNION
    SELECT m.prm_codigo
    FROM app.tb_usuario_permissao up
    JOIN app.tb_permissoes m ON m.prm_id = up.upr_permissao_id
    WHERE up.upr_usuario_id = :usu_id AND up.upr_ativo AND m.prm_ativo
      AND (up.upr_valido_ate IS NULL OR up.upr_valido_ate > now())
""")


def carregar_usuario(conexao: Connection, usu_id: uuid.UUID) -> UsuarioPortal | None:
    """Busca a pessoa e as permissões dela relacionadas a dashboards. None se não existir."""
    linha = conexao.execute(_SQL_USUARIO, {"usu_id": usu_id}).mappings().first()
    if linha is None:
        return None

    if linha["prf_codigo"] == PERFIL_ADMIN:
        permissoes = frozenset(PERMISSOES_UNIDASH)
    else:
        codigos = conexao.execute(
            _SQL_PERMISSOES, {"perfil_id": linha["usu_perfil_id"], "usu_id": usu_id}
        ).scalars()
        permissoes = frozenset(c for c in codigos if c in PERMISSOES_UNIDASH)

    return UsuarioPortal(
        usu_id=linha["usu_id"],
        nome=linha["usu_nome"],
        email=linha["usu_email"],
        perfil=linha["prf_codigo"],
        ativo=linha["usu_ativo"],
        perfil_ativo=linha["prf_ativo"],
        deve_trocar_senha=linha["usu_deve_trocar_senha"],
        permissoes=permissoes,
    )
