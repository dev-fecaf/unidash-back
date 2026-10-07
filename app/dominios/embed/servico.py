"""Consultas do embed: o dashboard pelo hash (com as páginas ativas) e o registro do acesso."""

from sqlalchemy import Connection, text

from app.dominios.embed.tokens import PessoaDoHub


def buscar_dashboard(conexao: Connection, hash_: str) -> dict | None:
    """Dashboard pelo hash, com as páginas ativas na ordem do Gerador. None se não existir."""
    dashboard = conexao.execute(
        text("SELECT id, hash, nome, status FROM unidash.dashboard WHERE hash = :hash"), {"hash": hash_}
    ).mappings().first()
    if dashboard is None:
        return None
    paginas = conexao.execute(
        text("""
            SELECT codigo, nome FROM unidash.pagina
            WHERE dashboard_id = :id AND ativo
            ORDER BY ordem, id
        """),
        {"id": dashboard["id"]},
    ).mappings().all()
    return {**dashboard, "paginas": [dict(p) for p in paginas]}


def registrar_acesso(conexao: Connection, dashboard_id: int, pessoa: PessoaDoHub) -> None:
    """Grava a abertura do dashboard pelo Hub. A contagem (30 min) é feita na hora de consultar."""
    conexao.execute(
        text("""
            INSERT INTO unidash.acesso
                (usuario_login, usuario_nome, usuario_email, usuario_setores, dashboard_id, origem, token_jti)
            VALUES (:login, :nome, :email, :setores, :dashboard_id, 'hub', :jti)
        """),
        {
            "login": pessoa.login, "nome": pessoa.nome, "email": pessoa.email, "setores": pessoa.setores,
            "dashboard_id": dashboard_id, "jti": pessoa.jti,
        },
    )
    conexao.commit()
