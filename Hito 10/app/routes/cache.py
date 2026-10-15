"""Rutas de caché: CU-14 (Redis, Hito 7), reservada al rol operador."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

from app.schemas.equipos import PATRON_EQUIPO
from app.schemas.errores import respuestas_error
from app.services.equipos import ServicioEquipos, obtener_servicio_equipos
from app.services.sesiones import Autorizacion, sesion_requerida

router = APIRouter(prefix="/api/v1/cache", tags=["cache"])


@router.delete(
    "/equipos/{equipoId}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="CU-14 · Invalidar la ficha cacheada de un equipo",
    description="Requiere una sesión con rol operador. DEL idempotente: 204 aunque no hubiera "
                "copia. Si Redis no confirma la invalidación → 503 y el operador debe reintentar.",
    responses=respuestas_error(400, 401, 403, 503, 504),
)
def invalidar_ficha_cacheada(
    equipoId: Annotated[str, Path(pattern=PATRON_EQUIPO, examples=["EQ-001"])],
    servicio: Annotated[ServicioEquipos, Depends(obtener_servicio_equipos)],
    auth: Annotated[Autorizacion, Depends(sesion_requerida("operador"))],
) -> Response:
    auth.exigir()
    servicio.invalidar_ficha_cacheada(equipoId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
