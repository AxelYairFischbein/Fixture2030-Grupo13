"""GET /api/v1/salud y carga de la configuración."""

import pytest

from app.config.settings import Settings, cargar_settings


SIN_ADAPTADOR = ("neo4j", "cassandra", "redis", "influxdb", "iris")


def test_salud_con_mongodb_disponible(client):
    respuesta = client.get("/api/v1/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "estado": "ok",
        "dependencias": {"mongodb": "disponible"} | {n: "no_configurada" for n in SIN_ADAPTADOR},
    }


def test_salud_con_mongodb_caido_es_degradado_pero_200(client, mongo_falso):
    mongo_falso.falla = RuntimeError("caído")
    respuesta = client.get("/api/v1/salud")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "degradado"
    assert respuesta.json()["dependencias"]["mongodb"] == "no_disponible"


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
