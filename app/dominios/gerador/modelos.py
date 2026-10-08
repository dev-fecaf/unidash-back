"""Formato dos dados que entram e saem do Gerador (cadastro de categorias, dashboards e páginas)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

Status = Literal["rascunho", "publicado", "desativado"]


def _nome(maximo: int):
    """Nome limpo: tira espaços das pontas, junta espaços repetidos e não aceita vazio."""

    def limpar(texto: str) -> str:
        limpo = " ".join(texto.split())
        if not limpo:
            raise ValueError("o nome não pode ficar vazio")
        if len(limpo) > maximo:
            raise ValueError(f"o nome pode ter no máximo {maximo} caracteres")
        return limpo

    return Annotated[str, AfterValidator(limpar)]


NomeCategoria = _nome(80)
NomeDashboard = _nome(120)
NomePagina = _nome(120)


# ---------------------------------------------------------------- categorias


class CategoriaIn(BaseModel):
    nome: NomeCategoria
    descricao: str | None = None


class CategoriaAlterarIn(CategoriaIn):
    ativo: bool = True


class OrdemCategoriasIn(BaseModel):
    ids: list[int] = Field(min_length=1)


class CategoriaOut(BaseModel):
    id: int
    slug: str  # identificador em minúsculas (só no banco; a tela mostra o nome)
    nome: str
    descricao: str | None
    ordem: int
    ativo: bool
    dashboards: int  # quantos dashboards não desativados usam a categoria


# ---------------------------------------------------------------- dashboards e páginas


class PaginaIn(BaseModel):
    codigo: str | None = None  # vazio = página nova; preenchido = página que já existe
    nome: NomePagina


class DashboardIn(BaseModel):
    nome: NomeDashboard
    descricao: str | None = None
    categoria_id: int
    status: Status = "rascunho"
    # Páginas na ordem em que devem aparecer. Página que existia e não veio = desativada.
    paginas: list[PaginaIn] = []


class PaginaOut(BaseModel):
    codigo: str
    nome: str
    ordem: int
    ativo: bool


class IdentificadorOut(BaseModel):
    slug: str  # identificador (= schema no DW) que o dashboard vai receber se for criado com este nome
    disponivel: bool = True  # False: o cadastro seria recusado (motivo explica)
    motivo: str | None = None


class DashboardResumo(BaseModel):
    hash: str
    slug: str
    nome: str
    categoria: str
    status: Status
    paginas: int
    responsavel_login: str | None
    atualizado_em: datetime


class SchemaDwOut(BaseModel):
    nome: str  # nome do schema no DW (o próprio identificador)
    situacao: Literal["existe", "nao_existe", "criado", "ja_existia", "desligado", "erro"]


class DashboardDetalhe(BaseModel):
    hash: str
    slug: str  # identificador em minúsculas; nunca muda
    nome: str
    descricao: str | None
    categoria_id: int
    categoria: str
    status: Status
    responsavel_login: str | None
    criado_em: datetime
    atualizado_em: datetime
    paginas: list[PaginaOut]  # ativas primeiro, na ordem; depois as desativadas
    schema_dw: SchemaDwOut | None = None  # schema do dashboard no DW e se ele existe (só no Gerador)
    schema_gravado: str | None = Field(default=None, exclude=True)  # coluna schema_dw (uso interno)
