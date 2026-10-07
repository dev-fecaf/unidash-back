"""Token do Hub (abertura do dashboard) e sessão do embed.

Token do Hub: JWT HS256 assinado com EMBED_HUB_SECRET, vale 60 s, uso único.
    Campos obrigatórios: dash (hash), sub (login), exp, jti. Opcionais: name, email,
    setores (lista dos setores da pessoa que dão acesso ao dashboard) e paginas (códigos das
    páginas liberadas; ainda em aberto com o Hub). Formato em docs/integracao-hub.md.
Sessão do embed: JWT HS256 do próprio UniDash (assinado com SESSAO_SECRET), vale
    EMBED_SESSAO_MINUTOS, só para um dashboard e só para as páginas liberadas.
    Sem cookie (dentro de iframe o navegador pode bloquear): a página guarda na memória
    e envia no cabeçalho Authorization de cada chamada.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import obter_config
from app.dominios.portal.tokens import FOLGA_RELOGIO, _RegistroUsoUnico

ALGORITMO = "HS256"
AUD_SESSAO_EMBED = "unidash-embed"
VALIDADE_MAXIMA_TOKEN = 60  # segundos

# Tokens do Hub já usados (na memória; trocar pelo Redis antes de rodar com mais de uma instância)
uso_unico_hub = _RegistroUsoUnico()


class EmbedIndisponivel(Exception):
    """EMBED_HUB_SECRET ou SESSAO_SECRET não configurado."""


class TokenInvalido(Exception):
    """Token do Hub ou sessão inválido. A mensagem é o motivo real, só para o log."""


@dataclass(frozen=True)
class PessoaDoHub:
    login: str
    nome: str | None
    email: str | None
    setores: list[str] | None  # None = o Hub não mandou
    jti: str
    paginas: list[str] | None  # None = o Hub não restringiu páginas (todas as ativas)


def _segredo(nome: str) -> str:
    valor = getattr(obter_config(), nome).get_secret_value()
    if not valor:
        raise EmbedIndisponivel(f"{nome.upper()} não configurado")
    return valor


def _texto(valor, limite: int) -> str | None:
    """Campo de texto opcional: corta no tamanho da coluna do banco; outro tipo vira vazio."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    return valor.strip()[:limite]


def _setores(valor) -> list[str] | None:
    """Lista de setores (cada um até 120 caracteres, sem repetir). Fora do formato: ignorado, não bloqueia."""
    if isinstance(valor, str):  # aceita também um texto só
        valor = [valor]
    if not isinstance(valor, list):
        return None
    limpos = list(dict.fromkeys(t for t in (_texto(v, 120) for v in valor) if t))
    return limpos[:50] or None


def validar_token_hub(token: str, hash_: str) -> PessoaDoHub:
    """Confere o token que o Hub mandou para abrir o dashboard `hash_`."""
    segredo = _segredo("embed_hub_secret")
    try:
        dados = jwt.decode(
            token,
            segredo,
            algorithms=[ALGORITMO],  # só HS256: recusa qualquer outro algoritmo
            leeway=FOLGA_RELOGIO,
            options={"require": ["exp", "sub", "dash", "jti"], "verify_aud": False},
        )
    except jwt.PyJWTError as erro:
        raise TokenInvalido(f"token do Hub recusado: {erro}") from None

    # O token vale no máximo 60 s (com ou sem "iat")
    if dados["exp"] - time.time() > VALIDADE_MAXIMA_TOKEN + FOLGA_RELOGIO:
        raise TokenInvalido("token do Hub com validade maior que 60 s")
    if "iat" in dados and dados["exp"] - dados["iat"] > VALIDADE_MAXIMA_TOKEN:
        raise TokenInvalido("token do Hub com validade maior que 60 s")
    if dados["dash"] != hash_:
        raise TokenInvalido(f"token do Hub é do dashboard {dados['dash']!r}, mas o link aberto é {hash_!r}")

    login = str(dados["sub"]).strip()
    if not login or len(login) > 80:
        raise TokenInvalido("token do Hub com sub vazio ou maior que 80 caracteres")

    paginas = dados.get("paginas")
    if paginas is not None and (not isinstance(paginas, list) or not all(isinstance(p, str) for p in paginas)):
        raise TokenInvalido("token do Hub com campo paginas fora do formato (lista de códigos)")

    # Só marca como usado depois de conferir a assinatura (um token falso não ocupa espaço)
    if not uso_unico_hub.registrar(str(dados["jti"]), float(dados["exp"])):
        raise TokenInvalido("token do Hub já usado")

    return PessoaDoHub(
        login=login,
        nome=_texto(dados.get("name"), 120),
        email=_texto(dados.get("email"), 160),
        setores=_setores(dados.get("setores")),
        jti=str(dados["jti"])[:64],
        paginas=paginas,
    )


def criar_sessao_embed(hash_: str, login: str, paginas: list[str]) -> tuple[str, int]:
    """Devolve (sessão, duração em segundos). `paginas` = códigos liberados para a pessoa."""
    duracao = obter_config().embed_sessao_minutos * 60
    agora = datetime.now(timezone.utc)
    dados = {
        "sub": login,
        "aud": AUD_SESSAO_EMBED,
        "dash": hash_,
        "pags": paginas,
        "iat": agora,
        "exp": agora + timedelta(seconds=duracao),
    }
    return jwt.encode(dados, _segredo("sessao_secret"), algorithm=ALGORITMO), duracao


def ler_sessao_embed(token: str) -> dict:
    """Confere a sessão do embed e devolve os dados dela (sub, dash, pags)."""
    try:
        dados = jwt.decode(
            token,
            _segredo("sessao_secret"),
            algorithms=[ALGORITMO],
            audience=AUD_SESSAO_EMBED,
            options={"require": ["exp", "sub", "dash", "pags", "aud"]},
        )
    except jwt.PyJWTError as erro:
        raise TokenInvalido(f"sessão do embed recusada: {erro}") from None
    return dados
