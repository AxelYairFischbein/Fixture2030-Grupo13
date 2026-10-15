"""Integración con el contenedor Neo4j del Hito 5 (muestra cargada con ejecutar.ps1 carga).

settings_reales (tests/integracion/conftest.py) lee Hito 10/.env. Los resultados
esperados son los de cada ficha de casos_de_uso.md (Q04, Q06, Q07 y Q09 del Hito 5).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.integration

DIA_1 = {"desde": "2030-06-10T00:00:00Z", "hasta": "2030-06-11T00:00:00Z"}


@pytest.fixture(scope="module")
def settings_neo4j(settings_reales):
    if "completar_localmente" in (settings_reales.neo4j_user,
                                  settings_reales.neo4j_password.get_secret_value()):
        pytest.skip("NEO4J_USER / NEO4J_PASSWORD de Hito 10/.env tienen el valor de relleno")
    return settings_reales


@pytest.fixture(scope="module")
def cliente_api(settings_neo4j):
    with TestClient(create_app(settings_neo4j)) as cliente:
        salud = cliente.get("/api/v1/salud").json()
        if salud["dependencias"]["neo4j"] != "disponible":
            pytest.skip("Neo4j no responde: verificar el contenedor del Hito 5 "
                        "y las credenciales de Hito 10/.env")
        if salud["catalogoPartidos"]["partidos"] == 0:
            pytest.skip("Neo4j no tiene la muestra del Hito 5: ejecutar "
                        "'Hito 5/scripts/ejecutar.ps1 carga'")
        yield cliente


def test_salud_informa_catalogo_cargado_con_64_partidos(cliente_api):
    salud = cliente_api.get("/api/v1/salud").json()
    assert salud["dependencias"]["neo4j"] == "disponible"
    assert salud["catalogoPartidos"]["estado"] == "cargado"
    assert salud["catalogoPartidos"]["partidos"] == 64
    assert salud["catalogoPartidos"]["ultimaCarga"] is not None


def test_cu05_agenda_de_eq001_como_q04_q06(cliente_api):
    respuesta = cliente_api.get("/api/v1/equipos/EQ-001/partidos")
    assert respuesta.status_code == 200
    items = respuesta.json()["items"]
    assert [(p["partidoId"], p["rival"]["equipoId"], p["rol"], p["estadio"]["estadioId"])
            for p in items] == [("PAR-001", "EQ-002", "LOCAL", "EST-01"),
                                ("PAR-033", "EQ-003", "LOCAL", "EST-01")]
    assert items[0]["inicio"] == "2030-06-10T18:00:00Z"
    assert items[1]["inicio"] == "2030-06-14T18:00:00Z"
    assert all("estado" not in p for p in items)


def test_cu05_equipo_inexistente(cliente_api):
    respuesta = cliente_api.get("/api/v1/equipos/EQ-999/partidos")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "EQUIPO_NO_ENCONTRADO"


def test_cu06_eventos_de_par001_como_q07(cliente_api):
    respuesta = cliente_api.get("/api/v1/partidos/PAR-001/eventos")
    assert respuesta.status_code == 200
    eventos = respuesta.json()["items"]
    assert [(e["minuto"], [(p["jugadorId"], p["equipoId"], p["rol"]) for p in e["participantes"]])
            for e in eventos] == [
        (60, [("JUG-0020", "EQ-001", "SALE"), ("JUG-0021", "EQ-001", "ENTRA")]),
        (65, [("JUG-0044", "EQ-002", "SALE"), ("JUG-0045", "EQ-002", "ENTRA")]),
    ]
    assert sum(len(e["participantes"]) for e in eventos) == 4


def test_cu06_limite_cuenta_eventos(cliente_api):
    eventos = cliente_api.get("/api/v1/partidos/PAR-001/eventos", params={"limite": 1}).json()
    assert [e["minuto"] for e in eventos["items"]] == [60]
    assert len(eventos["items"][0]["participantes"]) == 2


def test_cu06_partido_inexistente(cliente_api):
    respuesta = cliente_api.get("/api/v1/partidos/PAR-999/eventos")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "PARTIDO_NO_ENCONTRADO"


def test_cu07_primer_dia_como_q09(cliente_api):
    respuesta = cliente_api.get("/api/v1/partidos", params=DIA_1)
    assert respuesta.status_code == 200
    items = respuesta.json()["items"]
    assert [(p["partidoId"], p["estadio"]["estadioId"]) for p in items] == [
        (f"PAR-{n:03d}", f"EST-{n:02d}") for n in range(1, 9)]
    assert all("estado" not in p for p in items)


def test_cu07_estadio_inexistente_es_vacio_valido(cliente_api):
    respuesta = cliente_api.get("/api/v1/partidos", params=DIA_1 | {"estadioId": "EST-99"})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"items": []}


def test_cu07_intervalo_invertido_es_400(cliente_api):
    respuesta = cliente_api.get("/api/v1/partidos", params={
        "desde": DIA_1["hasta"], "hasta": DIA_1["desde"]})
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"


def test_api_arranca_con_neo4j_inaccesible(settings_reales):
    # Puerto cerrado: la API arranca, el catálogo queda no_cargado y CU-05 responde 503.
    # No necesita credenciales de Neo4j ni la muestra cargada.
    settings = settings_reales.model_copy(update={
        "neo4j_uri": "bolt://127.0.0.1:1", "neo4j_connection_timeout_s": 0.5})
    with TestClient(create_app(settings)) as cliente:
        salud = cliente.get("/api/v1/salud").json()
        assert salud["dependencias"]["neo4j"] == "no_disponible"
        assert salud["catalogoPartidos"] == {"estado": "no_cargado", "partidos": 0,
                                             "ultimaCarga": None}
        respuesta = cliente.get("/api/v1/equipos/EQ-001/partidos")
        assert respuesta.status_code == 503
        assert respuesta.json()["error"]["codigo"] == "DEPENDENCIA_NO_DISPONIBLE"
