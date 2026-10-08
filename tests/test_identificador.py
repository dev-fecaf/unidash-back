"""Regra do identificador (slug) do dashboard."""

import pytest

from app.dominios.gerador.identificador import TAMANHO_MAXIMO, com_sufixo, gerar_slug


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("Executivo", "executivo"),
        ("Executivo Financeiro", "executivo_financeiro"),
        ("Matrículas & Evasão – 2026", "matriculas_evasao_2026"),
        ("  EAD   (Polos)  ", "ead_polos"),
        ("2026 Captação", "d_2026_captacao"),  # schema não pode começar com número
        ("Fat", "fat"),  # reservado: não ganha prefixo, o cadastro é que recusa
        ("Fatura", "fatura"),
        ("Ação-Social/Comunitária", "acao_social_comunitaria"),
        ("___", ""),
        ("!!!", ""),
    ],
)
def test_gerar_slug(nome, esperado):
    assert gerar_slug(nome) == esperado


def test_slug_respeita_o_tamanho_maximo_sem_terminar_em_underline():
    slug = gerar_slug("Indicadores " * 10)
    assert len(slug) <= TAMANHO_MAXIMO
    assert not slug.endswith("_")


def test_sufixo_respeita_o_tamanho_maximo():
    base = gerar_slug("a" * 80)
    assert com_sufixo(base, 2).endswith("_2")
    assert len(com_sufixo(base, 12)) <= TAMANHO_MAXIMO
