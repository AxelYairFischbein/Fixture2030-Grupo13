"""Schemas del acta del partido en IRIS (CU-18, CU-19). Campos según casos_de_uso.md §5.

IRIS es la única fuente del estado del partido (§3.1). No se exponen IDs internos
(%ID), la licencia del árbitro ni nombres de clases.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EstadoPartido(StrEnum):
    PENDIENTE = "PENDIENTE"
    EN_JUEGO = "EN_JUEGO"
    FINALIZADO = "FINALIZADO"


class EstadoDestino(StrEnum):
    """Estados que acepta CU-19: volver a PENDIENTE nunca es una transición válida."""

    EN_JUEGO = "EN_JUEGO"
    FINALIZADO = "FINALIZADO"


class TipoEventoActa(StrEnum):
    GOL = "GOL"
    TARJETA = "TARJETA"
    CAMBIO = "CAMBIO"


class ArbitroActa(BaseModel):
    codigo: str = Field(examples=["ARB-001"])
    nombre: str = Field(examples=["Arbitro Sintetico 01"])
    nacionalidad: str = Field(examples=["F01"])


class JugadorActa(BaseModel):
    codigo: str = Field(examples=["JUG-0001"])
    nombre: str = Field(examples=["Nombre0001 Apellido0001"])
    numero: int = Field(examples=[1])
    posicion: str = Field(examples=["ARQUERO"])


class EventoActa(BaseModel):
    tipo: TipoEventoActa
    minuto: int = Field(examples=[15])
    jugador: JugadorActa


class ActaPartido(BaseModel):
    partidoId: str = Field(examples=["PAR-001"])
    estadioId: str = Field(examples=["EST-01"])
    estado: EstadoPartido
    arbitro: ArbitroActa
    eventos: list[EventoActa]


class SolicitudTransicion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nuevoEstado: EstadoDestino = Field(examples=["EN_JUEGO"])


class ResultadoTransicion(BaseModel):
    partidoId: str = Field(examples=["PAR-001"])
    estadoAnterior: EstadoPartido
    estadoActual: EstadoPartido
    cambio: bool
