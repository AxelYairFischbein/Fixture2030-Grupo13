"""Schemas de GET /api/v1/salud."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class EstadoDependencia(StrEnum):
    DISPONIBLE = "disponible"
    NO_DISPONIBLE = "no_disponible"
    NO_CONFIGURADA = "no_configurada"


class Dependencias(BaseModel):
    mongodb: EstadoDependencia
    neo4j: EstadoDependencia
    cassandra: EstadoDependencia
    redis: EstadoDependencia
    influxdb: EstadoDependencia
    iris: EstadoDependencia


class EstadoCatalogo(StrEnum):
    CARGADO = "cargado"
    NO_CARGADO = "no_cargado"


class CatalogoPartidos(BaseModel):
    """Catálogo de partidos en memoria (casos_de_uso.md §3.2)."""

    estado: EstadoCatalogo
    partidos: int
    ultimaCarga: datetime | None


class RespuestaSalud(BaseModel):
    estado: str
    dependencias: Dependencias
    catalogoPartidos: CatalogoPartidos
