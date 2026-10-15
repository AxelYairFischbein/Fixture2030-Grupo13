"""Punto de entrada: uvicorn app.main:app (ejecutar desde la carpeta Hito 10)."""

from fastapi import FastAPI

from app.config.logging import configurar_logging
from app.config.settings import Settings, cargar_settings
from app.manejadores import registrar_manejadores
from app.middleware import RequestIdMiddleware
from app.routes import salud


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or cargar_settings()
    configurar_logging(settings.log_level)

    app = FastAPI(
        title="Fixture 2030 · API integrada",
        version="0.1.0",
        description="API REST del Hito 10 (Grupo 13) sobre MongoDB, Neo4j, Cassandra, "
                    "Redis, InfluxDB e InterSystems IRIS.",
    )
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    registrar_manejadores(app)
    app.include_router(salud.router)
    return app


app = create_app()
