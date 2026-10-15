"""Casos de uso de equipos: CU-01 (sin caché hasta la Fase 3), CU-02 y CU-03."""

from typing import Annotated, Protocol

from fastapi import Depends

from app.dependencias import obtener_adaptador_mongo
from app.errors import NoEncontrado
from app.schemas.equipos import EquipoResumen, FichaEquipo, PaginaEquipos
from app.schemas.jugadores import JugadorPlantel, PlantelEquipo


class RepositorioEquipos(Protocol):
    def obtener_equipo(self, equipo_id: str) -> dict | None: ...
    def existe_equipo(self, equipo_id: str) -> bool: ...
    def listar_equipos(self, confederacion: str, ranking_max: int | None,
                       pagina: int, limite: int) -> tuple[list[dict], int]: ...
    def listar_jugadores_de_equipo(self, equipo_id: str, posicion: str | None,
                                   pagina: int, limite: int) -> tuple[list[dict], int]: ...


def equipo_no_encontrado(equipo_id: str) -> NoEncontrado:
    return NoEncontrado(
        "EQUIPO_NO_ENCONTRADO",
        "No existe un equipo con el identificador indicado.",
        [{"campo": "equipoId", "problema": f"{equipo_id} no existe"}],
    )


class ServicioEquipos:
    def __init__(self, repositorio: RepositorioEquipos) -> None:
        self._repo = repositorio

    def ficha(self, equipo_id: str) -> FichaEquipo:
        equipo = self._repo.obtener_equipo(equipo_id)
        if equipo is None:
            raise equipo_no_encontrado(equipo_id)
        return FichaEquipo(**equipo)

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
) -> ServicioEquipos:
    return ServicioEquipos(repositorio)