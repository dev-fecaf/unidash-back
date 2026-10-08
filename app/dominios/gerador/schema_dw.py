"""Schema de cada dashboard no DW: o Gerador cria ao cadastrar e mostra se existe.

Regra (decidida em 08/10/2026):
- o nome do schema é o identificador (slug) do dashboard, sem prefixo. Ex.: "executivo";
- é criado vazio, junto com o cadastro; as tabelas e os dados entram depois (time de dados);
- se o schema já existir no DW, o UniDash não mexe nele (avisa "já existia");
- nunca apaga nem renomeia: desativar o dashboard não toca no DW, e o slug nunca muda;
- se o DW estiver desligado ou falhar, o cadastro do dashboard continua valendo e a tela
  mostra o botão "Criar agora" (POST /gerador/dashboards/{hash}/schema-dw).
Bancos diferentes: não dá para gravar dashboard e schema "tudo ou nada", por isso o schema
vem depois do commit do dashboard.
"""

import logging
from typing import Literal

from sqlalchemy import text

from app.db.dw import obter_engine_dw
from app.dominios.gerador.identificador import PADRAO_VALIDO, TAMANHO_MAXIMO, reservado

logger = logging.getLogger(__name__)

# existe / nao_existe: consulta; criado / ja_existia: resultado de criar;
# desligado: DW_HOST vazio; erro: o DW não respondeu ou recusou (detalhe só no log)
Situacao = Literal["existe", "nao_existe", "criado", "ja_existia", "desligado", "erro"]


def _nome_seguro(slug: str) -> str:
    """O nome entra no SQL (CREATE SCHEMA não aceita parâmetro): só passa o que segue a regra do slug."""
    if not PADRAO_VALIDO.fullmatch(slug) or len(slug) > TAMANHO_MAXIMO or reservado(slug):
        raise ValueError(f"identificador fora da regra para schema: {slug!r}")
    return slug


def _existe(conexao, slug: str) -> bool:
    return conexao.execute(
        text("SELECT 1 FROM pg_namespace WHERE nspname = :nome"), {"nome": slug}
    ).first() is not None


def consultar(slug: str) -> Situacao:
    """O schema do dashboard existe no DW?"""
    engine = obter_engine_dw()
    if engine is None:
        return "desligado"
    try:
        with engine.connect() as conexao:
            return "existe" if _existe(conexao, slug) else "nao_existe"
    except Exception:
        logger.exception("DW: não foi possível consultar o schema %s", slug)
        return "erro"


def criar(slug: str) -> Situacao:
    """Cria o schema vazio. Se já existir, não mexe."""
    engine = obter_engine_dw()
    if engine is None:
        return "desligado"
    try:
        nome = _nome_seguro(slug)
        with engine.connect() as conexao:
            if _existe(conexao, nome):
                logger.warning("DW: o schema %s já existia; o UniDash não mexeu nele", nome)
                return "ja_existia"
            conexao.execute(text(f'CREATE SCHEMA "{nome}"'))
            conexao.commit()
        logger.info("DW: schema %s criado", nome)
        return "criado"
    except Exception:
        logger.exception("DW: não foi possível criar o schema %s", slug)
        return "erro"
