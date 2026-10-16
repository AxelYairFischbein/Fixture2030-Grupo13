"""Casos de uso de estadísticas temporales sobre InfluxDB (Hito 8): CU-15, CU-16 y CU-17.

Orden en cada operación: validación de fechas, orden y tamaño de ventana (400, sin tocar
el catálogo ni InfluxDB), catálogo de partidos en memoria (casos_de_uso.md §3.2: 404 si
el partido no existe o el equipo no lo disputa, 503 si no pudo cargarse) y recién
entonces InfluxDB. Una ventana sin puntos es un 200 vacío; una falla de InfluxDB nunca.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Protocol

from fastapi import Depends, Request

from app.dependencias import obtener_adaptador_influx, obtener_catalogo_partidos
from app.errors import ValidacionInvalida
from app.schemas.estadisticas import (
    ComparacionEquipo,
    ComparacionPartido,
    EstadoReciente,
    EvolucionPartido,
    IntervaloEvolucion,
    Observacion,
    Resolucion,
    SerieEquipo,
)

VENTANA_RECIENTE = timedelta(seconds=60)
VENTANA_MAXIMA_COMPARACION = timedelta(minutes=5)
VENTANA_MAXIMA_EVOLUCION = timedelta(hours=2)
DURACION_RESOLUCION = {
    Resolucion.UN_MINUTO: timedelta(minutes=1),
    Resolucion.CINCO_MINUTOS: timedelta(minutes=5),
}
EPOCA = datetime(1970, 1, 1, tzinfo=UTC)
UN_US = timedelta(microseconds=1)


class RepositorioEstadisticas(Protocol):
    def ultimas_observaciones(self, partido_id: str, equipo_id: str, desde: datetime,
                              hasta: datetime, limite: int) -> list[dict]: ...
    def comparar(self, partido_id: str, desde: datetime, hasta: datetime) -> list[dict]: ...
    def evolucion(self, partido_id: str, equipo_id: str | None, desde: datetime,
                  hasta: datetime, resolucion: str) -> list[dict]: ...


class Catalogo(Protocol):
    def validar_partido(self, partido_id: str) -> tuple[str, ...]: ...
    def validar_participacion(self, partido_id: str, equipo_id: str) -> None: ...


@dataclass(frozen=True)
class Ventana:
    """Intervalo semiabierto [desde, hasta) ya validado, en UTC."""

    desde: datetime
    hasta: datetime


def _invalido(campo: str, problema: str) -> ValidacionInvalida:
    return ValidacionInvalida(detalles=[{"campo": campo, "problema": problema}])


def ventana_valida(desde: datetime, hasta: datetime, maxima: timedelta,
                   descripcion_maxima: str) -> Ventana:
    if desde >= hasta:
        raise _invalido("hasta", "debe ser posterior a desde")
    if hasta - desde > maxima:
        raise _invalido("hasta", f"la ventana no puede superar {descripcion_maxima}")
    return Ventana(desde.astimezone(UTC), hasta.astimezone(UTC))


def muestras_esperadas(desde: datetime, hasta: datetime, paso_s: int) -> int:
    """Cantidad de timestamps múltiplos del paso (alineados a la época) en [desde, hasta)."""
    paso_us = paso_s * 1_000_000

    def techo(instante: datetime) -> int:
        return -(-((instante - EPOCA) // UN_US) // paso_us)

    return max(0, techo(hasta) - techo(desde))


def _medidas(fila: dict, esperadas: int) -> dict:
    muestras = int(fila["muestras"])
    invalidos = int(fila["intervalos_invalidos"] or 0)
    return {
        "muestras": muestras,
        "muestrasEsperadas": esperadas,
        "posesionMedia": fila.get("posesion_media"),
        "pasesNuevos": fila.get("pases_nuevos"),
        "tiros": fila.get("tiros"),
        "intervalosInvalidos": invalidos,
        "completo": muestras == esperadas and invalidos == 0,
    }


class ServicioEstadisticas:
    def __init__(self, repositorio: RepositorioEstadisticas, catalogo: Catalogo, paso_s: int,
                 reloj: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._repo = repositorio
        self._catalogo = catalogo
        self._paso_s = paso_s
        self._reloj = reloj

    # CU-15

    def preparar_recientes(self, hasta: datetime | None) -> Ventana:
        """Ventana [hasta − 60 s, hasta); sin hasta, termina ahora."""
        fin = (hasta or self._reloj()).astimezone(UTC)
        return Ventana(fin - VENTANA_RECIENTE, fin)

    def recientes(self, partido_id: str, equipo_id: str, ventana: Ventana,
                  limite: int) -> EstadoReciente:
        self._catalogo.validar_participacion(partido_id, equipo_id)
        filas = self._repo.ultimas_observaciones(
            partido_id, equipo_id, ventana.desde, ventana.hasta, limite)
        items = [Observacion(
            time=f["time"], posesionPct=f.get("posesion_pct"),
            pasesAcumulados=f.get("pases_acumulados"), tirosIntervalo=f.get("tiros_intervalo"),
        ) for f in filas]
        return EstadoReciente(
            partidoId=partido_id, equipoId=equipo_id,
            estadioId=filas[0].get("estadio_id") if filas else None,
            items=items, ultimaObservacion=items[0].time if items else None,
        )

    # CU-16

    @staticmethod
    def preparar_comparacion(desde: datetime, hasta: datetime) -> Ventana:
        return ventana_valida(desde, hasta, VENTANA_MAXIMA_COMPARACION, "5 minutos")

    def comparar(self, partido_id: str, ventana: Ventana) -> ComparacionPartido:
        self._catalogo.validar_partido(partido_id)
        filas = self._repo.comparar(partido_id, ventana.desde, ventana.hasta)
        esperadas = muestras_esperadas(ventana.desde, ventana.hasta, self._paso_s)
        return ComparacionPartido(
            partidoId=partido_id, desde=ventana.desde, hasta=ventana.hasta,
            equipos=[ComparacionEquipo(equipoId=f["equipo_id"], **_medidas(f, esperadas))
                     for f in filas],
        )

    # CU-17

    @staticmethod
    def preparar_evolucion(desde: datetime, hasta: datetime) -> Ventana:
        return ventana_valida(desde, hasta, VENTANA_MAXIMA_EVOLUCION, "2 horas")

    def evolucion(self, partido_id: str, ventana: Ventana, resolucion: Resolucion,
                  equipo_id: str | None) -> EvolucionPartido:
        if equipo_id is None:
            self._catalogo.validar_partido(partido_id)
        else:
            self._catalogo.validar_participacion(partido_id, equipo_id)
        filas = self._repo.evolucion(
            partido_id, equipo_id, ventana.desde, ventana.hasta, resolucion.value)
        duracion = DURACION_RESOLUCION[resolucion]
        series: dict[str, list[IntervaloEvolucion]] = {}
        for f in filas:
            # Un bin cortado por desde o hasta espera solo las muestras de la parte incluida.
            esperadas = muestras_esperadas(
                max(f["inicio"], ventana.desde), min(f["inicio"] + duracion, ventana.hasta),
                self._paso_s)
            series.setdefault(f["equipo_id"], []).append(
                IntervaloEvolucion(inicio=f["inicio"], **_medidas(f, esperadas)))
        return EvolucionPartido(
            partidoId=partido_id, desde=ventana.desde, hasta=ventana.hasta,
            resolucion=resolucion,
            series=[SerieEquipo(equipoId=e, intervalos=sorted(i, key=lambda x: x.inicio))
                    for e, i in sorted(series.items())],
        )


def obtener_servicio_estadisticas(
    request: Request,
    adaptador_influx: Annotated[object, Depends(obtener_adaptador_influx)],
    catalogo: Annotated[object, Depends(obtener_catalogo_partidos)],
) -> ServicioEstadisticas:
    return ServicioEstadisticas(adaptador_influx, catalogo, request.app.state.settings.influx_paso_s)
