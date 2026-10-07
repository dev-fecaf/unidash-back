"""Padrão de erros do UniDash (RFC 9457, "application/problem+json").

Todo erro volta no mesmo formato:
    {"type": "about:blank", "title": "...", "status": 404, "detail": "...", "trace_id": "..."}

Quem chama o back nunca vê detalhes técnicos; o motivo real vai só para o log,
junto com o mesmo trace_id.
"""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.rastreio import CABECALHO_TRACE_ID, obter_trace_id

logger = logging.getLogger(__name__)

TIPO_CONTEUDO = "application/problem+json"

TITULOS = {
    400: "Requisição inválida",
    401: "Não autenticado",
    403: "Acesso negado",
    404: "Não encontrado",
    405: "Método não permitido",
    409: "Conflito",
    422: "Dados inválidos",
    429: "Muitas tentativas",
    500: "Erro interno",
    503: "Serviço indisponível",
}


def resposta_problema(status: int, detail: str | None = None, **extras) -> JSONResponse:
    """Monta uma resposta de erro no padrão RFC 9457, sempre com trace_id."""
    trace_id = obter_trace_id()
    corpo = {
        "type": "about:blank",
        "title": TITULOS.get(status) or HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "trace_id": trace_id,
        **extras,
    }
    cabecalhos = {CABECALHO_TRACE_ID: trace_id} if trace_id else None
    return JSONResponse(status_code=status, content=corpo, media_type=TIPO_CONTEUDO, headers=cabecalhos)


async def _erro_http(request: Request, erro: StarletteHTTPException) -> JSONResponse:
    detalhe = erro.detail if isinstance(erro.detail, str) else None
    # Registra no log com o trace_id, para o código mostrado na tela ser encontrado aqui
    logger.info("%s %s respondeu %s: %s", request.method, request.url.path, erro.status_code, detalhe)
    resposta = resposta_problema(erro.status_code, detalhe)
    if erro.headers:
        resposta.headers.update(erro.headers)
    return resposta


async def _erro_validacao(request: Request, erro: RequestValidationError) -> JSONResponse:
    campos = [
        {"campo": ".".join(str(parte) for parte in e["loc"]), "mensagem": e["msg"]}
        for e in erro.errors()
    ]
    logger.info("%s %s respondeu 422: %s", request.method, request.url.path, campos)
    return resposta_problema(422, "Algum dado enviado está faltando ou em formato errado.", erros=campos)


async def _erro_inesperado(request: Request, erro: Exception) -> JSONResponse:
    logger.exception("Erro inesperado em %s %s", request.method, request.url.path)
    return resposta_problema(500, "Ocorreu um erro inesperado. Informe o trace_id ao time de dados.")


def registrar_tratadores_de_erro(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _erro_http)
    app.add_exception_handler(RequestValidationError, _erro_validacao)
    app.add_exception_handler(Exception, _erro_inesperado)
