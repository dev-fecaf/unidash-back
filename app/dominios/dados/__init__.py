"""Endpoints de dados dos dashboards: uma pasta por dashboard, app/dominios/dados/<identificador>/.

Cada pasta tem um rotas.py com um `router`. Este arquivo encontra todas as pastas e junta os
roteadores num só, incluído no app em /api/v1/dados. Pasta nova (criada pelo comando
novo_dashboard) não precisa mexer no main.py.
"""

import importlib
import pkgutil

from fastapi import APIRouter

router = APIRouter(prefix="/dados")

for _modulo in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
    if _modulo.ispkg:
        router.include_router(importlib.import_module(f"{__name__}.{_modulo.name}.rotas").router)
