"""Rutas de sesiones: CU-11, CU-12 y CU-13 (fuente Redis, Hito 7).

La sesión viaja en el encabezado X-Session-Id, nunca en la ruta ni en la query.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.schemas.errores import respuestas_error
from app.schemas.sesiones import ActividadRegistrada, SesionVigente
from app.services.sesiones import EncabezadoSesion, ServicioSesiones, obtener_servicio_sesiones

router = APIRouter(prefix="/api/v1/sesiones", tags=["sesiones"])

Servicio = Annotated[ServicioSesiones, Depends(obtener_servicio_sesiones)]


@router.get(
    "/actual",
    response_model=SesionVigente,
    summary="CU-11 · Consultar la sesión vigente",
    description="200 solo si la clave existe, estado=activa y TTL > 0. No renueva el TTL. "
                "Redis caído → 503, nunca 401: el cliente no debe descartar su sesión por un 503.",
    responses=respuestas_error(400, 401, 503, 504),
)
def consultar_sesion(servicio: Servicio, sesion_id: EncabezadoSesion = None) -> SesionVigente:
    return servicio.consultar(sesion_id)


@router.post(
    "/actual/actividad",
    response_model=ActividadRegistrada,
    summary="CU-12 · Registrar actividad de la sesión",
    description="Comprueba la sesión, actualiza ultima_actividad y renueva el TTL a 1800 s "
                "en un único script Lua. No recrea una sesión ausente.",
    responses=respuestas_error(400, 401, 503, 504),
)
def registrar_actividad(servicio: Servicio, sesion_id: EncabezadoSesion = None) -> ActividadRegistrada:
    return servicio.registrar_actividad(sesion_id)


@router.delete(
    "/actual",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="CU-13 · Cerrar la sesión",
    description="DEL idempotente: 204 también si la sesión ya no existía. "
                "Redis caído → 503, nunca 204.",
    responses=respuestas_error(400, 401, 503, 504),
)
def cerrar_sesion(servicio: Servicio, sesion_id: EncabezadoSesion = None) -> Response:
    servicio.cerrar(sesion_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
