"""Cria as pastas de um dashboard no front e no back, a partir do cadastro no Gerador.

Uso (na pasta UniDash, com o Docker ligado):
    docker compose exec backend python -m scripts.novo_dashboard <identificador>

O que faz:
1. Busca no banco o dashboard pelo identificador: hash, nome e páginas ativas.
2. Front: cria src/dashboards/<identificador>/ com config.js, tema.css (as cores do dashboard) e
   paginas/ (um arquivo por página, já com o layout padrão), e registra em src/dashboards/registro.js.
3. Back:  cria app/dominios/dados/<identificador>/ (__init__.py e rotas.py, com um endpoint de exemplo).
Os arquivos saem dos modelos em scripts/modelos_dashboard/.

Nunca sobrescreve: se a pasta de um lado já existir, pula esse lado e avisa.
Não faz commit: depois de rodar, confira, edite e faça commit/push nos dois repositórios.

Onde fica o front: a pasta unidash-front ao lado da unidash-back (no Docker, /unidash-front,
montada pelo docker-compose). Para outro lugar: variável UNIDASH_FRONT_DIR.
"""

import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

PADRAO = re.compile(r"^[a-z][a-z0-9_]*$")
BACK = Path(__file__).resolve().parent.parent
MODELOS = Path(__file__).resolve().parent / "modelos_dashboard"
MARCA_IMPORTS = "// novo_dashboard: imports (o comando acrescenta aqui)"
MARCA_LISTA = "  // novo_dashboard: lista (o comando acrescenta aqui)"


def pasta_do_front() -> Path:
    return Path(os.environ.get("UNIDASH_FRONT_DIR") or BACK.parent / "unidash-front")


def buscar_no_banco(identificador: str) -> dict | None:
    """Hash, nome e páginas ativas (na ordem) do dashboard. None se não existir."""
    from sqlalchemy import text

    from app.db.sessao import obter_engine

    with obter_engine().connect() as conexao:
        d = conexao.execute(
            text("SELECT id, hash, nome FROM unidash.dashboard WHERE slug = :slug"), {"slug": identificador}
        ).mappings().first()
        if d is None:
            return None
        paginas = conexao.execute(
            text("SELECT codigo, nome FROM unidash.pagina WHERE dashboard_id = :id AND ativo ORDER BY ordem, id"),
            {"id": d["id"]},
        ).mappings().all()
    return {"identificador": identificador, "hash": d["hash"], "nome": d["nome"], "paginas": [dict(p) for p in paginas]}


def nome_de_componente(nome: str, usados: set[str]) -> str:
    """"Visão geral" -> "VisaoGeral" (nome de componente React: começa com maiúscula, sem acento). Sem repetir."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    base = "".join(parte[:1].upper() + parte[1:] for parte in re.split(r"[^A-Za-z0-9]+", sem_acento) if parte)
    if not base or not base[0].isalpha():
        base = f"Pagina{base}"
    componente, numero = base, 2
    while componente in usados:
        componente, numero = f"{base}{numero}", numero + 1
    usados.add(componente)
    return componente


def _com_componentes(dados: dict) -> list[dict]:
    """Páginas com o nome do componente de cada uma (VisaoGeral, Matriculas...)."""
    usados: set[str] = set()
    return [{**p, "componente": nome_de_componente(p["nome"], usados)} for p in dados["paginas"]]


def _preencher(modelo: str, dados: dict, pagina: dict | None = None) -> str:
    paginas = _com_componentes(dados)
    trocas = {
        "__IDENTIFICADOR__": dados["identificador"],
        "__HASH__": dados["hash"],
        "__NOME_TEXTO__": dados["nome"].replace('"', "'"),
        "__NOME__": json.dumps(dados["nome"], ensure_ascii=False),
        "__IMPORTS__": "\n".join(f"import {p['componente']} from './paginas/{p['componente']}.jsx'" for p in paginas),
        "__PAGINAS__": "\n".join(
            f"    {{ codigo: '{p['codigo']}', nome: {json.dumps(p['nome'], ensure_ascii=False)}, Conteudo: {p['componente']} }},"
            for p in paginas
        ),
        "__DATA__": date.today().strftime("%d/%m/%Y"),
    }
    if pagina:
        trocas |= {
            "__COMPONENTE__": pagina["componente"],
            "__NOME_PAGINA_TEXTO__": pagina["nome"].replace('"', "'"),
            "__CODIGO__": pagina["codigo"],
        }
    for marcador, valor in trocas.items():
        modelo = modelo.replace(marcador, valor)
    return modelo


def _escrever(arquivo: Path, conteudo: str) -> Path:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(conteudo, encoding="utf-8", newline="\n")
    return arquivo


def _criar_front(destino: Path, dados: dict) -> list[Path]:
    """config.js e tema.css uma vez; paginas/Pagina.jsx vira um arquivo por página."""
    modelos = MODELOS / "front"
    criados = [
        _escrever(destino / nome, _preencher((modelos / nome).read_text(encoding="utf-8"), dados))
        for nome in ("config.js", "tema.css")
    ]
    modelo_pagina = (modelos / "paginas" / "Pagina.jsx").read_text(encoding="utf-8")
    for pagina in _com_componentes(dados):
        conteudo = _preencher(modelo_pagina, dados, pagina)
        criados.append(_escrever(destino / "paginas" / f"{pagina['componente']}.jsx", conteudo))
    return criados


def _copiar_modelos(origem: Path, destino: Path, dados: dict) -> list[Path]:
    destino.mkdir(parents=True)
    criados = []
    for modelo in sorted(origem.iterdir()):
        arquivo = destino / modelo.name
        arquivo.write_text(_preencher(modelo.read_text(encoding="utf-8"), dados), encoding="utf-8", newline="\n")
        criados.append(arquivo)
    return criados


def registrar_no_front(front: Path, identificador: str) -> bool:
    """Acrescenta o import e a entrada em src/dashboards/registro.js. False se já estava registrado."""
    registro = front / "src" / "dashboards" / "registro.js"
    texto = registro.read_text(encoding="utf-8")
    variavel = f"dashboard_{identificador}"
    linha_import = f"import {variavel} from './{identificador}/config.js'"
    if linha_import in texto:
        return False
    if MARCA_IMPORTS not in texto or MARCA_LISTA not in texto:
        raise RuntimeError(f"Não achei as marcas do comando em {registro}. Registre o dashboard à mão.")
    texto = texto.replace(MARCA_IMPORTS, f"{linha_import}\n{MARCA_IMPORTS}")
    texto = texto.replace(MARCA_LISTA, f"  {variavel},\n{MARCA_LISTA}")
    registro.write_text(texto, encoding="utf-8", newline="\n")
    return True


def criar_pastas(dados: dict, front: Path, back: Path) -> list[str]:
    """Cria o que faltar nos dois lados. Devolve as mensagens para mostrar."""
    identificador = dados["identificador"]
    mensagens = []

    pasta_front = front / "src" / "dashboards" / identificador
    if pasta_front.exists():
        mensagens.append(f"Front: a pasta já existe, nada foi mudado ({pasta_front})")
    else:
        for arquivo in _criar_front(pasta_front, dados):
            mensagens.append(f"Front: criado {arquivo.relative_to(front).as_posix()}")
    if registrar_no_front(front, identificador):
        mensagens.append("Front: registrado em src/dashboards/registro.js")

    pasta_back = back / "app" / "dominios" / "dados" / identificador
    if pasta_back.exists():
        mensagens.append(f"Back:  a pasta já existe, nada foi mudado ({pasta_back})")
    else:
        for arquivo in _copiar_modelos(MODELOS / "back", pasta_back, dados):
            mensagens.append(f"Back:  criado {arquivo.relative_to(back).as_posix()}")
    return mensagens


def main() -> None:
    if len(sys.argv) != 2 or not PADRAO.fullmatch(sys.argv[1]):
        sys.exit("Informe o identificador do dashboard (está no Gerador). Ex.: python -m scripts.novo_dashboard executivo")
    identificador = sys.argv[1]

    front = pasta_do_front()
    if not (front / "src" / "dashboards" / "registro.js").exists():
        sys.exit(
            f"Não achei o unidash-front em {front}.\n"
            "No Docker: confira se o docker-compose monta ./unidash-front em /unidash-front (e rode docker compose up -d).\n"
            "Fora do Docker: a pasta unidash-front precisa estar ao lado da unidash-back, ou use UNIDASH_FRONT_DIR."
        )

    dados = buscar_no_banco(identificador)
    if dados is None:
        sys.exit(f"Não existe dashboard com o identificador \"{identificador}\". Crie primeiro no Gerador.")
    if not dados["paginas"]:
        sys.exit("O dashboard não tem páginas ativas. Cadastre ao menos uma no Gerador.")

    print(f"Dashboard \"{dados['nome']}\" ({identificador}), {len(dados['paginas'])} página(s)")
    for mensagem in criar_pastas(dados, front, BACK):
        print("  " + mensagem)
    print("\nPróximos passos: confira os arquivos, reinicie o back se ele não recarregar sozinho e faça commit/push nos dois repositórios.")


if __name__ == "__main__":
    main()
