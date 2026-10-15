"""Caso de uso de jugadores: CU-04."""

from typing import Annotated, Protocol

from fastapi import Depends

from app.dependencias import obtener_adaptador_mongo
from app.errors import NoEncontrado
from app.schemas.jugadores import FichaJugador


class RepositorioJugadores(Protocol):
    def obtener_jugador(self, jugador_id: str) -> dict | None: ...


class ServicioJugadores:
    def __init__(self, repositorio: RepositorioJugadores) -> None:
        self._repo = repositorio

    def ficha(self, jugador_id: str) -> FichaJugador:
        jugador = self._repo.obtener_jugador(jugador_id)
        if jugador is None:
            raise NoEncontrado(
                "JUGADOR_NO_ENCONTRADO",
                "No existe un jugador con el identificador indicado.",
                [{"campo": "jugadorId", "problema": f"{jugador_id} no existe"}],
            )
        return FichaJugador(**jugador)


def obtener_servicio_jugadores(
    repositorio: Annotated[RepositorioJugadores, Depends(obtener_adaptador_mongo)],
) -> ServicioJugadores:
    return ServicioJugadores(repositorio)