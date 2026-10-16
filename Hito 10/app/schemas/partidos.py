"""Schemas de partidos en Neo4j (CU-05, CU-06, CU-07). Campos según casos_de_uso.md §5.

Ninguna respuesta incluye el estado del partido: su fuente es IRIS (§3.1, CU-18).
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict

PATRON_PARTIDO = r"^PAR-\d{3}$"
PATRON_ESTADIO = r"^EST-\d{2}$"


def _a_utc(valor: datetime) -> datetime:
    return valor.astimezone(UTC)


# Fecha ISO-8601 con zona obligatoria (sin zona → 400), normalizada a UTC.
# Reutilizable por comentarios (fase 5) y estadísticas (fase 6).
InstanteUTC = Annotated[AwareDatetime, AfterValidator(_a_utc)]


class RolPartido(StrEnum):
    LOCAL = "LOCAL"
    VISITANTE = "VISITANTE"


class RolParticipante(StrEnum):
    SALE = "SALE"
    ENTRA = "ENTRA"


class EquipoRival(BaseModel):
    equipoId: str
    codigo: str
    nombre: str


def _estadio(n: int) -> dict:
    """Estadio de la muestra del Hito 5 (02_load.cypher, L03), para los ejemplos."""
    return {"estadioId": f"EST-{n:02d}", "nombre": f"Estadio Sintetico {n:02d}",
            "ciudad": f"Ciudad Sede {n:02d}"}


class EstadioResumen(BaseModel):
    estadioId: str
    nombre: str
    ciudad: str


class PartidoAgenda(BaseModel):
    partidoId: str
    inicio: datetime
    grupo: str
    fase: str
    rol: RolPartido
    rival: EquipoRival
    estadio: EstadioResumen


class AgendaEquipo(BaseModel):
    """CU-05. Orden inicio ASC, partidoId ASC."""

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "equipoId": "EQ-001",
        "items": [
            {"partidoId": "PAR-001", "inicio": "2030-06-10T18:00:00Z", "grupo": "G01",
             "fase": "GRUPOS_MUESTRA", "rol": "LOCAL",
             "rival": {"equipoId": "EQ-002", "codigo": "F02", "nombre": "Seleccion Sintetica 02"},
             "estadio": _estadio(1)},
            {"partidoId": "PAR-033", "inicio": "2030-06-14T18:00:00Z", "grupo": "G01",
             "fase": "GRUPOS_MUESTRA", "rol": "LOCAL",
             "rival": {"equipoId": "EQ-003", "codigo": "F03", "nombre": "Seleccion Sintetica 03"},
             "estadio": _estadio(1)},
        ],
    }]})

    equipoId: str
    items: list[PartidoAgenda]


class Participante(BaseModel):
    jugadorId: str
    nombre: str
    apellido: str
    equipoId: str
    rol: RolParticipante


class EventoPartido(BaseModel):
    eventoId: str
    tipo: str
    minuto: int
    participantes: list[Participante]


class EventosPartido(BaseModel):
    """CU-06. Orden minuto ASC, eventoId ASC; participantes SALE, ENTRA."""

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "partidoId": "PAR-001",
        "items": [
            {"eventoId": "EVT-PAR-001-LOCAL", "tipo": "SUSTITUCION", "minuto": 60,
             "participantes": [
                 {"jugadorId": "JUG-0020", "nombre": "Nombre0020", "apellido": "Apellido0020",
                  "equipoId": "EQ-001", "rol": "SALE"},
                 {"jugadorId": "JUG-0021", "nombre": "Nombre0021", "apellido": "Apellido0021",
                  "equipoId": "EQ-001", "rol": "ENTRA"},
             ]},
            {"eventoId": "EVT-PAR-001-VISITANTE", "tipo": "SUSTITUCION", "minuto": 65,
             "participantes": [
                 {"jugadorId": "JUG-0044", "nombre": "Nombre0044", "apellido": "Apellido0044",
                  "equipoId": "EQ-002", "rol": "SALE"},
                 {"jugadorId": "JUG-0045", "nombre": "Nombre0045", "apellido": "Apellido0045",
                  "equipoId": "EQ-002", "rol": "ENTRA"},
             ]},
        ],
    }]})

    partidoId: str
    items: list[EventoPartido]


class PartidoCalendario(BaseModel):
    partidoId: str
    inicio: datetime
    grupo: str
    fase: str
    estadio: EstadioResumen


class CalendarioPartidos(BaseModel):
    """CU-07. Orden inicio, partidoId."""

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "items": [
            {"partidoId": "PAR-001", "inicio": "2030-06-10T18:00:00Z", "grupo": "G01",
             "fase": "GRUPOS_MUESTRA", "estadio": _estadio(1)},
            {"partidoId": "PAR-002", "inicio": "2030-06-10T18:00:00Z", "grupo": "G01",
             "fase": "GRUPOS_MUESTRA", "estadio": _estadio(2)},
        ],
    }]})

    items: list[PartidoCalendario]
