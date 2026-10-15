"""Caso de uso de salud: estado de cada dependencia.

Cada dependencia con adaptador registra un chequeo (ping) que devuelve True o
False sin lanzar. Las que todavía no tienen adaptador figuran "no_configurada";
cada fase siguiente agrega el suyo.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends

from app.dependencias import obtener_adaptador_mongo
from app.schemas.salud import Dependencias, EstadoDependencia, RespuestaSalud

DEPENDENCIAS = ("mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris")


class ServicioSalud:
    def __init__(self, chequeos: dict[str, Callable[[], bool]] | None = None) -> None:
        self._chequeos = chequeos or {}

    def consultar(self) -> RespuestaSalud:
        estados = {}
        for nombre in DEPENDENCIAS:
            chequeo = self._chequeos.get(nombre)
            if chequeo is None:
                estados[nombre] = EstadoDependencia.NO_CONFIGURADA
            elif chequeo():
                estados[nombre] = EstadoDependencia.DISPONIBLE
            else:
                estados[nombre] = EstadoDependencia.NO_DISPONIBLE
        degradado = EstadoDependencia.NO_DISPONIBLE in estados.values()
        return RespuestaSalud(
            estado="degradado" if degradado else "ok",
            dependencias=Dependencias(**estados),
        )


def obtener_servicio_salud(
    adaptador_mongo: Annotated[object, Depends(obtener_adaptador_mongo)],
) -> ServicioSalud:
    return ServicioSalud({"mongodb": adaptador_mongo.ping})