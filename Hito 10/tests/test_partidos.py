"""CU-05, CU-06 y CU-07 con el adaptador Neo4j falso."""

import pytest

from app.errors import DependenciaNoDisponible, DependenciaTimeout

DIA = {"desde": "2030-06-10T00:00:00Z", "hasta": "2030-06-11T00:00:00Z"}


def _error(respuesta, http_status: int, codigo: str) -> dict:
    assert respuesta.status_code == http_status
    error = respuesta.json()["error"]
    assert error["codigo"] == codigo
    assert error["requestId"] == respuesta.headers["X-Request-Id"]
    return error


# CU-05 · agenda y rivales de un equipo

def test_agenda_de_eq001(client):
    respuesta = client.get("/api/v1/equipos/EQ-001/partidos")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["equipoId"] == "EQ-001"
    assert [(p["partidoId"], p["rival"]["equipoId"], p["rol"], p["estadio"]["estadioId"])
            for p in cuerpo["items"]] == [("PAR-001", "EQ-002", "LOCAL", "EST-01"),
                                           ("PAR-033", "EQ-003", "LOCAL", "EST-01")]
    primero = cuerpo["items"][0]
    assert primero["inicio"] == "2030-06-10T18:00:00Z"
    assert set(primero) == {"partidoId", "inicio", "grupo", "fase", "rol", "rival", "estadio"}
    assert set(primero["rival"]) == {"equipoId", "codigo", "nombre"}
    assert set(primero["estadio"]) == {"estadioId", "nombre", "ciudad"}


def test_agenda_no_incluye_el_estado_del_partido(client):
    # El estado pertenece a IRIS (casos_de_uso.md §3.1).
    for partido in client.get("/api/v1/equipos/EQ-001/partidos").json()["items"]:
        assert "estado" not in partido


def test_agenda_rol_visitante(client):
    items = client.get("/api/v1/equipos/EQ-003/partidos").json()["items"]
    assert [(p["partidoId"], p["rol"], p["rival"]["equipoId"]) for p in items] == [
        ("PAR-002", "LOCAL", "EQ-004"), ("PAR-033", "VISITANTE", "EQ-001")]


def test_agenda_respeta_el_limite(client):
    items = client.get("/api/v1/equipos/EQ-001/partidos", params={"limite": 1}).json()["items"]
    assert [p["partidoId"] for p in items] == ["PAR-001"]


def test_agenda_de_equipo_inexistente(client):
    error = _error(client.get("/api/v1/equipos/EQ-999/partidos"), 404, "EQUIPO_NO_ENCONTRADO")
    assert error["detalles"] == [{"campo": "equipoId", "problema": "EQ-999 no existe"}]


def test_agenda_de_equipo_sin_partidos_es_vacio_valido(client):
    respuesta = client.get("/api/v1/equipos/EQ-005/partidos")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"equipoId": "EQ-005", "items": []}


@pytest.mark.parametrize("ruta", [
    "/api/v1/equipos/EQ-1/partidos",
    "/api/v1/equipos/EQ-001/partidos?limite=0",
    "/api/v1/equipos/EQ-001/partidos?limite=51",
])
def test_agenda_con_entrada_invalida_no_consulta(client, neo4j_falso, ruta):
    _error(client.get(ruta), 400, "VALIDACION")
    assert neo4j_falso.llamadas == []


# CU-06 · eventos y participantes de un partido

def test_eventos_de_par001(client):
    respuesta = client.get("/api/v1/partidos/PAR-001/eventos")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["partidoId"] == "PAR-001"
    resumen = [(e["minuto"], [(p["jugadorId"], p["equipoId"], p["rol"])
                              for p in e["participantes"]]) for e in cuerpo["items"]]
    assert resumen == [
        (60, [("JUG-0020", "EQ-001", "SALE"), ("JUG-0021", "EQ-001", "ENTRA")]),
        (65, [("JUG-0044", "EQ-002", "SALE"), ("JUG-0045", "EQ-002", "ENTRA")]),
    ]
    assert set(cuerpo["items"][0]) == {"eventoId", "tipo", "minuto", "participantes"}
    assert set(cuerpo["items"][0]["participantes"][0]) == {
        "jugadorId", "nombre", "apellido", "equipoId", "rol"}


def test_eventos_limite_cuenta_eventos(client):
    cuerpo = client.get("/api/v1/partidos/PAR-001/eventos", params={"limite": 1}).json()
    assert len(cuerpo["items"]) == 1
    assert len(cuerpo["items"][0]["participantes"]) == 2


def test_eventos_de_partido_inexistente(client):
    error = _error(client.get("/api/v1/partidos/PAR-999/eventos"), 404, "PARTIDO_NO_ENCONTRADO")
    assert error["detalles"] == [{"campo": "partidoId", "problema": "PAR-999 no existe"}]


def test_eventos_de_partido_sin_eventos_es_vacio_valido(client):
    respuesta = client.get("/api/v1/partidos/PAR-002/eventos")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"partidoId": "PAR-002", "items": []}


@pytest.mark.parametrize("ruta", [
    "/api/v1/partidos/PAR-1/eventos",
    "/api/v1/partidos/par-001/eventos",
    "/api/v1/partidos/PAR-001/eventos?limite=0",
    "/api/v1/partidos/PAR-001/eventos?limite=201",
])
def test_eventos_con_entrada_invalida_no_consulta(client, neo4j_falso, ruta):
    _error(client.get(ruta), 400, "VALIDACION")
    assert neo4j_falso.llamadas == []


# CU-07 · partidos de un rango de fechas

def test_partidos_del_dia(client):
    respuesta = client.get("/api/v1/partidos", params=DIA)
    assert respuesta.status_code == 200
    items = respuesta.json()["items"]
    assert [(p["partidoId"], p["estadio"]["estadioId"]) for p in items] == [
        ("PAR-001", "EST-01"), ("PAR-002", "EST-02")]
    assert set(items[0]) == {"partidoId", "inicio", "grupo", "fase", "estadio"}
    assert items[0]["inicio"] == "2030-06-10T18:00:00Z"


def test_partidos_filtrados_por_estadio(client):
    items = client.get("/api/v1/partidos", params=DIA | {"estadioId": "EST-02"}).json()["items"]
    assert [p["partidoId"] for p in items] == ["PAR-002"]


def test_estadio_inexistente_es_vacio_valido(client):
    respuesta = client.get("/api/v1/partidos", params=DIA | {"estadioId": "EST-99"})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"items": []}


def test_intervalo_sin_partidos_es_vacio_valido(client):
    respuesta = client.get("/api/v1/partidos", params={
        "desde": "2030-07-01T00:00:00Z", "hasta": "2030-07-02T00:00:00Z"})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"items": []}


def test_fechas_con_offset_se_normalizan_a_utc(client, neo4j_falso):
    # 2030-06-10T15:00-03:00 = 18:00 UTC: el rango [15:00, 16:00) local incluye PAR-001.
    items = client.get("/api/v1/partidos", params={
        "desde": "2030-06-10T15:00:00-03:00", "hasta": "2030-06-10T16:00:00-03:00",
        "estadioId": "EST-01"}).json()["items"]
    assert [p["partidoId"] for p in items] == ["PAR-001"]


@pytest.mark.parametrize("params, campo", [
    ({"desde": "2030-06-11T00:00:00Z", "hasta": "2030-06-10T00:00:00Z"}, "hasta"),
    ({"desde": "2030-06-10T00:00:00Z", "hasta": "2030-06-10T00:00:00Z"}, "hasta"),
    ({"desde": "2030-06-01T00:00:00Z", "hasta": "2030-06-08T00:00:01Z"}, "hasta"),
    ({"hasta": "2030-06-11T00:00:00Z"}, "desde"),
    ({"desde": "2030-06-10T00:00:00Z"}, "hasta"),
    ({"desde": "2030-06-10T00:00:00", "hasta": "2030-06-11T00:00:00Z"}, "desde"),
    ({"desde": "ayer", "hasta": "2030-06-11T00:00:00Z"}, "desde"),
    (DIA | {"estadioId": "EST-1"}, "estadioId"),
    (DIA | {"limite": 0}, "limite"),
    (DIA | {"limite": 65}, "limite"),
])
def test_partidos_con_entrada_invalida_no_ejecuta_cypher(client, neo4j_falso, params, campo):
    error = _error(client.get("/api/v1/partidos", params=params), 400, "VALIDACION")
    assert campo in [d["campo"] for d in error["detalles"]]
    assert neo4j_falso.llamadas == []


def test_intervalo_de_7_dias_exactos_es_valido(client):
    respuesta = client.get("/api/v1/partidos", params={
        "desde": "2030-06-10T00:00:00Z", "hasta": "2030-06-17T00:00:00Z"})
    assert respuesta.status_code == 200
    assert [p["partidoId"] for p in respuesta.json()["items"]] == ["PAR-001", "PAR-002", "PAR-033"]


# Dependencia caída o lenta: nunca 200 vacío

@pytest.mark.parametrize("ruta", [
    "/api/v1/equipos/EQ-001/partidos",
    "/api/v1/partidos/PAR-001/eventos",
    "/api/v1/partidos?desde=2030-06-10T00:00:00Z&hasta=2030-06-11T00:00:00Z",
])
@pytest.mark.parametrize("falla, http_status, codigo", [
    (DependenciaNoDisponible("neo4j"), 503, "DEPENDENCIA_NO_DISPONIBLE"),
    (DependenciaTimeout("neo4j"), 504, "DEPENDENCIA_TIMEOUT"),
])
def test_neo4j_caido_o_lento(client, neo4j_falso, ruta, falla, http_status, codigo):
    neo4j_falso.falla = falla
    _error(client.get(ruta), http_status, codigo)
