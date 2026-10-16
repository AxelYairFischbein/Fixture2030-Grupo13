"""Fixtures comunes de las pruebas unitarias (sin Docker).

Las variables obligatorias se completan con valores ficticios antes de importar
la app, para que app.main pueda crear la aplicación sin un .env real. El token de
InfluxDB es un archivo temporal con un valor ficticio: el adaptador lo lee al crearse.
"""

import atexit
import os
import tempfile
from typing import Annotated

_descriptor, TOKEN_INFLUX_DE_PRUEBA = tempfile.mkstemp(suffix=".token")
os.write(_descriptor, b"token-ficticio-de-prueba")
os.close(_descriptor)
atexit.register(lambda: os.path.exists(TOKEN_INFLUX_DE_PRUEBA) and os.remove(TOKEN_INFLUX_DE_PRUEBA))

VARIABLES_DE_PRUEBA = {
    "MONGO_USER": "usuario-de-prueba",
    "MONGO_PASSWORD": "valor-de-prueba",
    "NEO4J_USER": "usuario-de-prueba",
    "NEO4J_PASSWORD": "valor-de-prueba",
    "INFLUX_TOKEN_FILE": TOKEN_INFLUX_DE_PRUEBA,
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
from app.dependencias import (  # noqa: E402
    obtener_adaptador_cassandra,
    obtener_adaptador_influx,
    obtener_adaptador_mongo,
    obtener_adaptador_neo4j,
    obtener_adaptador_redis,
    obtener_catalogo_partidos,
)
from app.main import create_app  # noqa: E402
from app.services.catalogo_partidos import CatalogoPartidos  # noqa: E402
from tests.falsos import (  # noqa: E402
    CassandraFalso,
    InfluxFalso,
    MongoFalso,
    Neo4jFalso,
    RedisFalso,
)


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
def redis_falso() -> RedisFalso:
    return RedisFalso()


@pytest.fixture
def neo4j_falso() -> Neo4jFalso:
    return Neo4jFalso()


@pytest.fixture
def cassandra_falso() -> CassandraFalso:
    return CassandraFalso()


@pytest.fixture
def influx_falso() -> InfluxFalso:
    return InfluxFalso()


@pytest.fixture
def catalogo(neo4j_falso) -> CatalogoPartidos:
    """Catálogo cargado desde el Neo4j falso (sin hilo de refresco)."""
    catalogo = CatalogoPartidos(neo4j_falso, Settings(_env_file=None))
    catalogo.cargar()
    neo4j_falso.llamadas.clear()
    return catalogo


@pytest.fixture
def app(mongo_falso, redis_falso, neo4j_falso, cassandra_falso, influx_falso, catalogo):
    # iniciar_catalogo=False: el lifespan no intenta conectarse a un Neo4j real.
    aplicacion = create_app(Settings(_env_file=None), iniciar_catalogo=False)
    aplicacion.include_router(_router_de_prueba())
    aplicacion.dependency_overrides[obtener_adaptador_mongo] = lambda: mongo_falso
    aplicacion.dependency_overrides[obtener_adaptador_redis] = lambda: redis_falso
    aplicacion.dependency_overrides[obtener_adaptador_neo4j] = lambda: neo4j_falso
    aplicacion.dependency_overrides[obtener_adaptador_cassandra] = lambda: cassandra_falso
    aplicacion.dependency_overrides[obtener_adaptador_influx] = lambda: influx_falso
    aplicacion.dependency_overrides[obtener_catalogo_partidos] = lambda: catalogo
    return aplicacion


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente
