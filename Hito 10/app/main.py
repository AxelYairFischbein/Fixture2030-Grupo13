"""Punto de entrada: uvicorn app.main:app (ejecutar desde la carpeta Hito 10)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.mongo_adaptador import AdaptadorMongo
from app.adapters.redis_adaptador import AdaptadorRedis
from app.config.logging import configurar_logging
from app.config.settings import Settings, cargar_settings
from app.manejadores import registrar_manejadores
from app.middleware import RequestIdMiddleware
from app.routes import cache, equipos, jugadores, salud, sesiones


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or cargar_settings()
    configurar_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Los adaptadores se crean una vez y se comparten entre requests.
        app.state.adaptador_mongo = AdaptadorMongo(settings)
        app.state.adaptador_redis = AdaptadorRedis(settings)
        try:
            yield
        finally:
            app.state.adaptador_mongo.cerrar()
            app.state.adaptador_redis.cerrar()

    app = FastAPI(
        title="Fixture 2030 · API integrada",
        version="0.3.0",
        description="API REST del Hito 10 (Grupo 13) sobre MongoDB, Neo4j, Cassandra, "
                    "Redis, InfluxDB e InterSystems IRIS.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    registrar_manejadores(app)
    app.include_router(salud.router)
    app.include_router(equipos.router)
    app.include_router(jugadores.router)
    app.include_router(sesiones.router)
    app.include_router(cache.router)
    return app


app = create_app()
