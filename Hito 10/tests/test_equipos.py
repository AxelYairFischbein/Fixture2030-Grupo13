"""CU-01 (sin caché), CU-02 y CU-03 con el adaptador MongoDB falso."""

import pytest

from app.errors import DependenciaNoDisponible, DependenciaTimeout

CAMPOS_FICHA = {
    "equipoId", "codigo", "nombre", "confederacion", "region", "rankingReferencia",
    "sedeBase", "participacionesMundiales", "titulosMundiales", "estado",
}


def _error(respuesta, http_status: int, codigo: str) -> dict:
    assert respuesta.status_code == http_status
    error = respuesta.json()["error"]
    assert error["codigo"] == codigo
    assert error["requestId"] == respuesta.headers["X-Request-Id"]
    return error


# CU-01 · ficha de equipo

def test_ficha_de_equipo(client):
    respuesta = client.get("/api/v1/equipos/EQ-001")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == CAMPOS_FICHA
    assert cuerpo["equipoId"] == "EQ-001"
    assert cuerpo["sedeBase"] == {"ciudad": "Ciudad 01", "pais": "Pais 01"}


def test_ficha_de_equipo_inexistente(client):
    error = _error(client.get("/api/v1/equipos/EQ-999"), 404, "EQUIPO_NO_ENCONTRADO")
    assert error["detalles"] == [{"campo": "equipoId", "problema": "EQ-999 no existe"}]


@pytest.mark.parametrize("equipo_id", ["EQ-1", "EQ-0001", "eq-001", "XX-001"])
def test_ficha_con_formato_invalido_no_consulta(client, mongo_falso, equipo_id):
    _error(client.get(f"/api/v1/equipos/{equipo_id}"), 400, "VALIDACION")
    assert mongo_falso.llamadas == []


# CU-02 · listado por confederación

def test_listado_ordenado_por_ranking(client):
    respuesta = client.get("/api/v1/equipos", params={"confederacion": "CONMEBOL"})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert [i["equipoId"] for i in cuerpo["items"]] == ["EQ-002", "EQ-001"]
    assert set(cuerpo["items"][0]) == {"equipoId", "codigo", "nombre", "rankingReferencia"}
    assert (cuerpo["pagina"], cuerpo["limite"], cuerpo["total"]) == (1, 20, 2)


def test_listado_con_ranking_max_y_paginas(client):
    cuerpo = client.get("/api/v1/equipos", params={
        "confederacion": "CONMEBOL", "rankingMax": 50, "limite": 1, "pagina": 2,
    }).json()
    assert [i["equipoId"] for i in cuerpo["items"]] == ["EQ-001"]
    assert cuerpo["total"] == 2


def test_listado_sin_coincidencias_es_200_vacio(client):
    cuerpo = client.get("/api/v1/equipos", params={"confederacion": "OFC"}).json()
    assert cuerpo["items"] == [] and cuerpo["total"] == 0


@pytest.mark.parametrize("params", [
    {},                                                     # confederación obligatoria
    {"confederacion": "FIFA"},                              # fuera del enum
    {"confederacion": "conmebol"},
    {"confederacion": "UEFA", "rankingMax": 0},
    {"confederacion": "UEFA", "rankingMax": 251},
    {"confederacion": "UEFA", "limite": 51},
    {"confederacion": "UEFA", "pagina": 0},
])
def test_listado_con_filtros_invalidos_no_consulta(client, mongo_falso, params):
    _error(client.get("/api/v1/equipos", params=params), 400, "VALIDACION")
    assert mongo_falso.llamadas == []


# CU-03 · plantel

def test_plantel_ordenado_por_apellido_nombre_id(client):
    cuerpo = client.get("/api/v1/equipos/EQ-001/jugadores").json()
    assert cuerpo["equipoId"] == "EQ-001"
    assert [i["jugadorId"] for i in cuerpo["items"]] == ["JUG-0002", "JUG-0003", "JUG-0001"]
    assert set(cuerpo["items"][0]) == {
        "jugadorId", "nombre", "apellido", "posicion", "numeroCamiseta", "estadoPlantel",
    }
    assert (cuerpo["pagina"], cuerpo["limite"], cuerpo["total"]) == (1, 24, 3)


def test_plantel_paginado_y_filtrado(client):
    cuerpo = client.get("/api/v1/equipos/EQ-001/jugadores",
                        params={"limite": 1, "pagina": 2}).json()
    assert [i["jugadorId"] for i in cuerpo["items"]] == ["JUG-0003"]
    cuerpo = client.get("/api/v1/equipos/EQ-001/jugadores",
                        params={"posicion": "ARQUERO"}).json()
    assert [i["jugadorId"] for i in cuerpo["items"]] == ["JUG-0001"]


def test_plantel_de_equipo_inexistente_es_404(client, mongo_falso):
    _error(client.get("/api/v1/equipos/EQ-999/jugadores"), 404, "EQUIPO_NO_ENCONTRADO")
    assert mongo_falso.llamadas == ["existe_equipo"]


def test_plantel_vacio_de_equipo_existente_es_200(client):
    respuesta = client.get("/api/v1/equipos/EQ-003/jugadores")
    assert respuesta.status_code == 200
    assert respuesta.json()["items"] == []
    cuerpo = client.get("/api/v1/equipos/EQ-002/jugadores", params={"posicion": "DELANTERO"}).json()
    assert cuerpo["items"] == [] and cuerpo["total"] == 0


@pytest.mark.parametrize("params", [
    {"limite": 25}, {"limite": 0}, {"pagina": 0}, {"posicion": "VOLANTE"},
])
def test_plantel_con_parametros_invalidos_no_consulta(client, mongo_falso, params):
    _error(client.get("/api/v1/equipos/EQ-001/jugadores", params=params), 400, "VALIDACION")
    assert mongo_falso.llamadas == []


# Dependencia caída o lenta: nunca 200 vacío

@pytest.mark.parametrize("ruta", [
    "/api/v1/equipos/EQ-001",
    "/api/v1/equipos?confederacion=UEFA",
    "/api/v1/equipos/EQ-001/jugadores",
])
@pytest.mark.parametrize("falla, http_status, codigo", [
    (DependenciaNoDisponible("mongodb"), 503, "DEPENDENCIA_NO_DISPONIBLE"),
    (DependenciaTimeout("mongodb"), 504, "DEPENDENCIA_TIMEOUT"),
])
def test_dependencia_caida(client, mongo_falso, ruta, falla, http_status, codigo):
    mongo_falso.falla = falla
    _error(client.get(ruta), http_status, codigo)
