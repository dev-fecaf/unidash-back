"""Identificador (slug) do dashboard, gerado a partir do nome.

Exemplo: "Executivo Financeiro – 2026" → "executivo_financeiro_2026"

É usado no banco (coluna unidash.dashboard.slug), na pasta do dashboard no front
(src/dashboards/<slug>/) e no schema do dashboard no DW (dash_<slug>). Por isso:
- só letras minúsculas sem acento, números e "_" (o banco não aceita "-" em nome de schema sem aspas);
- começa com letra;
- no máximo 50 caracteres (o schema "dash_" + slug cabe no limite de 63 do PostgreSQL);
- é gerado uma vez, no cadastro, e nunca muda (o banco também impede, por trigger).

A mesma regra existe no front (src/paginas/area/gerador/identificador.js) para a prévia em tempo real.
Se mudar aqui, mude lá também.
"""

import re
import unicodedata

TAMANHO_MAXIMO = 50
PADRAO_VALIDO = re.compile(r"^[a-z][a-z0-9_]*$")


def gerar_slug(nome: str) -> str:
    """Converte o nome no identificador. Devolve "" se não sobrar nenhuma letra ou número."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")
    if not texto:
        return ""
    if not texto[0].isalpha():
        texto = f"d_{texto}"  # schema não pode começar com número
    return texto[:TAMANHO_MAXIMO].rstrip("_")


def com_sufixo(base: str, numero: int) -> str:
    """base + "_2", "_3"... respeitando o tamanho máximo."""
    sufixo = f"_{numero}"
    return base[: TAMANHO_MAXIMO - len(sufixo)].rstrip("_") + sufixo
