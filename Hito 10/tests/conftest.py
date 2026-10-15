"""Fixtures comunes de las pruebas unitarias (sin Docker).

Las variables obligatorias se completan con valores ficticios antes de importar
la app, para que app.main pueda crear la aplicación sin un .env real.
"""

import os
from typing import Annotated

VARIABLES_DE_PRUEBA = {
    "MONGO_USER": "usuario-de-prueba",
    "MONGO_PASSWORD": "valor-de-prueba",
    "NEO4J_USER": "usuario-de-prueba",
    "NEO4J_PASSWORD": "valor-de-prueba",
    "INFLUX_TOKEN_FILE": "ruta/de/prueba.token",
    "IRIS_USER": "usuario-de-prueba",
    "IRIS_PASSWORD": "valor-de-prueba",
}
for _nombre, _valor in VARIABLES_DE_PRUEBA.items():
    os.environ[_nombre] = _valor

import pytest  # noqa: E402
from fastapi import APIRouter, Path, Query  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config.settings import Settings  # noqa: E402
from app.errors import (  # noqa: E402
    Conflicto,
    DependenciaNoDisponible,
    DependenciaTimeout,
    NoEncontrado,
)
from app.dependencias import obtener_adaptador_mongo  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.falsos import MongoFalso  # noqa: E402


def _router_de_prueba() -> APIRouter:
    """Rutas auxiliares que existen solo en las pruebas para ejercitar los manejadores."""
    router = APIRouter(prefix="/prueba")

    @router.get("/equipos/{equipoId}")
    def ver_equipo(
        equipoId: Annotated[str, Path(pattern=r"^EQ-\d{3}$")],
        limite: Annotated[int, Query(ge=1, le=50)],
    ) -> dict:
        return {"equipoId": equipoId, "limite": limite}

    @router.get("/no-encontrado")
    def no_encontrado() -> dict:
        raise NoEncontrado(
            "PARTIDO_NO_ENCONTRADO",
            "No existe un partido con el identificador indicado.",
            [{"campo": "partidoId", "problema": "PAR-999 no existe"}],
        )

    @router.get("/conflicto")
    def conflicto() -> dict:
        raise Conflicto("TRANSICION_NO_PERMITIDA")

    @router.get("/caida")
    def caida() -> dict:
        raise DependenciaNoDisponible("mongodb")

    @router.get("/timeout")
    def timeout() -> dict:
        raise DependenciaTimeout("cassandra")

    @router.get("/inesperado")
    def inesperado() -> dict:
        raise RuntimeError("mongodb://usuario:secreto@127.0.0.1 detalle interno")

    return router


@pytest.fixture
def mongo_falso() -> MongoFalso:
    return MongoFalso()


@pytest.fixture
def app(mongo_falso):
    aplicacion = create_app(Settings(_env_file=None))
    aplicacion.include_router(_router_de_prueba())
    aplicacion.dependency_overrides[obtener_adaptador_mongo] = lambda: mongo_falso
    return aplicacion


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente
