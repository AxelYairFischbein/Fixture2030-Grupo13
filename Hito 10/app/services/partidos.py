"""Casos de uso de partidos sobre Neo4j (Hito 5): CU-05, CU-06 y CU-07."""

from datetime import datetime, timedelta
from typing import Annotated, Protocol

from fastapi import Depends

from app.dependencias import obtener_adaptador_neo4j
from app.errors import NoEncontrado, ValidacionInvalida
from app.schemas.partidos import (
    AgendaEquipo,
    CalendarioPartidos,
    EventoPartido,
    EventosPartido,
    PartidoAgenda,
    PartidoCalendario,
)
from app.services.equipos import equipo_no_encontrado

# CU-07: intervalo máximo del calendario.
INTERVALO_MAXIMO = timedelta(days=7)


class RepositorioPartidos(Protocol):
    def agenda_equipo(self, equipo_id: str, limite: int) -> list[dict] | None: ...
    def eventos_partido(self, partido_id: str, limite: int) -> list[dict] | None: ...
    def partidos_por_fecha(self, desde: datetime, hasta: datetime,
                           estadio_id: str | None, limite: int) -> list[dict]: ...


def partido_no_encontrado(partido_id: str) -> NoEncontrado:
    return NoEncontrado(
        "PARTIDO_NO_ENCONTRADO",
        "No existe un partido con el identificador indicado.",
        [{"campo": "partidoId", "problema": f"{partido_id} no existe"}],
    )


class ServicioPartidos:
    def __init__(self, repositorio: RepositorioPartidos) -> None:
        self._repo = repositorio

    def agenda(self, equipo_id: str, limite: int) -> AgendaEquipo:
        """CU-05. None del adaptador = sin nodo Equipo (404); lista vacía = 200 []."""
        partidos = self._repo.agenda_equipo(equipo_id, limite)
        if partidos is None:
            raise equipo_no_encontrado(equipo_id)
        return AgendaEquipo(equipoId=equipo_id, items=[PartidoAgenda(**p) for p in partidos])

    def eventos(self, partido_id: str, limite: int) -> EventosPartido:
        """CU-06. None del adaptador = sin nodo Partido (404); lista vacía = 200 []."""
        eventos = self._repo.eventos_partido(partido_id, limite)
        if eventos is None:
            raise partido_no_encontrado(partido_id)
        return EventosPartido(partidoId=partido_id, items=[EventoPartido(**e) for e in eventos])

    def por_fechas(self, desde: datetime, hasta: datetime,
                   estadio_id: str | None, limite: int) -> CalendarioPartidos:
        """CU-07. El orden y el tamaño del intervalo se validan antes de consultar."""
        if desde >= hasta:
            raise ValidacionInvalida(detalles=[
                {"campo": "hasta", "problema": "debe ser posterior a desde"}])
        if hasta - desde > INTERVALO_MAXIMO:
            raise ValidacionInvalida(detalles=[
                {"campo": "hasta", "problema": "el intervalo no puede superar 7 días"}])
        partidos = self._repo.partidos_por_fecha(desde, hasta, estadio_id, limite)
        return CalendarioPartidos(items=[PartidoCalendario(**p) for p in partidos])


def obtener_servicio_partidos(
    repositorio: Annotated[RepositorioPartidos, Depends(obtener_adaptador_neo4j)],
) -> ServicioPartidos:
    return ServicioPartidos(repositorio)
