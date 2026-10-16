"""Schemas de equipos (CU-01, CU-02, CU-03). Campos según casos_de_uso.md §5."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

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

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "equipoId": "EQ-001", "codigo": "F01", "nombre": "Seleccion Sintetica 01",
        "confederacion": "AFC", "region": "ASIA_PACIFICO", "rankingReferencia": 1,
        "sedeBase": {"ciudad": "Ciudad Sintetica 01", "pais": "Pais Sintetico 01"},
        "participacionesMundiales": 1, "titulosMundiales": 0, "estado": "PRESELECCIONADO",
    }]})

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

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "items": [
            {"equipoId": "EQ-004", "codigo": "F04", "nombre": "Seleccion Sintetica 04",
             "rankingReferencia": 4},
            {"equipoId": "EQ-010", "codigo": "F10", "nombre": "Argentina", "rankingReferencia": 10},
        ],
        "pagina": 1, "limite": 2, "total": 8,
    }]})

    items: list[EquipoResumen]
    pagina: int
    limite: int
    total: int