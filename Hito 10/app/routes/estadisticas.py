"""Rutas de estadísticas temporales sobre InfluxDB (Hito 8): CU-15, CU-16 y CU-17.

Orden en cada ruta: validación de la entrada (400, sin tocar ninguna base), catálogo de
partidos (404/503) y recién entonces InfluxDB (503/504; 500 si rechaza la credencial).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.schemas.equipos import PATRON_EQUIPO
from app.schemas.errores import CAIDA_O_CATALOGO, respuestas_error
from app.schemas.estadisticas import (
    ComparacionPartido,
    EstadoReciente,
    EvolucionPartido,
    Resolucion,
)
from app.schemas.partidos import PATRON_PARTIDO, InstanteUTC
from app.services.estadisticas import ServicioEstadisticas, obtener_servicio_estadisticas

router = APIRouter(prefix="/api/v1", tags=["estadisticas"])

Servicio = Annotated[ServicioEstadisticas, Depends(obtener_servicio_estadisticas)]
PartidoId = Annotated[str, Path(pattern=PATRON_PARTIDO, examples=["PAR-001"])]
EquipoId = Annotated[str, Path(pattern=PATRON_EQUIPO, examples=["EQ-001"])]

AGREGACIONES = (
    "`muestras` = COUNT(*) en [desde, hasta); `muestrasEsperadas` = timestamps múltiplos del "
    "paso de la serie (1 s) en la ventana; `posesionMedia` = ROUND(AVG(posesion_pct), 3); "
    "`pasesNuevos` = SUM de pases_acumulados − LAG(pases_acumulados) por serie, incluyendo la "
    "muestra anterior a desde; `tiros` = SUM(tiros_intervalo); `intervalosInvalidos` = muestras "
    "sin muestra anterior, con separación distinta del paso o con contador que retrocede; "
    "`completo` = muestras == muestrasEsperadas y intervalosInvalidos == 0. No se rellenan "
    "huecos con ceros."
)


@router.get(
    "/partidos/{partidoId}/equipos/{equipoId}/estadisticas/recientes",
    response_model=EstadoReciente,
    summary="CU-15 · Ver estado reciente de un equipo en un partido",
    description="Últimas observaciones de la serie (partido, equipo) en [hasta − 60 s, hasta), "
                "en orden time DESC. `hasta` por defecto es ahora. Sin puntos → 200 con "
                "`items: []` y `ultimaObservacion: null` (no hay observaciones; no significa "
                "estadísticas en cero). Partido fuera del catálogo → 404 PARTIDO_NO_ENCONTRADO; "
                "equipo que no lo disputa → 404 EQUIPO_NO_PARTICIPA.",
    responses=respuestas_error(400, 404, 500, 503, 504, ejemplos={
        404: ["PARTIDO_NO_ENCONTRADO", "EQUIPO_NO_PARTICIPA"], 503: CAIDA_O_CATALOGO}),
)
def ver_recientes(
    partidoId: PartidoId,
    equipoId: EquipoId,
    servicio: Servicio,
    hasta: Annotated[InstanteUTC | None, Query(examples=["2026-10-16T00:17:00Z"])] = None,
    limite: Annotated[int, Query(ge=1, le=60)] = 5,
) -> EstadoReciente:
    ventana = servicio.preparar_recientes(hasta)
    return servicio.recientes(partidoId, equipoId, ventana, limite)


@router.get(
    "/partidos/{partidoId}/estadisticas/comparacion",
    response_model=ComparacionPartido,
    summary="CU-16 · Comparar los equipos de un partido",
    description="Una fila por equipo con medidas agregadas sobre [desde, hasta), ventana de "
                "como máximo 5 min. " + AGREGACIONES + " Partido sin puntos → 200 con "
                "`equipos: []`.",
    responses=respuestas_error(400, 404, 500, 503, 504, ejemplos={
        404: ["PARTIDO_NO_ENCONTRADO"], 503: CAIDA_O_CATALOGO}),
)
def comparar_equipos(
    partidoId: PartidoId,
    servicio: Servicio,
    desde: Annotated[InstanteUTC, Query(examples=["2026-10-16T00:12:00Z"])],
    hasta: Annotated[InstanteUTC, Query(examples=["2026-10-16T00:17:00Z"])],
) -> ComparacionPartido:
    ventana = servicio.preparar_comparacion(desde, hasta)
    return servicio.comparar(partidoId, ventana)


@router.get(
    "/partidos/{partidoId}/estadisticas/evolucion",
    response_model=EvolucionPartido,
    summary="CU-17 · Ver evolución por minuto",
    description="Intervalos DATE_BIN de 1 o 5 minutos UTC (alineados a la época) por equipo "
                "sobre [desde, hasta), ventana de como máximo 2 h (120 intervalos × 2 equipos). "
                "Mismas agregaciones que CU-16 por intervalo: " + AGREGACIONES + " Un bin "
                "cortado por la ventana espera solo las muestras de la parte incluida. "
                "`equipoId` opcional: si no disputa el partido → 404 EQUIPO_NO_PARTICIPA. "
                "Partido sin puntos → 200 con `series: []`.",
    responses=respuestas_error(400, 404, 500, 503, 504, ejemplos={
        404: ["PARTIDO_NO_ENCONTRADO", "EQUIPO_NO_PARTICIPA"], 503: CAIDA_O_CATALOGO}),
)
def ver_evolucion(
    partidoId: PartidoId,
    servicio: Servicio,
    desde: Annotated[InstanteUTC, Query(examples=["2026-10-16T00:12:00Z"])],
    hasta: Annotated[InstanteUTC, Query(examples=["2026-10-16T00:17:00Z"])],
    resolucion: Annotated[Resolucion, Query()] = Resolucion.UN_MINUTO,
    equipoId: Annotated[str | None, Query(pattern=PATRON_EQUIPO, examples=["EQ-001"])] = None,
) -> EvolucionPartido:
    ventana = servicio.preparar_evolucion(desde, hasta)
    return servicio.evolucion(partidoId, ventana, resolucion, equipoId)
