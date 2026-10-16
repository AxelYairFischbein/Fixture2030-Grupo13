"""Rutas de equipos: CU-01 (Redis + MongoDB), CU-02 y CU-03 (MongoDB, Hito 4) y
CU-05 (Neo4j, Hito 5)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from app.schemas.equipos import PATRON_EQUIPO, Confederacion, FichaEquipo, PaginaEquipos
from app.schemas.errores import respuestas_error
from app.schemas.jugadores import PlantelEquipo, Posicion
from app.schemas.partidos import AgendaEquipo
from app.services.equipos import ServicioEquipos, obtener_servicio_equipos
from app.services.partidos import ServicioPartidos, obtener_servicio_partidos

router = APIRouter(prefix="/api/v1/equipos", tags=["equipos"])

Servicio = Annotated[ServicioEquipos, Depends(obtener_servicio_equipos)]
EquipoId = Annotated[str, Path(pattern=PATRON_EQUIPO, examples=["EQ-001"])]
Pagina = Annotated[int, Query(ge=1, description="Número de página, desde 1.")]

ENCABEZADO_CACHE = {
    "X-Cache": {
        "description": "HIT: copia de Redis. MISS: leída de MongoDB y guardada por 300 s. "
                       "BYPASS: Redis no disponible, leída de MongoDB sin caché.",
        "schema": {"type": "string", "enum": ["HIT", "MISS", "BYPASS"]},
    }
}


@router.get(
    "",
    response_model=PaginaEquipos,
    summary="CU-02 · Listar equipos de una confederación",
    description="Orden rankingReferencia ASC, equipoId ASC. Sin coincidencias → items vacío.",
    responses=respuestas_error(400, 500, 503, 504),
)
def listar_equipos(
    servicio: Servicio,
    confederacion: Annotated[Confederacion, Query()],
    rankingMax: Annotated[int | None, Query(ge=1, le=250)] = None,
    limite: Annotated[int, Query(ge=1, le=50)] = 20,
    pagina: Pagina = 1,
) -> PaginaEquipos:
    return servicio.listar(confederacion.value, rankingMax, pagina, limite)


@router.get(
    "/{equipoId}",
    response_model=FichaEquipo,
    summary="CU-01 · Ver ficha de un equipo",
    description="Cache-aside: Redis (copia por 300 s) delante de MongoDB. Con Redis caído "
                "responde igual desde MongoDB con X-Cache: BYPASS.",
    responses={200: {"headers": ENCABEZADO_CACHE}} | respuestas_error(400, 404, 500, 503, 504,
        ejemplos={404: ["EQUIPO_NO_ENCONTRADO"]}),
)
def ver_equipo(equipoId: EquipoId, servicio: Servicio, response: Response) -> FichaEquipo:
    ficha, estado_cache = servicio.ficha(equipoId)
    response.headers["X-Cache"] = estado_cache
    return ficha


@router.get(
    "/{equipoId}/jugadores",
    response_model=PlantelEquipo,
    summary="CU-03 · Ver plantel de un equipo",
    description="Orden apellido, nombre, jugadorId. Equipo inexistente → 404; "
                "equipo sin jugadores para el filtro → items vacío.",
    responses=respuestas_error(400, 404, 500, 503, 504, ejemplos={404: ["EQUIPO_NO_ENCONTRADO"]}),
)
def ver_plantel(
    equipoId: EquipoId,
    servicio: Servicio,
    posicion: Annotated[Posicion | None, Query()] = None,
    limite: Annotated[int, Query(ge=1, le=24)] = 24,
    pagina: Pagina = 1,
) -> PlantelEquipo:
    return servicio.plantel(equipoId, posicion.value if posicion else None, pagina, limite)


@router.get(
    "/{equipoId}/partidos",
    response_model=AgendaEquipo,
    summary="CU-05 · Ver agenda y rivales de un equipo",
    description="Neo4j. Orden inicio, partidoId. Equipo inexistente → 404; equipo sin "
                "partidos → items vacío. No incluye el estado del partido (fuente: IRIS, CU-18).",
    responses=respuestas_error(400, 404, 500, 503, 504, ejemplos={404: ["EQUIPO_NO_ENCONTRADO"]}),
)
def ver_agenda(
    equipoId: EquipoId,
    servicio: Annotated[ServicioPartidos, Depends(obtener_servicio_partidos)],
    limite: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AgendaEquipo:
    return servicio.agenda(equipoId, limite)
