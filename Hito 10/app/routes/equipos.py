"""Rutas de equipos: CU-01, CU-02 y CU-03 (fuente MongoDB, Hito 4)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.schemas.equipos import PATRON_EQUIPO, Confederacion, FichaEquipo, PaginaEquipos
from app.schemas.errores import respuestas_error
from app.schemas.jugadores import PlantelEquipo, Posicion
from app.services.equipos import ServicioEquipos, obtener_servicio_equipos

router = APIRouter(prefix="/api/v1/equipos", tags=["equipos"])

Servicio = Annotated[ServicioEquipos, Depends(obtener_servicio_equipos)]
EquipoId = Annotated[str, Path(pattern=PATRON_EQUIPO, examples=["EQ-001"])]
Pagina = Annotated[int, Query(ge=1, description="Número de página, desde 1.")]


@router.get(
    "",
    response_model=PaginaEquipos,
    summary="CU-02 · Listar equipos de una confederación",
    description="Orden rankingReferencia ASC, equipoId ASC. Sin coincidencias → items vacío.",
    responses=respuestas_error(400, 503, 504),
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
    responses=respuestas_error(400, 404, 503, 504),
)
def ver_equipo(equipoId: EquipoId, servicio: Servicio) -> FichaEquipo:
    return servicio.ficha(equipoId)


@router.get(
    "/{equipoId}/jugadores",
    response_model=PlantelEquipo,
    summary="CU-03 · Ver plantel de un equipo",
    description="Orden apellido, nombre, jugadorId. Equipo inexistente → 404; "
                "equipo sin jugadores para el filtro → items vacío.",
    responses=respuestas_error(400, 404, 503, 504),
)
def ver_plantel(
    equipoId: EquipoId,
    servicio: Servicio,
    posicion: Annotated[Posicion | None, Query()] = None,
    limite: Annotated[int, Query(ge=1, le=24)] = 24,
    pagina: Pagina = 1,
) -> PlantelEquipo:
    return servicio.plantel(equipoId, posicion.value if posicion else None, pagina, limite)
