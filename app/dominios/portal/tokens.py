"""Ingresso do portal (entrada) e sessão de trabalho do time de dados.

Ingresso: JWT HS256 gerado pelo UniData quando a pessoa clica no card Dashboards.
    Vale 60 s, uso único, aud = "unidash", sub = usu_id. Assinado com PORTAL_INGRESSO_SECRET.
Sessão: JWT HS256 do próprio UniDash, guardado num cookie HttpOnly.
    Vale SESSAO_HORAS, aud = "unidash-sessao". Assinado com SESSAO_SECRET.
"""

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import obter_config

ALGORITMO = "HS256"
AUD_INGRESSO = "unidash"
AUD_SESSAO = "unidash-sessao"
VALIDADE_MAXIMA_INGRESSO = 60  # segundos
FOLGA_RELOGIO = 5  # segundos de tolerância entre os relógios dos servidores


class EntradaIndisponivel(Exception):
    """Os segredos da entrada pelo portal não estão configurados."""


class TokenInvalido(Exception):
    """Ingresso ou sessão inválido. A mensagem é o motivo real, só para o log."""


class _RegistroUsoUnico:
    """Lembra os ingressos já usados até eles vencerem, para não aceitar o mesmo duas vezes.

    Guarda na memória do processo: serve para o computador e para um único servidor.
    Antes de rodar com mais de uma instância, trocar pelo Redis (etapa 6).
    """

    def __init__(self):
        self._usados: dict[str, float] = {}
        self._trava = threading.Lock()

    def registrar(self, jti: str, expira_em: float) -> bool:
        """True na primeira vez que o jti aparece; False se já foi usado."""
        agora = time.time()
        with self._trava:
            self._usados = {j: exp for j, exp in self._usados.items() if exp + FOLGA_RELOGIO > agora}
            if jti in self._usados:
                return False
            self._usados[jti] = expira_em
            return True

    def limpar(self) -> None:
        with self._trava:
            self._usados.clear()


uso_unico = _RegistroUsoUnico()


def _segredo(nome: str) -> str:
    valor = getattr(obter_config(), nome).get_secret_value()
    if not valor:
        raise EntradaIndisponivel(f"{nome.upper()} não configurado")
    return valor


def validar_ingresso(token: str) -> uuid.UUID:
    """Confere o ingresso do portal e devolve o usu_id de quem entrou."""
    segredo = _segredo("portal_ingresso_secret")
    try:
        dados = jwt.decode(
            token,
            segredo,
            algorithms=[ALGORITMO],  # só HS256: recusa qualquer outro algoritmo
            audience=AUD_INGRESSO,
            leeway=FOLGA_RELOGIO,
            options={"require": ["exp", "iat", "sub", "jti", "aud"]},
        )
    except jwt.PyJWTError as erro:
        raise TokenInvalido(f"ingresso recusado: {erro}") from None

    if dados["exp"] - dados["iat"] > VALIDADE_MAXIMA_INGRESSO:
        raise TokenInvalido("ingresso com validade maior que 60 s")
    try:
        usu_id = uuid.UUID(str(dados["sub"]))
    except ValueError:
        raise TokenInvalido("ingresso com sub que não é um usu_id") from None

    # Só marca como usado depois de conferir a assinatura (um token falso não ocupa espaço)
    if not uso_unico.registrar(str(dados["jti"]), float(dados["exp"])):
        raise TokenInvalido("ingresso já usado")
    return usu_id


def criar_sessao(usu_id: uuid.UUID) -> tuple[str, int]:
    """Devolve (token da sessão, duração em segundos)."""
    config = obter_config()
    duracao = config.sessao_horas * 3600
    agora = datetime.now(timezone.utc)
    dados = {
        "sub": str(usu_id),
        "aud": AUD_SESSAO,
        "iat": agora,
        "exp": agora + timedelta(seconds=duracao),
    }
    return jwt.encode(dados, _segredo("sessao_secret"), algorithm=ALGORITMO), duracao


def ler_sessao(token: str) -> uuid.UUID:
    """Confere a sessão e devolve o usu_id dela."""
    try:
        dados = jwt.decode(
            token,
            _segredo("sessao_secret"),
            algorithms=[ALGORITMO],
            audience=AUD_SESSAO,
            options={"require": ["exp", "sub", "aud"]},
        )
        return uuid.UUID(str(dados["sub"]))
    except (jwt.PyJWTError, ValueError) as erro:
        raise TokenInvalido(f"sessão recusada: {erro}") from None
