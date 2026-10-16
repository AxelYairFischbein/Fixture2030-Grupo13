"""Schemas de jugadores (CU-03, CU-04). Campos según casos_de_uso.md §5."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

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

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "equipoId": "EQ-002",
        "items": [
            {"jugadorId": "JUG-0025", "nombre": "Nombre0025", "apellido": "Apellido0025",
             "posicion": "ARQUERO", "numeroCamiseta": 1, "estadoPlantel": "CONVOCADO"},
            {"jugadorId": "JUG-0026", "nombre": "Nombre0026", "apellido": "Apellido0026",
             "posicion": "ARQUERO", "numeroCamiseta": 2, "estadoPlantel": "CONVOCADO"},
        ],
        "pagina": 1, "limite": 2, "total": 24,
    }]})

    equipoId: str
    items: list[JugadorPlantel]
    pagina: int
    limite: int
    total: int


class FichaJugador(BaseModel):
    """CU-04. Sin _id ni campos de control. fechaNacimiento en ISO-8601 (YYYY-MM-DD)."""

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "jugadorId": "JUG-0313", "equipoId": "EQ-014", "nombre": "Nombre0313",
        "apellido": "Apellido0313", "fechaNacimiento": "2004-01-26", "nacionalidadCodigo": "F14",
        "posicion": "ARQUERO", "numeroCamiseta": 1, "pieHabil": "DERECHO", "alturaCm": 187,
        "partidosInternacionales": 19, "golesInternacionales": 1, "estadoPlantel": "CONVOCADO",
    }]})

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
