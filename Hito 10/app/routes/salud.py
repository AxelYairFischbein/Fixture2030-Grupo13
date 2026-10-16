"""GET /api/v1/salud: estado de las dependencias de la API."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas.errores import respuestas_error
from app.schemas.errores import respuestas_error
from app.schemas.salud import RespuestaSalud
from app.services.salud import ServicioSalud, obtener_servicio_salud

router = APIRouter(prefix="/api/v1", tags=["salud"])


@router.get(
    "/salud",
    response_model=RespuestaSalud,
    summary="Estado de las dependencias",
    description='Informa por dependencia "disponible", "no_disponible" o "no_configurada", '
                'y el estado del catálogo de partidos en memoria (cargado, cantidad de '
                'partidos y hora de la última carga, casos_de_uso.md §3.2).',
    responses=respuestas_error(500),
)
def consultar_salud(
    servicio: Annotated[ServicioSalud, Depends(obtener_servicio_salud)],
) -> RespuestaSalud:
    return servicio.consultar()
