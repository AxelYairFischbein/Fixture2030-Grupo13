"""Punto de entrada: uvicorn app.main:app (ejecutar desde la carpeta Hito 10)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.cassandra_adaptador import AdaptadorCassandra
from app.adapters.influx_adaptador import AdaptadorInflux
from app.adapters.iris_adaptador import AdaptadorIris
from app.adapters.mongo_adaptador import AdaptadorMongo
from app.adapters.neo4j_adaptador import AdaptadorNeo4j
from app.adapters.redis_adaptador import AdaptadorRedis
from app.config.logging import configurar_logging
from app.config.settings import Settings, cargar_settings
from app.manejadores import registrar_manejadores
from app.middleware import RequestIdMiddleware
from app.openapi import instalar_openapi
from app.routes import (
    actas,
    cache,
    comentarios,
    equipos,
    estadisticas,
    jugadores,
    partidos,
    salud,
    sesiones,
)
from app.services.catalogo_partidos import CatalogoPartidos

DESCRIPCION = (
    "API REST del Hito 10 (Grupo 13) sobre MongoDB, Neo4j, Cassandra, Redis, InfluxDB e "
    "InterSystems IRIS. Datos sintéticos.\n\n"
    "Toda respuesta lleva el encabezado `X-Request-Id` (se acepta el del cliente si es un UUID). "
    "Todo error usa el formato único `{\"error\": {codigo, mensaje, requestId, detalles}}` "
    "(casos_de_uso.md §6.1). Además de los errores declarados en cada operación, cualquier "
    "ruta inexistente responde `404 RUTA_NO_ENCONTRADA` y un método no admitido "
    "`405 METODO_NO_PERMITIDO` con el encabezado `Allow`. Las operaciones protegidas reciben "
    "la sesión en `X-Session-Id`, nunca en la ruta ni en la query."
)


def create_app(settings: Settings | None = None, iniciar_catalogo: bool = True) -> FastAPI:
    """`iniciar_catalogo=False` deja el catálogo de partidos sin cargar ni refrescar:
    lo usan las pruebas unitarias, que inyectan su propio catálogo sobre un Neo4j falso."""
    settings = settings or cargar_settings()
    configurar_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Los adaptadores se crean una vez y se comparten entre requests.
        app.state.adaptador_mongo = AdaptadorMongo(settings)
        app.state.adaptador_redis = AdaptadorRedis(settings)
        app.state.adaptador_neo4j = AdaptadorNeo4j(settings)
        # Cassandra conecta en el primer uso: la API arranca aunque esté caída.
        app.state.adaptador_cassandra = AdaptadorCassandra(settings)
        # InfluxDB lee el token al crearse: si falta, la API no arranca (nombra la variable).
        app.state.adaptador_influx = AdaptadorInflux(settings)
        # IRIS conecta en el primer uso: la API arranca aunque esté caído.
        app.state.adaptador_iris = AdaptadorIris(settings)
        app.state.catalogo_partidos = CatalogoPartidos(app.state.adaptador_neo4j, settings)
        if iniciar_catalogo:
            # Con Neo4j caído la API arranca igual y el catálogo queda "no_cargado" (§3.2).
            app.state.catalogo_partidos.iniciar()
        try:
            yield
        finally:
            app.state.catalogo_partidos.detener()
            app.state.adaptador_mongo.cerrar()
            app.state.adaptador_redis.cerrar()
            app.state.adaptador_neo4j.cerrar()
            app.state.adaptador_cassandra.cerrar()
            app.state.adaptador_influx.cerrar()
            app.state.adaptador_iris.cerrar()

    app = FastAPI(
        title="Fixture 2030 · API integrada",
        version="0.8.0",
        description=DESCRIPCION,
        lifespan=lifespan,
    )
    instalar_openapi(app)
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    registrar_manejadores(app)
    app.include_router(salud.router)
    app.include_router(equipos.router)
    app.include_router(jugadores.router)
    app.include_router(partidos.router)
    app.include_router(sesiones.router)
    app.include_router(cache.router)
    app.include_router(comentarios.router)
    app.include_router(estadisticas.router)
    app.include_router(actas.router)
    return app


app = create_app()
