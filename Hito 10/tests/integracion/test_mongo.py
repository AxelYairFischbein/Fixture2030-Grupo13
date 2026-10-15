"""Integración con el contenedor MongoDB del Hito 4 (fixture2030-mongodb).

Settings se arma desde Hito 10/.env de forma explícita: el conftest reemplaza
las variables de entorno por valores ficticios para las pruebas unitarias.
"""

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from pymongo import ASCENDING, MongoClient

from app.config.settings import RAIZ_HITO10, Settings
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def settings_reales() -> Settings:
    archivo = RAIZ_HITO10 / ".env"
    if not archivo.exists():
        pytest.skip("Falta Hito 10/.env con las credenciales locales de MongoDB")
    valores = {k.lower(): v for k, v in dotenv_values(archivo).items() if v}
    if "completar_localmente" in (valores.get("mongo_user"), valores.get("mongo_password")):
        pytest.skip("MONGO_USER / MONGO_PASSWORD de Hito 10/.env tienen el valor de relleno")
    return Settings(_env_file=None, **valores)


@pytest.fixture(scope="module")
def cliente_api(settings_reales):
    with TestClient(create_app(settings_reales)) as cliente:
        if cliente.get("/api/v1/salud").json()["dependencias"]["mongodb"] != "disponible":
            pytest.skip("MongoDB no responde al ping: verificar el contenedor del Hito 4 "
                        "y las credenciales de Hito 10/.env")
        yield cliente


@pytest.fixture(scope="module")
def db_directa(settings_reales):
    cliente = MongoClient(
        host=settings_reales.mongo_host, port=settings_reales.mongo_port,
        username=settings_reales.mongo_user,
        password=settings_reales.mongo_password.get_secret_value(),
        authSource=settings_reales.mongo_auth_db, serverSelectionTimeoutMS=2000,
    )
    yield cliente[settings_reales.mongo_db]
    cliente.close()


def test_salud_informa_mongodb_disponible(cliente_api):
    assert cliente_api.get("/api/v1/salud").json()["dependencias"]["mongodb"] == "disponible"


def test_cu01_ficha_de_equipo(cliente_api):
    respuesta = cliente_api.get("/api/v1/equipos/EQ-001")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["equipoId"] == "EQ-001"
    assert set(cuerpo) == {
        "equipoId", "codigo", "nombre", "confederacion", "region", "rankingReferencia",
        "sedeBase", "participacionesMundiales", "titulosMundiales", "estado",
    }


def test_cu01_equipo_inexistente(cliente_api):
    respuesta = cliente_api.get("/api/v1/equipos/EQ-999")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "EQUIPO_NO_ENCONTRADO"


def test_cu02_conmebol_ranking_50_igual_que_q03(cliente_api, db_directa):
    cuerpo = cliente_api.get(
        "/api/v1/equipos", params={"confederacion": "CONMEBOL", "rankingMax": 50}
    ).json()
    q03 = list(db_directa.equipos.find(
        {"confederacion": "CONMEBOL", "rankingReferencia": {"$lte": 50}},
        {"_id": 0, "equipoId": 1},
    ).sort([("rankingReferencia", ASCENDING), ("equipoId", ASCENDING)]))
    assert cuerpo["total"] == 8
    assert [i["equipoId"] for i in cuerpo["items"]] == [d["equipoId"] for d in q03]


def test_cu03_eq002_tiene_24_jugadores(cliente_api):
    cuerpo = cliente_api.get("/api/v1/equipos/EQ-002/jugadores").json()
    assert cuerpo["total"] == 24
    assert len(cuerpo["items"]) == 24


def test_cu03_pagina_2_de_eq001_coincide_con_q06(cliente_api, db_directa):
    cuerpo = cliente_api.get(
        "/api/v1/equipos/EQ-001/jugadores", params={"limite": 5, "pagina": 2}
    ).json()
    q06 = list(db_directa.jugadores.find(
        {"equipoId": "EQ-001"},
        {"_id": 0, "jugadorId": 1, "apellido": 1, "nombre": 1, "posicion": 1, "numeroCamiseta": 1},
    ).sort([("apellido", 1), ("nombre", 1), ("jugadorId", 1)]).skip(5).limit(5))
    campos = ("jugadorId", "apellido", "nombre", "posicion", "numeroCamiseta")
    assert [{k: i[k] for k in campos} for i in cuerpo["items"]] == q06
    # Resultado registrado en Hito 4/evidencias/10_consultas_y_agregaciones.txt
    assert [i["jugadorId"] for i in cuerpo["items"]] == [f"JUG-{n:04d}" for n in range(6, 11)]


def test_cu04_ficha_de_jugador_sin_huerfanos(cliente_api):
    respuesta = cliente_api.get("/api/v1/jugadores/JUG-0313")
    assert respuesta.status_code == 200
    jugador = respuesta.json()
    assert jugador["jugadorId"] == "JUG-0313"
    assert "_id" not in jugador and "creadoEn" not in jugador
    assert cliente_api.get(f"/api/v1/equipos/{jugador['equipoId']}").status_code == 200


def test_cu04_jugador_inexistente(cliente_api):
    assert cliente_api.get("/api/v1/jugadores/JUG-9999").status_code == 404