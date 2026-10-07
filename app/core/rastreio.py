"""Rastreio: dá um código único (trace_id) a cada pedido feito ao back.

O código aparece no cabeçalho X-Trace-Id da resposta, no corpo dos erros e em cada
linha de log. Assim, um erro relatado por alguém pode ser achado no log do servidor.
"""

import logging
import uuid
from contextvars import ContextVar

CABECALHO_TRACE_ID = "X-Trace-Id"

_trace_id_atual: ContextVar[str | None] = ContextVar("trace_id", default=None)


def obter_trace_id() -> str | None:
    """Devolve o trace_id do pedido em andamento (ou None fora de um pedido)."""
    return _trace_id_atual.get()


class MiddlewareRastreio:
    """Gera o trace_id no início de cada pedido e o devolve no cabeçalho da resposta."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace_id = uuid.uuid4().hex
        _trace_id_atual.set(trace_id)

        async def enviar_com_trace_id(mensagem):
            if mensagem["type"] == "http.response.start":
                cabecalhos = list(mensagem.get("headers", []))
                if not any(nome.lower() == CABECALHO_TRACE_ID.lower().encode() for nome, _ in cabecalhos):
                    cabecalhos.append((CABECALHO_TRACE_ID.encode(), trace_id.encode()))
                mensagem["headers"] = cabecalhos
            await send(mensagem)

        await self.app(scope, receive, enviar_com_trace_id)


class _FiltroTraceId(logging.Filter):
    """Coloca o trace_id em cada linha de log ('-' quando não há pedido em andamento)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = obter_trace_id() or "-"
        return True


def configurar_logs() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(trace_id)s] %(name)s: %(message)s",
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(_FiltroTraceId())
