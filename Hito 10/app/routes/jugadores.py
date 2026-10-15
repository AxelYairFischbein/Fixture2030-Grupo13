"""Rutas de jugadores: CU-04 (fuente MongoDB, Hito 4)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.schemas.errores import respuestas_error
from app.schemas.jugadores import PATRON_JUGADOR, FichaJugador
from app.services.jugadores import ServicioJugadores, obtener_servicio_jugadores

router = APIRouter(prefix="/api/v1/jugadores", tags=["jugadores"])


@router.get(
    "/{jugadorId}",
    response_model=FichaJugador,
    summary="CU-04 · Ver ficha de un jugador",
    responses=respuestas_error(400, 404, 503, 504),
)
def ver_jugador(
    jugadorId: Annotated[str, Path(pattern=PATRON_JUGADOR, examples=["JUG-0313"])],
    servicio: Annotated[ServicioJugadores, Depends(obtener_servicio_jugadores)],
) -> FichaJugador:
    return servicio.ficha(jugadorId)
