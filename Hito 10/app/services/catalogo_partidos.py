"""Catálogo de partidos en memoria cargado desde Neo4j (casos_de_uso.md §3.2).

Cassandra e InfluxDB no saben si un partido existe. Comentarios (fase 5) y
estadísticas (fase 6) validan el partido contra este catálogo, sin consultar
Neo4j en cada request:

- Se carga al iniciar la API y se refresca cada `catalogo_refresco_s` (10 min)
  en un hilo de fondo.
- Si Neo4j está caído al iniciar, la API arranca igual con el catálogo
  "no_cargado"; una request que lo necesita reintenta la carga como máximo una
  vez cada `catalogo_reintento_s` (30 s) y, mientras no cargue, recibe 503.
- Si Neo4j cae después de cargar, se sigue usando el último catálogo cargado.
"""

import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, ErrorDominio, NoEncontrado
from app.services.partidos import partido_no_encontrado

logger = logging.getLogger("app.services.catalogo_partidos")

CARGADO, NO_CARGADO = "cargado", "no_cargado"


class FuenteCatalogo(Protocol):
    def cargar_catalogo_partidos(self) -> dict[str, tuple[str, ...]]: ...


class CatalogoPartidos:
    def __init__(self, fuente: FuenteCatalogo, settings: Settings,
                 reloj: Callable[[], float] = time.monotonic) -> None:
        self._fuente = fuente
        self._refresco_s = settings.catalogo_refresco_s
        self._reintento_s = settings.catalogo_reintento_s
        self._reloj = reloj
        self._partidos: dict[str, tuple[str, ...]] | None = None
        self._cargado_en: datetime | None = None
        self._ultimo_intento: float | None = None
        self._lock = threading.Lock()
        self._detener = threading.Event()
        self._hilo: threading.Thread | None = None

    # Ciclo de vida

    def iniciar(self) -> None:
        """Primera carga (acotada por los timeouts de Neo4j) y refresco periódico."""
        self.cargar()
        self._hilo = threading.Thread(
            target=self._refrescar_periodicamente, name="catalogo-partidos", daemon=True
        )
        self._hilo.start()

    def detener(self) -> None:
        self._detener.set()
        if self._hilo is not None:
            self._hilo.join(timeout=5)

    def _refrescar_periodicamente(self) -> None:
        while not self._detener.wait(self._refresco_s):
            self.cargar()

    def cargar(self) -> bool:
        """Reemplaza el catálogo si la carga sale bien; si falla, conserva el anterior."""
        with self._lock:
            return self._cargar_sin_lock()

    def _cargar_sin_lock(self) -> bool:
        self._ultimo_intento = self._reloj()
        try:
            partidos = self._fuente.cargar_catalogo_partidos()
        except ErrorDominio as exc:
            logger.warning("catalogo=no_actualizado motivo=%s conserva_anterior=%s",
                           exc.codigo, self._partidos is not None)
            return False
        self._partidos = partidos
        self._cargado_en = datetime.now(UTC)
        logger.info("catalogo=cargado partidos=%d", len(partidos))
        return True

    def _asegurar_cargado(self) -> dict[str, tuple[str, ...]]:
        partidos = self._partidos
        if partidos is not None:
            return partidos
        with self._lock:
            if self._partidos is None and (
                self._ultimo_intento is None
                or self._reloj() - self._ultimo_intento >= self._reintento_s
            ):
                self._cargar_sin_lock()
            if self._partidos is None:
                # No se puede saber si el partido existe: ni 200 ni 404.
                raise DependenciaNoDisponible(
                    "neo4j", "El catálogo de partidos todavía no pudo cargarse."
                )
            return self._partidos

    # Consultas para los casos de uso

    def validar_partido(self, partido_id: str) -> tuple[str, ...]:
        """Devuelve los equipos del partido o lanza 404 PARTIDO_NO_ENCONTRADO (503 sin catálogo)."""
        equipos = self._asegurar_cargado().get(partido_id)
        if equipos is None:
            raise partido_no_encontrado(partido_id)
        return equipos

    def validar_participacion(self, partido_id: str, equipo_id: str) -> None:
        """404 PARTIDO_NO_ENCONTRADO o 404 EQUIPO_NO_PARTICIPA (503 sin catálogo)."""
        if equipo_id not in self.validar_partido(partido_id):
            raise NoEncontrado(
                "EQUIPO_NO_PARTICIPA",
                "El equipo indicado no disputa ese partido.",
                [{"campo": "equipoId", "problema": f"{equipo_id} no disputa {partido_id}"}],
            )

    def estado(self) -> dict:
        """Para /api/v1/salud. No dispara recargas."""
        partidos = self._partidos
        return {
            "estado": CARGADO if partidos is not None else NO_CARGADO,
            "partidos": len(partidos) if partidos is not None else 0,
            "ultimaCarga": self._cargado_en,
        }
