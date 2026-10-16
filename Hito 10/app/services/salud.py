"""Caso de uso de salud: estado de cada dependencia y del catálogo de partidos.

Cada dependencia con adaptador registra un chequeo (ping) que devuelve True o
False sin lanzar. Las que todavía no tienen adaptador figuran "no_configurada";
cada fase siguiente agrega el suyo. El catálogo de partidos (casos_de_uso.md
§3.2) se informa sin forzar una recarga.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends

from app.dependencias import (
    obtener_adaptador_cassandra,
    obtener_adaptador_mongo,
    obtener_adaptador_neo4j,
    obtener_adaptador_redis,
    obtener_catalogo_partidos,
)
from app.schemas.salud import (
    CatalogoPartidos,
    Dependencias,
    EstadoCatalogo,
    EstadoDependencia,
    RespuestaSalud,
)

DEPENDENCIAS = ("mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris")


class ServicioSalud:
    def __init__(self, chequeos: dict[str, Callable[[], bool]] | None = None,
                 estado_catalogo: Callable[[], dict] | None = None) -> None:
        self._chequeos = chequeos or {}
        self._estado_catalogo = estado_catalogo or (
            lambda: {"estado": "no_cargado", "partidos": 0, "ultimaCarga": None}
        )

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
        catalogo = CatalogoPartidos(**self._estado_catalogo())
        degradado = (EstadoDependencia.NO_DISPONIBLE in estados.values()
                     or catalogo.estado is EstadoCatalogo.NO_CARGADO)
        return RespuestaSalud(
            estado="degradado" if degradado else "ok",
            dependencias=Dependencias(**estados),
            catalogoPartidos=catalogo,
        )


def obtener_servicio_salud(
    adaptador_mongo: Annotated[object, Depends(obtener_adaptador_mongo)],
    adaptador_redis: Annotated[object, Depends(obtener_adaptador_redis)],
    adaptador_neo4j: Annotated[object, Depends(obtener_adaptador_neo4j)],
    adaptador_cassandra: Annotated[object, Depends(obtener_adaptador_cassandra)],
    catalogo: Annotated[object, Depends(obtener_catalogo_partidos)],
) -> ServicioSalud:
    return ServicioSalud(
        {"mongodb": adaptador_mongo.ping, "redis": adaptador_redis.ping,
         "neo4j": adaptador_neo4j.ping, "cassandra": adaptador_cassandra.ping},
        catalogo.estado,
    )
