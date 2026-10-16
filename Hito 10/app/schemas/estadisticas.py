"""Schemas de estadísticas temporales en InfluxDB (CU-15, CU-16, CU-17). Campos según
casos_de_uso.md §5.

Las fechas salen en UTC con sufijo Z. Un valor ausente (sin muestras o sin incrementos
válidos) se informa null: no se rellena con ceros, porque cero es una medida distinta.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Resolucion(StrEnum):
    """Tamaño de los intervalos de CU-17."""

    UN_MINUTO = "1m"
    CINCO_MINUTOS = "5m"


class Observacion(BaseModel):
    time: datetime
    posesionPct: float | None
    pasesAcumulados: int | None
    tirosIntervalo: int | None


class EstadoReciente(BaseModel):
    """CU-15. items en orden time DESC; ultimaObservacion = time del primer ítem o null."""

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "partidoId": "PAR-001", "equipoId": "EQ-001", "estadioId": "EST-01",
        "items": [
            {"time": "2026-10-16T00:16:59Z", "posesionPct": 46.5, "pasesAcumulados": 539,
             "tirosIntervalo": 0},
            {"time": "2026-10-16T00:16:58Z", "posesionPct": 46.0, "pasesAcumulados": 539,
             "tirosIntervalo": 0},
        ],
        "ultimaObservacion": "2026-10-16T00:16:59Z",
    }]})

    partidoId: str
    equipoId: str
    estadioId: str | None
    items: list[Observacion]
    ultimaObservacion: datetime | None


class Medidas(BaseModel):
    """Agregaciones comunes de CU-16 y CU-17 (Hito 8)."""

    muestras: int
    muestrasEsperadas: int
    posesionMedia: float | None
    pasesNuevos: int | None
    tiros: int | None
    intervalosInvalidos: int
    completo: bool


class ComparacionEquipo(Medidas):
    equipoId: str


class ComparacionPartido(BaseModel):
    """CU-16. Una fila por equipo, orden equipoId."""

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "partidoId": "PAR-001", "desde": "2026-10-16T00:12:00Z", "hasta": "2026-10-16T00:17:00Z",
        "equipos": [
            {"equipoId": "EQ-001", "muestras": 300, "muestrasEsperadas": 300,
             "posesionMedia": 49.975, "pasesNuevos": 30, "tiros": 1, "intervalosInvalidos": 0,
             "completo": True},
            {"equipoId": "EQ-002", "muestras": 300, "muestrasEsperadas": 300,
             "posesionMedia": 50.025, "pasesNuevos": 25, "tiros": 1, "intervalosInvalidos": 0,
             "completo": True},
        ],
    }]})

    partidoId: str
    desde: datetime
    hasta: datetime
    equipos: list[ComparacionEquipo]


class IntervaloEvolucion(Medidas):
    inicio: datetime


class SerieEquipo(BaseModel):
    equipoId: str
    intervalos: list[IntervaloEvolucion]


class EvolucionPartido(BaseModel):
    """CU-17. Series en orden equipoId; intervalos en orden inicio."""

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "partidoId": "PAR-001", "desde": "2026-10-16T00:12:00Z", "hasta": "2026-10-16T00:17:00Z",
        "resolucion": "1m",
        "series": [
            {"equipoId": "EQ-001", "intervalos": [
                {"inicio": "2026-10-16T00:12:00Z", "muestras": 60, "muestrasEsperadas": 60,
                 "posesionMedia": 49.825, "pasesNuevos": 6, "tiros": 0,
                 "intervalosInvalidos": 0, "completo": True},
            ]},
        ],
    }]})

    partidoId: str
    desde: datetime
    hasta: datetime
    resolucion: Resolucion
    series: list[SerieEquipo]
