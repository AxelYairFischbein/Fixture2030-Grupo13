"""Rutas de partidos sobre Neo4j (Hito 5): CU-06 y CU-07.

CU-05 (agenda de un equipo) cuelga de /equipos en app.routes.equipos.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.schemas.errores import respuestas_error
from app.schemas.partidos import (
    PATRON_ESTADIO,
    PATRON_PARTIDO,
    CalendarioPartidos,
    EventosPartido,
    InstanteUTC,
)
from app.services.partidos import ServicioPartidos, obtener_servicio_partidos

router = APIRouter(prefix="/api/v1/partidos", tags=["partidos"])

Servicio = Annotated[ServicioPartidos, Depends(obtener_servicio_partidos)]


@router.get(
    "",
    response_model=CalendarioPartidos,
    summary="CU-07 · Ver partidos de un rango de fechas",
    description="Rango semiabierto [desde, hasta) en UTC, de hasta 7 días. Orden inicio, "
                "partidoId. Intervalo o estadio sin partidos → items vacío. "
                "No incluye el estado del partido (fuente: IRIS, CU-18).",
    responses=respuestas_error(400, 500, 503, 504),
)
def listar_partidos(
    servicio: Servicio,
    desde: Annotated[InstanteUTC, Query(examples=["2030-06-10T00:00:00Z"])],
    hasta: Annotated[InstanteUTC, Query(examples=["2030-06-11T00:00:00Z"])],
    estadioId: Annotated[str | None, Query(pattern=PATRON_ESTADIO, examples=["EST-01"])] = None,
    limite: Annotated[int, Query(ge=1, le=64)] = 64,
) -> CalendarioPartidos:
    return servicio.por_fechas(desde, hasta, estadioId, limite)


@router.get(
    "/{partidoId}/eventos",
    response_model=EventosPartido,
    summary="CU-06 · Ver eventos y participantes de un partido",
    description="Orden minuto, eventoId; el límite cuenta eventos. Partido inexistente → 404; "
                "partido sin eventos → items vacío.",
    responses=respuestas_error(400, 404, 500, 503, 504, ejemplos={404: ["PARTIDO_NO_ENCONTRADO"]}),
)
def ver_eventos(
    partidoId: Annotated[str, Path(pattern=PATRON_PARTIDO, examples=["PAR-001"])],
    servicio: Servicio,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
) -> EventosPartido:
    return servicio.eventos(partidoId, limite)
