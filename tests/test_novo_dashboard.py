"""Comando novo_dashboard: cria as pastas a partir dos modelos, sem sobrescrever (sem banco)."""

import pytest

from scripts import novo_dashboard

DADOS = {
    "identificador": "executivo",
    "hash": "h" * 32,
    "nome": 'Executivo "Geral"',
    "paginas": [{"codigo": "a" * 32, "nome": "Visão geral"}, {"codigo": "b" * 32, "nome": "D'Ávila"}],
}

REGISTRO = """import exemplo from './exemplo/config.js'
// novo_dashboard: imports (o comando acrescenta aqui)

const DASHBOARDS = [
  ...(import.meta.env.DEV ? [exemplo] : []),
  // novo_dashboard: lista (o comando acrescenta aqui)
]
"""


@pytest.fixture
def repos(tmp_path):
    front, back = tmp_path / "unidash-front", tmp_path / "unidash-back"
    (front / "src" / "dashboards").mkdir(parents=True)
    (front / "src" / "dashboards" / "registro.js").write_text(REGISTRO, encoding="utf-8")
    (back / "app" / "dominios" / "dados").mkdir(parents=True)
    return front, back


def test_cria_front_e_back_com_os_dados_do_banco(repos):
    front, back = repos
    novo_dashboard.criar_pastas(DADOS, front, back)

    pasta = front / "src/dashboards/executivo"
    config = (pasta / "config.js").read_text(encoding="utf-8")
    assert f"hash: '{'h' * 32}'" in config
    assert 'nome: "Executivo \\"Geral\\""' in config  # aspas do nome não quebram o JS
    assert "import './tema.css'" in config
    assert "import VisaoGeral from './paginas/VisaoGeral.jsx'" in config
    assert f"{{ codigo: '{'b' * 32}', nome: \"D'Ávila\", Conteudo: DAvila }}," in config

    # Tema só deste dashboard e um arquivo por página, já com o layout padrão
    assert ".dashboard-executivo {" in (pasta / "tema.css").read_text(encoding="utf-8")
    pagina = (pasta / "paginas/VisaoGeral.jsx").read_text(encoding="utf-8")
    assert "export default function VisaoGeral({ dashboard, pagina })" in pagina
    assert f"Código da página no banco: {'a' * 32}" in pagina
    assert (pasta / "paginas/DAvila.jsx").exists()
    assert "__" not in pagina.replace("pagina__", "").replace("espaco-reservado--", "")  # nenhum marcador sobrou

    registro = (front / "src/dashboards/registro.js").read_text(encoding="utf-8")
    assert "import dashboard_executivo from './executivo/config.js'" in registro
    assert "  dashboard_executivo,\n  // novo_dashboard: lista" in registro

    rotas = (back / "app/dominios/dados/executivo/rotas.py").read_text(encoding="utf-8")
    assert 'SCHEMA = "executivo"' in rotas
    compile(rotas, "rotas.py", "exec")  # o Python gerado é válido
    assert (back / "app/dominios/dados/executivo/__init__.py").exists()


@pytest.mark.parametrize(
    "nomes, esperado",
    [
        (["Visão geral"], ["VisaoGeral"]),
        (["Matrículas & evasão"], ["MatriculasEvasao"]),
        (["2026"], ["Pagina2026"]),  # componente React começa com letra maiúscula
        (["!!!"], ["Pagina"]),
        (["Visão geral", "Visao Geral"], ["VisaoGeral", "VisaoGeral2"]),  # sem repetir
    ],
)
def test_nome_do_componente_de_cada_pagina(nomes, esperado):
    usados = set()
    assert [novo_dashboard.nome_de_componente(n, usados) for n in nomes] == esperado


def test_nunca_sobrescreve_e_nao_registra_duas_vezes(repos):
    front, back = repos
    novo_dashboard.criar_pastas(DADOS, front, back)
    (front / "src/dashboards/executivo/config.js").write_text("// editado", encoding="utf-8")

    mensagens = novo_dashboard.criar_pastas(DADOS, front, back)
    assert (front / "src/dashboards/executivo/config.js").read_text(encoding="utf-8") == "// editado"
    assert all("já existe" in m for m in mensagens)
    assert (front / "src/dashboards/registro.js").read_text(encoding="utf-8").count("dashboard_executivo,") == 1
