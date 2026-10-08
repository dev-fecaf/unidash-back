"""Ponto de partida do back do UniDash: cria a aplicação e registra as rotas."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import obter_config
from app.core.erros import registrar_tratadores_de_erro
from app.core.rastreio import MiddlewareRastreio, configurar_logs
from app.dominios.analises.rotas import router as analises_router
from app.dominios.dados import router as dados_router
from app.dominios.embed.rotas import router as embed_router
from app.dominios.galeria.rotas import router as galeria_router
from app.dominios.gerador.rotas import router as gerador_router
from app.dominios.inicio.rotas import router as inicio_router
from app.dominios.portal.rotas import router as portal_router
from app.dominios.saude.rotas import router as saude_router

configurar_logs()


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    # Lê o .env logo ao ligar: se faltar algo, o back não sobe e diz o que falta
    obter_config()
    yield


app = FastAPI(title="UniDash API", version="0.1.0", lifespan=ciclo_de_vida)

app.add_middleware(MiddlewareRastreio)
registrar_tratadores_de_erro(app)

app.include_router(saude_router, prefix="/api/v1")
app.include_router(portal_router, prefix="/api/v1")
app.include_router(galeria_router, prefix="/api/v1")
app.include_router(inicio_router, prefix="/api/v1")
app.include_router(analises_router, prefix="/api/v1")
app.include_router(gerador_router, prefix="/api/v1")
app.include_router(embed_router, prefix="/api/v1")
app.include_router(dados_router, prefix="/api/v1")  # endpoints de cada dashboard
