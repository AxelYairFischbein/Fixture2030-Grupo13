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
