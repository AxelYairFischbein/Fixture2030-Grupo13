"""Rutas del acta del partido sobre IRIS (Hito 9): CU-18 y CU-19.

Son las únicas rutas que informan o cambian el estado de un partido (casos_de_uso.md §3.1).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.schemas.actas import ActaPartido, ResultadoTransicion, SolicitudTransicion
from app.schemas.errores import respuestas_error
from app.schemas.partidos import PATRON_PARTIDO
from app.services.actas import ServicioActas, obtener_servicio_actas
from app.services.sesiones import Autorizacion, sesion_requerida

router = APIRouter(prefix="/api/v1/partidos", tags=["actas"])

Servicio = Annotated[ServicioActas, Depends(obtener_servicio_actas)]
PartidoId = Annotated[str, Path(pattern=PATRON_PARTIDO, examples=["PAR-001"])]


@router.get(
    "/{partidoId}/acta",
    response_model=ActaPartido,
    summary="CU-18 · Ver el acta de un partido",
    description="Estado (fuente autoritativa: IRIS), estadio, árbitro y eventos ordenados por "
                "minuto. Partido sin acta en IRIS → 404 ACTA_NO_ENCONTRADA aunque exista en "
                "el calendario; acta sin eventos → eventos vacío.",
    responses=respuestas_error(400, 404, 500, 503, 504, ejemplos={404: ["ACTA_NO_ENCONTRADA"]}),
)
def ver_acta(partidoId: PartidoId, servicio: Servicio) -> ActaPartido:
    return servicio.ver_acta(partidoId)


@router.post(
    "/{partidoId}/acta/transiciones",
    response_model=ResultadoTransicion,
    summary="CU-19 · Cambiar el estado de un partido",
    description="Requiere una sesión con rol operador. Solo PENDIENTE → EN_JUEGO → FINALIZADO, "
                "aplicado con CambiarEstado() en IRIS. Si el estado ya es el pedido → 200 con "
                "cambio=false (reintento seguro tras un 504). Transición no permitida → 409 "
                "TRANSICION_NO_PERMITIDA con el estado actual en detalles.",
    responses=respuestas_error(400, 401, 403, 404, 409, 500, 503, 504, ejemplos={
        404: ["ACTA_NO_ENCONTRADA"], 409: ["TRANSICION_NO_PERMITIDA"]}),
)
def transicionar(
    partidoId: PartidoId,
    solicitud: SolicitudTransicion,
    servicio: Servicio,
    auth: Annotated[Autorizacion, Depends(sesion_requerida("operador"))],
) -> ResultadoTransicion:
    auth.exigir()
    return servicio.transicionar(partidoId, solicitud.nuevoEstado.value)
