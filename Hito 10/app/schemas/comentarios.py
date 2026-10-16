"""Schemas de comentarios en Cassandra (CU-08, CU-09, CU-10, CU-20). Campos según casos_de_uso.md §5.

Toda fecha de salida se informa en UTC con milisegundos (la precisión de un timestamp de
Cassandra): el moderador reenvía creadoEn tal cual en CU-20 y debe coincidir con la clave.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer

from app.schemas.partidos import InstanteUTC

PATRON_USUARIO = r"^USR-\d{5}$"
# Los identificadores de la muestra del Hito 6 son MUESTRA-001; los nuevos, UUID.
PATRON_COMENTARIO = r"^[A-Za-z0-9-]{1,64}$"


def iso_ms(instante: datetime) -> str:
    """2030-06-10T18:00:20.000Z"""
    utc = instante.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


InstanteMs = Annotated[datetime, PlainSerializer(iso_ms, return_type=str)]


class EstadoComentario(StrEnum):
    VISIBLE = "visible"
    PENDIENTE = "pendiente"
    OCULTO = "oculto"


class EstadoModeracion(StrEnum):
    """Estados destino de CU-20: volver a pendiente no está permitido (400)."""

    VISIBLE = "visible"
    OCULTO = "oculto"


# Cursor "creadoEn|comentarioId" (CU-08 y CU-10)

@dataclass(frozen=True)
class Cursor:
    creado_en: datetime
    comentario_id: str

    def texto(self) -> str:
        return f"{iso_ms(self.creado_en)}|{self.comentario_id}"


def parsear_cursor(valor: str | None) -> Cursor | None:
    """ValueError si el cursor no tiene la forma creadoEn|comentarioId (→ 400)."""
    if valor is None:
        return None
    creado, separador, comentario_id = valor.partition("|")
    if not separador or not comentario_id or len(comentario_id) > 64 or not all(
        c.isascii() and (c.isalnum() or c == "-") for c in comentario_id
    ):
        raise ValueError("el cursor debe tener la forma creadoEn|comentarioId")
    try:
        instante = datetime.fromisoformat(creado)
    except ValueError:
        raise ValueError("creadoEn del cursor no es una fecha ISO-8601") from None
    if instante.tzinfo is None:
        raise ValueError("creadoEn del cursor debe tener zona horaria")
    return Cursor(instante.astimezone(UTC), comentario_id)


def _milisegundos_exactos(valor: datetime) -> datetime:
    if valor.microsecond % 1000:
        raise ValueError("creadoEn debe tener precisión de milisegundos")
    return valor


# CU-08

class ComentarioPartido(BaseModel):
    comentarioId: str
    usuarioId: str
    creadoEn: InstanteMs
    contenido: str
    estado: EstadoComentario
    likes: int


class ComentariosPartido(BaseModel):
    """CU-08. Orden creadoEn DESC, comentarioId ASC con límite global."""

    partidoId: str
    items: list[ComentarioPartido]
    siguienteCursor: str | None = Field(examples=["2030-06-10T18:01:20.000Z|MUESTRA-005"])


# CU-09

class NuevoComentario(BaseModel):
    """El servidor calcula usuarioId, creadoEn, minuto, segmento, dia, estado y likes."""

    model_config = ConfigDict(extra="forbid")

    contenido: str = Field(min_length=1, max_length=280, examples=["Gran jugada"])


class ComentarioCreado(BaseModel):
    comentarioId: str
    partidoId: str
    usuarioId: str
    creadoEn: InstanteMs
    contenido: str
    estado: EstadoComentario
    likes: int


# CU-10

class ComentarioUsuario(BaseModel):
    comentarioId: str
    partidoId: str
    creadoEn: InstanteMs
    contenido: str
    estado: EstadoComentario
    likes: int


class HistorialUsuario(BaseModel):
    """CU-10. Una sola partición (usuario_id, dia), en el orden del clustering."""

    usuarioId: str
    dia: date
    items: list[ComentarioUsuario]
    siguienteCursor: str | None


# CU-20

class Moderacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    creadoEn: Annotated[InstanteUTC, AfterValidator(_milisegundos_exactos)] = Field(
        examples=["2030-06-10T18:01:05.000Z"])
    estado: EstadoModeracion


class ComentarioModerado(BaseModel):
    comentarioId: str
    partidoId: str
    usuarioId: str
    creadoEn: InstanteMs
    estadoAnterior: EstadoComentario
    estado: EstadoComentario
    cambio: bool
