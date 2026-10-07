"""Regras e consultas do Gerador.

Regras combinadas (06/10/2026):
- Página removida não é apagada: fica desativada (o histórico de acessos aponta para ela).
- Dashboard não é excluído: fica com status "desativado". O hash nunca muda (o Hub depende dele).
- Todo dashboard precisa de pelo menos 1 página ativa, em qualquer status (decidido em 07/10/2026:
  o link de embed abre a primeira página). (A falta de configuração no
  front só gera um aviso, na tela.)
- Não pode haver dois dashboards com o mesmo nome entre os não desativados.
- Nome de categoria é único (o banco também garante).
- Identificador (slug) do dashboard e da categoria: gerado do nome no cadastro, único e fixo
  (o banco impede a troca). Se já existir (inclusive de um desativado), recebe _2, _3...
  O da categoria fica só no banco (a tela mostra o nome como foi digitado).

Toda função que grava confirma a transação no final (commit). Se qualquer regra falhar no meio,
nada é confirmado: a conexão é devolvida sem commit e o banco desfaz tudo.
"""

from sqlalchemy import Connection, text

from app.dominios.gerador.identificador import com_sufixo, gerar_slug
from app.dominios.gerador.modelos import (
    CategoriaAlterarIn,
    CategoriaIn,
    CategoriaOut,
    DashboardDetalhe,
    DashboardIn,
    DashboardResumo,
    PaginaOut,
)


class ErroCadastro(Exception):
    """Regra do cadastro não atendida. `status` vira o código HTTP da resposta."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


def _linha(conexao: Connection, sql: str, **parametros):
    return conexao.execute(text(sql), parametros).mappings().first()


def _linhas(conexao: Connection, sql: str, **parametros):
    return list(conexao.execute(text(sql), parametros).mappings())


# ================================================================ categorias


def listar_categorias(conexao: Connection) -> list[CategoriaOut]:
    linhas = _linhas(conexao, """
        SELECT c.id, c.slug, c.nome, c.descricao, c.ordem, c.ativo,
               count(d.id) FILTER (WHERE d.status <> 'desativado') AS dashboards
        FROM unidash.categoria c
        LEFT JOIN unidash.dashboard d ON d.categoria_id = c.id
        GROUP BY c.id
        ORDER BY c.ordem, c.nome
    """)
    return [CategoriaOut(**l) for l in linhas]


def _conferir_nome_categoria(conexao: Connection, nome: str, ignorar_id: int | None = None) -> None:
    repetida = _linha(conexao, """
        SELECT id, nome FROM unidash.categoria WHERE lower(nome) = lower(:nome)
    """, nome=nome)
    if repetida and repetida["id"] != ignorar_id:
        raise ErroCadastro(409, f"Já existe uma categoria chamada \"{repetida['nome']}\".")


def criar_categoria(conexao: Connection, dados: CategoriaIn) -> CategoriaOut:
    _conferir_nome_categoria(conexao, dados.nome)
    nova = _linha(conexao, """
        INSERT INTO unidash.categoria (nome, slug, descricao, ordem)
        VALUES (:nome, :slug, :descricao, (SELECT coalesce(max(ordem), 0) + 1 FROM unidash.categoria))
        RETURNING id
    """, nome=dados.nome, slug=proximo_slug(conexao, dados.nome, tabela="categoria"), descricao=dados.descricao)
    conexao.commit()
    return next(c for c in listar_categorias(conexao) if c.id == nova["id"])


def alterar_categoria(conexao: Connection, categoria_id: int, dados: CategoriaAlterarIn) -> CategoriaOut:
    _conferir_nome_categoria(conexao, dados.nome, ignorar_id=categoria_id)
    alterada = _linha(conexao, """
        UPDATE unidash.categoria SET nome = :nome, descricao = :descricao, ativo = :ativo
        WHERE id = :id
        RETURNING id
    """, id=categoria_id, nome=dados.nome, descricao=dados.descricao, ativo=dados.ativo)
    if alterada is None:
        raise ErroCadastro(404, "Categoria não encontrada.")
    conexao.commit()
    return next(c for c in listar_categorias(conexao) if c.id == categoria_id)


def ordenar_categorias(conexao: Connection, ids: list[int]) -> list[CategoriaOut]:
    existentes = {l["id"] for l in _linhas(conexao, "SELECT id FROM unidash.categoria")}
    if set(ids) != existentes or len(ids) != len(existentes):
        raise ErroCadastro(422, "A nova ordem precisa conter todas as categorias, cada uma uma vez.")
    for posicao, categoria_id in enumerate(ids, start=1):
        conexao.execute(
            text("UPDATE unidash.categoria SET ordem = :ordem WHERE id = :id"),
            {"ordem": posicao, "id": categoria_id},
        )
    conexao.commit()
    return listar_categorias(conexao)


# ================================================================ dashboards


def listar_dashboards(conexao: Connection) -> list[DashboardResumo]:
    linhas = _linhas(conexao, """
        SELECT d.hash, d.slug, d.nome, c.nome AS categoria, d.status, d.responsavel_login, d.atualizado_em,
               count(p.id) FILTER (WHERE p.ativo) AS paginas
        FROM unidash.dashboard d
        JOIN unidash.categoria c ON c.id = d.categoria_id
        LEFT JOIN unidash.pagina p ON p.dashboard_id = d.id
        GROUP BY d.id, c.id
        ORDER BY d.atualizado_em DESC
    """)
    return [DashboardResumo(**l) for l in linhas]


def buscar_dashboard(conexao: Connection, hash_: str) -> DashboardDetalhe:
    d = _linha(conexao, """
        SELECT d.id, d.hash, d.slug, d.nome, d.descricao, d.categoria_id, c.nome AS categoria, d.status,
               d.responsavel_login, d.criado_em, d.atualizado_em
        FROM unidash.dashboard d
        JOIN unidash.categoria c ON c.id = d.categoria_id
        WHERE d.hash = :hash
    """, hash=hash_)
    if d is None:
        raise ErroCadastro(404, "Dashboard não encontrado.")
    paginas = _linhas(conexao, """
        SELECT codigo, nome, ordem, ativo FROM unidash.pagina
        WHERE dashboard_id = :id
        ORDER BY ativo DESC, ordem, id
    """, id=d["id"])
    dados = {k: v for k, v in d.items() if k != "id"}
    return DashboardDetalhe(**dados, paginas=[PaginaOut(**p) for p in paginas])


# Tabelas que têm identificador (lista fechada: o nome da tabela entra no SQL)
_TABELAS_COM_SLUG = {"dashboard": "unidash.dashboard", "categoria": "unidash.categoria"}


def proximo_slug(conexao: Connection, nome: str, tabela: str = "dashboard") -> str:
    """Identificador que um dashboard (ou categoria) novo com este nome vai receber (com _2, _3... se já existir)."""
    tabela_sql = _TABELAS_COM_SLUG[tabela]
    base = gerar_slug(nome)
    if not base:
        raise ErroCadastro(422, "O nome precisa ter pelo menos uma letra ou um número.")
    # Identificadores que começam igual (os com _2, _3... podem ter a base cortada no fim)
    prefixo = base[:40]
    usados = {
        l["slug"]
        for l in _linhas(conexao, f"SELECT slug FROM {tabela_sql} WHERE left(slug, :n) = :prefixo",
                         n=len(prefixo), prefixo=prefixo)
    }
    slug, numero = base, 2
    while slug in usados:
        slug, numero = com_sufixo(base, numero), numero + 1
    return slug


def conferir_regras_do_dashboard(dados: DashboardIn) -> None:
    """Regras que não precisam do banco (dá para testar sem banco)."""
    if not dados.paginas:
        raise ErroCadastro(422, "O dashboard precisa de pelo menos 1 página.")
    nomes = [p.nome.lower() for p in dados.paginas]
    if len(nomes) != len(set(nomes)):
        raise ErroCadastro(422, "Duas páginas não podem ter o mesmo nome no mesmo dashboard.")
    codigos = [p.codigo for p in dados.paginas if p.codigo]
    if len(codigos) != len(set(codigos)):
        raise ErroCadastro(422, "A mesma página apareceu duas vezes na lista.")


def _conferir_nome_dashboard(conexao: Connection, dados: DashboardIn, hash_atual: str | None) -> None:
    if dados.status == "desativado":
        return  # desativados podem repetir nome
    repetido = _linha(conexao, """
        SELECT hash, nome FROM unidash.dashboard
        WHERE lower(nome) = lower(:nome) AND status <> 'desativado'
    """, nome=dados.nome)
    if repetido and repetido["hash"] != hash_atual:
        raise ErroCadastro(409, f"Já existe um dashboard ativo chamado \"{repetido['nome']}\".")


def _conferir_categoria(conexao: Connection, categoria_id: int, categoria_atual: int | None) -> None:
    categoria = _linha(conexao, "SELECT ativo FROM unidash.categoria WHERE id = :id", id=categoria_id)
    if categoria is None:
        raise ErroCadastro(422, "A categoria escolhida não existe.")
    # Categoria desativada não recebe dashboards novos (quem já estava nela pode continuar)
    if not categoria["ativo"] and categoria_id != categoria_atual:
        raise ErroCadastro(422, "A categoria escolhida está desativada.")


def _sincronizar_paginas(conexao: Connection, dashboard_id: int, dados: DashboardIn) -> None:
    existentes = {
        l["codigo"]: l["id"]
        for l in _linhas(conexao, "SELECT id, codigo FROM unidash.pagina WHERE dashboard_id = :id", id=dashboard_id)
    }
    mantidas = set()
    for ordem, pagina in enumerate(dados.paginas, start=1):
        if pagina.codigo:
            if pagina.codigo not in existentes:
                raise ErroCadastro(422, f"A página \"{pagina.nome}\" não pertence a este dashboard.")
            conexao.execute(
                text("UPDATE unidash.pagina SET nome = :nome, ordem = :ordem, ativo = true WHERE id = :id"),
                {"nome": pagina.nome, "ordem": ordem, "id": existentes[pagina.codigo]},
            )
            mantidas.add(pagina.codigo)
        else:
            conexao.execute(
                text("INSERT INTO unidash.pagina (dashboard_id, nome, ordem) VALUES (:id, :nome, :ordem)"),
                {"id": dashboard_id, "nome": pagina.nome, "ordem": ordem},
            )
    # Páginas que existiam e não vieram na lista: desativadas, nunca apagadas
    for codigo, pagina_id in existentes.items():
        if codigo not in mantidas:
            conexao.execute(text("UPDATE unidash.pagina SET ativo = false WHERE id = :id"), {"id": pagina_id})


def criar_dashboard(conexao: Connection, dados: DashboardIn, responsavel: str) -> DashboardDetalhe:
    conferir_regras_do_dashboard(dados)
    if any(p.codigo for p in dados.paginas):
        raise ErroCadastro(422, "Um dashboard novo não pode receber páginas que já existem.")
    _conferir_nome_dashboard(conexao, dados, hash_atual=None)
    _conferir_categoria(conexao, dados.categoria_id, categoria_atual=None)

    novo = _linha(conexao, """
        INSERT INTO unidash.dashboard (nome, slug, descricao, categoria_id, responsavel_login, status)
        VALUES (:nome, :slug, :descricao, :categoria_id, :responsavel, :status)
        RETURNING id, hash
    """, nome=dados.nome, slug=proximo_slug(conexao, dados.nome), descricao=dados.descricao,
        categoria_id=dados.categoria_id, responsavel=responsavel[:80], status=dados.status)
    _sincronizar_paginas(conexao, novo["id"], dados)
    conexao.commit()
    return buscar_dashboard(conexao, novo["hash"])


def alterar_dashboard(conexao: Connection, hash_: str, dados: DashboardIn) -> DashboardDetalhe:
    conferir_regras_do_dashboard(dados)
    atual = _linha(conexao, "SELECT id, categoria_id FROM unidash.dashboard WHERE hash = :hash", hash=hash_)
    if atual is None:
        raise ErroCadastro(404, "Dashboard não encontrado.")
    _conferir_nome_dashboard(conexao, dados, hash_atual=hash_)
    _conferir_categoria(conexao, dados.categoria_id, categoria_atual=atual["categoria_id"])

    # O hash não aparece aqui: ele nunca muda (o banco também impede, por trigger)
    conexao.execute(text("""
        UPDATE unidash.dashboard
        SET nome = :nome, descricao = :descricao, categoria_id = :categoria_id, status = :status
        WHERE id = :id
    """), {"nome": dados.nome, "descricao": dados.descricao, "categoria_id": dados.categoria_id,
           "status": dados.status, "id": atual["id"]})
    _sincronizar_paginas(conexao, atual["id"], dados)
    conexao.commit()
    return buscar_dashboard(conexao, hash_)
