"""Schemas de jugadores (CU-03, CU-04). Campos según casos_de_uso.md §5."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel

PATRON_JUGADOR = r"^JUG-\d{4}$"


class Posicion(StrEnum):
    ARQUERO = "ARQUERO"
    DEFENSOR = "DEFENSOR"
    MEDIOCAMPISTA = "MEDIOCAMPISTA"
    DELANTERO = "DELANTERO"


class JugadorPlantel(BaseModel):
    jugadorId: str
    nombre: str
    apellido: str
    posicion: Posicion
    numeroCamiseta: int
    estadoPlantel: str


class PlantelEquipo(BaseModel):
    """CU-03. Orden apellido, nombre, jugadorId."""

    equipoId: str
    items: list[JugadorPlantel]
    pagina: int
    limite: int
    total: int


class FichaJugador(BaseModel):
    """CU-04. Sin _id ni campos de control. fechaNacimiento en ISO-8601 (YYYY-MM-DD)."""

    jugadorId: str
    equipoId: str
    nombre: str
    apellido: str
    fechaNacimiento: date
    nacionalidadCodigo: str
    posicion: Posicion
    numeroCamiseta: int
    pieHabil: str
    alturaCm: int
    partidosInternacionales: int
    golesInternacionales: int
    estadoPlantel: str
