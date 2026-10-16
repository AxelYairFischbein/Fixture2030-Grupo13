"""Proveedores de adaptadores para Depends.

Los adaptadores se crean una vez en el lifespan de app.main y se guardan en
app.state. Las pruebas reemplazan estas funciones con dependency_overrides para
inyectar adaptadores falsos.
"""

from fastapi import Request


def obtener_adaptador_mongo(request: Request):
    return request.app.state.adaptador_mongo


def obtener_adaptador_redis(request: Request):
    return request.app.state.adaptador_redis


def obtener_adaptador_neo4j(request: Request):
    return request.app.state.adaptador_neo4j


def obtener_adaptador_cassandra(request: Request):
    return request.app.state.adaptador_cassandra


def obtener_adaptador_influx(request: Request):
    return request.app.state.adaptador_influx


def obtener_catalogo_partidos(request: Request):
    """Catálogo de partidos en memoria (casos_de_uso.md §3.2), para las fases 5 y 6."""
    return request.app.state.catalogo_partidos
