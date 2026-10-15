"""Casos de uso de equipos: CU-01 (cache-aside Redis + MongoDB), CU-02, CU-03 y CU-14."""

import logging
from typing import Annotated, Protocol

from fastapi import Depends

from app.dependencias import obtener_adaptador_mongo, obtener_adaptador_redis
from app.errors import DependenciaNoDisponible, DependenciaTimeout, NoEncontrado
from app.schemas.equipos import EquipoResumen, FichaEquipo, PaginaEquipos
from app.schemas.jugadores import JugadorPlantel, PlantelEquipo


class RepositorioEquipos(Protocol):
    def obtener_equipo(self, equipo_id: str) -> dict | None: ...
    def existe_equipo(self, equipo_id: str) -> bool: ...
    def listar_equipos(self, confederacion: str, ranking_max: int | None,
                       pagina: int, limite: int) -> tuple[list[dict], int]: ...
    def listar_jugadores_de_equipo(self, equipo_id: str, posicion: str | None,
                                   pagina: int, limite: int) -> tuple[list[dict], int]: ...


class CacheFichas(Protocol):
    """Copia no autoritativa de la ficha (Redis, Hito 7). La fuente de verdad es MongoDB."""

    def leer_ficha_cacheada(self, equipo_id: str) -> dict | None: ...
    def guardar_ficha_cacheada(self, equipo_id: str, ficha: dict) -> None: ...
    def invalidar_ficha_cacheada(self, equipo_id: str) -> None: ...


# Valores del encabezado X-Cache de CU-01.
HIT, MISS, BYPASS = "HIT", "MISS", "BYPASS"

logger = logging.getLogger("app.services.equipos")


def equipo_no_encontrado(equipo_id: str) -> NoEncontrado:
    return NoEncontrado(
        "EQUIPO_NO_ENCONTRADO",
        "No existe un equipo con el identificador indicado.",
        [{"campo": "equipoId", "problema": f"{equipo_id} no existe"}],
    )


class ServicioEquipos:
    def __init__(self, repositorio: RepositorioEquipos, cache: CacheFichas) -> None:
        self._repo = repositorio
        self._cache = cache

    def ficha(self, equipo_id: str) -> tuple[FichaEquipo, str]:
        """CU-01 con cache-aside. Devuelve la ficha y el valor de X-Cache.

        Redis caído o con timeout → se lee MongoDB y se responde BYPASS (respuesta
        degradada del Hito 7). Si falla el SET se responde igual, sin confirmar la copia.
        La ausencia no se cachea.
        """
        bypass = False
        try:
            copia = self._cache.leer_ficha_cacheada(equipo_id)
        except (DependenciaNoDisponible, DependenciaTimeout):
            copia, bypass = None, True
        if copia is not None:
            return FichaEquipo(**copia), HIT

        equipo = self._repo.obtener_equipo(equipo_id)
        if equipo is None:
            raise equipo_no_encontrado(equipo_id)
        ficha = FichaEquipo(**equipo)
        if bypass:
            return ficha, BYPASS
        try:
            self._cache.guardar_ficha_cacheada(equipo_id, ficha.model_dump(mode="json"))
        except (DependenciaNoDisponible, DependenciaTimeout):
            logger.warning("cache=no_confirmada equipoId=%s", equipo_id)
        return ficha, MISS

    def invalidar_ficha_cacheada(self, equipo_id: str) -> None:
        """CU-14. DEL idempotente; si Redis no lo confirma se propaga 503/504."""
        self._cache.invalidar_ficha_cacheada(equipo_id)

    def listar(self, confederacion: str, ranking_max: int | None,
               pagina: int, limite: int) -> PaginaEquipos:
        items, total = self._repo.listar_equipos(confederacion, ranking_max, pagina, limite)
        return PaginaEquipos(
            items=[EquipoResumen(**i) for i in items], pagina=pagina, limite=limite, total=total
        )

    def plantel(self, equipo_id: str, posicion: str | None,
                pagina: int, limite: int) -> PlantelEquipo:
        # Primero la existencia del equipo: distingue 404 de un plantel vacío (200 []).
        if not self._repo.existe_equipo(equipo_id):
            raise equipo_no_encontrado(equipo_id)
        items, total = self._repo.listar_jugadores_de_equipo(equipo_id, posicion, pagina, limite)
        return PlantelEquipo(
            equipoId=equipo_id, items=[JugadorPlantel(**i) for i in items],
            pagina=pagina, limite=limite, total=total,
        )


def obtener_servicio_equipos(
    repositorio: Annotated[RepositorioEquipos, Depends(obtener_adaptador_mongo)],
    cache: Annotated[CacheFichas, Depends(obtener_adaptador_redis)],
) -> ServicioEquipos:
    return ServicioEquipos(repositorio, cache)