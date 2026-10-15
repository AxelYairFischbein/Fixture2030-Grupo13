"""Schemas de equipos (CU-01, CU-02, CU-03). Campos según casos_de_uso.md §5."""

from enum import StrEnum

from pydantic import BaseModel

PATRON_EQUIPO = r"^EQ-\d{3}$"


class Confederacion(StrEnum):
    AFC = "AFC"
    CAF = "CAF"
    CONCACAF = "CONCACAF"
    CONMEBOL = "CONMEBOL"
    OFC = "OFC"
    UEFA = "UEFA"


class SedeBase(BaseModel):
    ciudad: str
    pais: str


class FichaEquipo(BaseModel):
    """CU-01. Sin _id, origen, esDatoSintetico, creadoEn ni actualizadoEn."""

    equipoId: str
    codigo: str
    nombre: str
    confederacion: Confederacion
    region: str
    rankingReferencia: int
    sedeBase: SedeBase
    participacionesMundiales: int
    titulosMundiales: int
    estado: str


class EquipoResumen(BaseModel):
    equipoId: str
    codigo: str
    nombre: str
    rankingReferencia: int


class PaginaEquipos(BaseModel):
    """CU-02. Orden rankingReferencia ASC, equipoId ASC."""

    items: list[EquipoResumen]
    pagina: int
    limite: int
    total: int