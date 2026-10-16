"""Integración con el Redis del Hito 7 (puerto 16379) y, para CU-01, el MongoDB del Hito 4.

Cada prueba crea sus sesiones con IDs aleatorios y la misma estructura y EVAL que
Hito 7/scripts/carga_muestra.redis, y las borra al terminar. Los IDs no se imprimen.
"""

import secrets
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.integration

URL_SESION = "/api/v1/sesiones/actual"

# redis_directo y la fábrica de sesiones están en tests/integracion/conftest.py.


@pytest.fixture(scope="module")
def cliente_api(settings_reales, redis_directo):
    with TestClient(create_app(settings_reales)) as cliente:
        yield cliente


@pytest.fixture
def requiere_mongo(cliente_api):
    if cliente_api.get("/api/v1/salud").json()["dependencias"]["mongodb"] != "disponible":
        pytest.skip("MongoDB del Hito 4 no responde: CU-01 necesita la fuente de verdad")


def _encabezado(sesion_id: str) -> dict:
    return {"X-Session-Id": sesion_id}


def test_salud_informa_redis_disponible(cliente_api):
    assert cliente_api.get("/api/v1/salud").json()["dependencias"]["redis"] == "disponible"


# Sesiones

def test_cu11_sesion_vigente_no_renueva(cliente_api, redis_directo, sesiones):
    sesion_id, clave = sesiones(rol="moderador", ttl=600, usuario_id="USR-00002")
    actividad_antes = redis_directo.hget(clave, "ultima_actividad")
    respuesta = cliente_api.get(URL_SESION, headers=_encabezado(sesion_id))
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"usuarioId", "rol", "estado", "expiraEnSegundos"}
    assert (cuerpo["usuarioId"], cuerpo["rol"], cuerpo["estado"]) == ("USR-00002", "moderador", "activa")
    assert 0 < cuerpo["expiraEnSegundos"] <= 600
    assert redis_directo.ttl(clave) <= 600
    assert redis_directo.hget(clave, "ultima_actividad") == actividad_antes


def test_cu12_renueva_ttl_y_ultima_actividad(cliente_api, redis_directo, sesiones):
    sesion_id, clave = sesiones(ttl=60)
    actividad_antes = int(redis_directo.hget(clave, "ultima_actividad"))
    time.sleep(1.1)
    respuesta = cliente_api.post(f"{URL_SESION}/actividad", headers=_encabezado(sesion_id))
    assert respuesta.status_code == 200
    assert respuesta.json() == {"expiraEnSegundos": 1800}
    assert 1790 <= redis_directo.ttl(clave) <= 1800
    assert int(redis_directo.hget(clave, "ultima_actividad")) > actividad_antes


def test_sesion_vencida_por_ttl_corto(cliente_api, redis_directo, sesiones):
    # Igual que SES-CORTA del Hito 7: TTL de 3 s y espera de 4 s.
    sesion_id, clave = sesiones(ttl=3)
    assert cliente_api.get(URL_SESION, headers=_encabezado(sesion_id)).status_code == 200
    time.sleep(4)
    vencida = cliente_api.get(URL_SESION, headers=_encabezado(sesion_id))
    assert vencida.status_code == 401
    assert vencida.json()["error"]["codigo"] == "SESION_NO_VIGENTE"
    actividad = cliente_api.post(f"{URL_SESION}/actividad", headers=_encabezado(sesion_id))
    assert actividad.status_code == 401
    assert redis_directo.exists(clave) == 0  # la renovación no recrea la sesión


def test_sesion_sin_vencimiento_no_es_valida(cliente_api, redis_directo, sesiones):
    sesion_id, clave = sesiones()
    redis_directo.persist(clave)  # TTL -1: el Hito 7 no la acepta como sesión válida
    assert cliente_api.get(URL_SESION, headers=_encabezado(sesion_id)).status_code == 401
    assert cliente_api.post(f"{URL_SESION}/actividad", headers=_encabezado(sesion_id)).status_code == 401
    assert redis_directo.ttl(clave) == -1


def test_cu13_cierre_repetido_es_204(cliente_api, redis_directo, sesiones):
    sesion_id, clave = sesiones()
    assert cliente_api.delete(URL_SESION, headers=_encabezado(sesion_id)).status_code == 204
    assert redis_directo.exists(clave) == 0
    assert cliente_api.delete(URL_SESION, headers=_encabezado(sesion_id)).status_code == 204
    respuesta = cliente_api.get(URL_SESION, headers=_encabezado(sesion_id))
    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "SESION_NO_VIGENTE"


def test_sesion_inexistente_es_401(cliente_api):
    respuesta = cliente_api.get(URL_SESION, headers=_encabezado(f"SES-PRUEBA-{secrets.token_hex(16)}"))
    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "SESION_NO_VIGENTE"


# CU-01 cache-aside y CU-14 invalidación

def test_cu01_miss_hit_y_cu14_invalidacion(cliente_api, redis_directo, sesiones, settings_reales,
                                          requiere_mongo):
    clave_ficha = f"{settings_reales.redis_prefijo}cache:equipo:EQ-001"
    redis_directo.delete(clave_ficha)

    primera = cliente_api.get("/api/v1/equipos/EQ-001")
    assert (primera.status_code, primera.headers["X-Cache"]) == (200, "MISS")
    assert 0 < redis_directo.ttl(clave_ficha) <= 300
    segunda = cliente_api.get("/api/v1/equipos/EQ-001")
    assert (segunda.status_code, segunda.headers["X-Cache"]) == (200, "HIT")
    assert segunda.json() == primera.json()

    lector, clave_lector = sesiones(rol="lector", ttl=100)
    ruta = "/api/v1/cache/equipos/EQ-001"
    denegada = cliente_api.delete(ruta, headers=_encabezado(lector))
    assert denegada.status_code == 403
    assert redis_directo.exists(clave_ficha) == 1
    assert redis_directo.ttl(clave_lector) <= 100  # un intento rechazado no renueva

    operador, clave_operador = sesiones(rol="operador", ttl=100, usuario_id="USR-00003")
    assert cliente_api.delete(ruta, headers=_encabezado(operador)).status_code == 204
    assert redis_directo.exists(clave_ficha) == 0
    assert redis_directo.ttl(clave_operador) > 1700  # la operación cuenta como actividad
    assert cliente_api.delete(ruta, headers=_encabezado(operador)).status_code == 204

    tercera = cliente_api.get("/api/v1/equipos/EQ-001")
    assert (tercera.status_code, tercera.headers["X-Cache"]) == (200, "MISS")


# Redis no disponible: la API apunta a un puerto sin servicio (no se detiene el contenedor)

def test_redis_no_disponible_bypass_y_503(settings_reales, requiere_mongo):
    caido = settings_reales.model_copy(update={"redis_port": 1})
    with TestClient(create_app(caido)) as cliente:
        ficha = cliente.get("/api/v1/equipos/EQ-001")
        assert (ficha.status_code, ficha.headers["X-Cache"]) == (200, "BYPASS")
        assert ficha.json()["equipoId"] == "EQ-001"

        sesion = cliente.get(URL_SESION, headers=_encabezado("SES-PRUEBA-cualquiera"))
        assert sesion.status_code == 503  # nunca 401: Redis caído no invalida la sesión
        assert sesion.json()["error"]["codigo"] == "DEPENDENCIA_NO_DISPONIBLE"
        assert cliente.delete(URL_SESION, headers=_encabezado("SES-PRUEBA-cualquiera")).status_code == 503
        assert cliente.get("/api/v1/salud").json()["dependencias"]["redis"] == "no_disponible"
