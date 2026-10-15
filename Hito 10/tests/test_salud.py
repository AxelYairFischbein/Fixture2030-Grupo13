"""GET /api/v1/salud y carga de la configuración."""

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings, cargar_settings
from app.dependencias import obtener_catalogo_partidos
from app.errors import DependenciaNoDisponible
from app.services.catalogo_partidos import CatalogoPartidos


SIN_ADAPTADOR = ("cassandra", "influxdb", "iris")


def test_salud_con_mongodb_redis_y_neo4j_disponibles(client):
    respuesta = client.get("/api/v1/salud")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["dependencias"] == (
        {"mongodb": "disponible", "redis": "disponible", "neo4j": "disponible"}
        | {n: "no_configurada" for n in SIN_ADAPTADOR}
    )
    catalogo = cuerpo["catalogoPartidos"]
    assert catalogo["estado"] == "cargado"
    assert catalogo["partidos"] == 3
    assert catalogo["ultimaCarga"].endswith("Z")


def test_salud_con_neo4j_caido_y_catalogo_no_cargado(app, neo4j_falso):
    neo4j_falso.falla = DependenciaNoDisponible("neo4j")
    catalogo = CatalogoPartidos(neo4j_falso, Settings(_env_file=None))
    catalogo.cargar()
    app.dependency_overrides[obtener_catalogo_partidos] = lambda: catalogo
    with TestClient(app) as cliente:
        respuesta = cliente.get("/api/v1/salud")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "degradado"
    assert cuerpo["dependencias"]["neo4j"] == "no_disponible"
    assert cuerpo["catalogoPartidos"] == {"estado": "no_cargado", "partidos": 0,
                                          "ultimaCarga": None}


def test_salud_no_recarga_el_catalogo(app, neo4j_falso):
    neo4j_falso.falla = DependenciaNoDisponible("neo4j")
    catalogo = CatalogoPartidos(neo4j_falso, Settings(_env_file=None))
    app.dependency_overrides[obtener_catalogo_partidos] = lambda: catalogo
    with TestClient(app) as cliente:
        cliente.get("/api/v1/salud")
    assert "cargar_catalogo_partidos" not in neo4j_falso.llamadas


def test_salud_con_mongodb_caido_es_degradado_pero_200(client, mongo_falso):
    mongo_falso.falla = RuntimeError("caído")
    respuesta = client.get("/api/v1/salud")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "degradado"
    assert respuesta.json()["dependencias"]["mongodb"] == "no_disponible"


def test_salud_con_redis_caido_es_degradado_pero_200(client, redis_falso):
    redis_falso.falla = RuntimeError("caído")
    respuesta = client.get("/api/v1/salud")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "degradado"
    assert respuesta.json()["dependencias"]["redis"] == "no_disponible"


def test_falta_una_contrasena_nombra_la_variable(monkeypatch):
    monkeypatch.delenv("MONGO_PASSWORD")
    with pytest.raises(RuntimeError) as exc:
        cargar_settings(_env_file=None)
    mensaje = str(exc.value)
    assert "MONGO_PASSWORD" in mensaje
    assert "valor-de-prueba" not in mensaje


def test_contrasena_vacia_cuenta_como_faltante(monkeypatch):
    monkeypatch.setenv("IRIS_PASSWORD", "")
    with pytest.raises(RuntimeError, match="IRIS_PASSWORD"):
        cargar_settings(_env_file=None)


def test_timeouts_por_defecto_de_la_seccion_6_3():
    settings = Settings(_env_file=None)
    assert settings.mongo_server_selection_timeout_s == 2
    assert settings.redis_socket_timeout_s == 0.5
    assert settings.influx_timeout_s == 5
    assert "valor-de-prueba" not in repr(settings)
