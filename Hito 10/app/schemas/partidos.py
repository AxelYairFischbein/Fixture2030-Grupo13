"""Schemas de partidos en Neo4j (CU-05, CU-06, CU-07). Campos según casos_de_uso.md §5.

Ninguna respuesta incluye el estado del partido: su fuente es IRIS (§3.1, CU-18).
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel

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

    items: list[PartidoCalendario]
