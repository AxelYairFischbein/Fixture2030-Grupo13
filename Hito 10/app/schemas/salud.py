"""Schemas de GET /api/v1/salud."""

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


class RespuestaSalud(BaseModel):
    estado: str
    dependencias: Dependencias
