"""CU-15, CU-16 y CU-17 sin Docker: validación previa, catálogo, agregaciones y fallas.

InfluxFalso tiene 20 min de PAR-001 (EQ-001 y EQ-002, un punto por segundo) desde
2026-10-16T00:00:00Z: EQ-001 suma un pase cada 10 s, EQ-002 cada 12 s, y cada equipo tiene
un tiro a los 900 s. Sobre [00:05, 00:10) reproduce la comparación del Hito 8: 300 muestras,
30 y 25 pases. PAR-002 está en el catálogo y no tiene puntos.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.dependencias import obtener_catalogo_partidos
from app.errors import DependenciaNoDisponible, DependenciaTimeout
from app.services.catalogo_partidos import CatalogoPartidos
from app.services.estadisticas import muestras_esperadas

RECIENTES = "/api/v1/partidos/{p}/equipos/{e}/estadisticas/recientes"
COMPARACION = "/api/v1/partidos/{p}/estadisticas/comparacion"
EVOLUCION = "/api/v1/partidos/{p}/estadisticas/evolucion"
VENTANA = {"desde": "2026-10-16T00:05:00Z", "hasta": "2026-10-16T00:10:00Z"}


def _error(respuesta, http_status: int, codigo: str) -> dict:
    assert respuesta.status_code == http_status, respuesta.text
    cuerpo = respuesta.json()["error"]
    assert cuerpo["codigo"] == codigo
    return cuerpo


def _por_equipo(respuesta) -> dict[str, dict]:
    assert respuesta.status_code == 200, respuesta.text
    return {e["equipoId"]: e for e in respuesta.json()["equipos"]}


# Cálculo de muestras esperadas

def test_muestras_esperadas_cuenta_multiplos_del_paso():
    t = datetime(2026, 10, 16, tzinfo=UTC)
    assert muestras_esperadas(t, t + timedelta(minutes=5), 1) == 300
    assert muestras_esperadas(t + timedelta(milliseconds=500), t + timedelta(seconds=3), 1) == 2
    assert muestras_esperadas(t, t + timedelta(seconds=60), 5) == 12


# CU-15

def test_cu15_devuelve_las_ultimas_observaciones_en_orden_descendente(client, influx_falso):
    respuesta = client.get(RECIENTES.format(p="PAR-001", e="EQ-001"),
                           params={"hasta": "2026-10-16T00:10:00Z"})
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["partidoId"] == "PAR-001" and cuerpo["equipoId"] == "EQ-001"
    assert cuerpo["estadioId"] == "EST-01"
    tiempos = [i["time"] for i in cuerpo["items"]]
    assert tiempos == [f"2026-10-16T00:09:{s}Z" for s in (59, 58, 57, 56, 55)]
    assert cuerpo["ultimaObservacion"] == "2026-10-16T00:09:59Z"
    assert cuerpo["items"][0] == {"time": "2026-10-16T00:09:59Z", "posesionPct": 52.0,
                                  "pasesAcumulados": 59, "tirosIntervalo": 0}
    assert influx_falso.llamadas == ["ultimas_observaciones"]


def test_cu15_respeta_el_limite_y_la_ventana_de_60_segundos(client):
    respuesta = client.get(RECIENTES.format(p="PAR-001", e="EQ-002"),
                           params={"hasta": "2026-10-16T00:00:30Z", "limite": 60})
    items = respuesta.json()["items"]
    assert len(items) == 30  # la serie empieza a las 00:00:00
    assert items[-1]["time"] == "2026-10-16T00:00:00Z"


def test_cu15_offset_se_normaliza_a_utc(client):
    respuesta = client.get(RECIENTES.format(p="PAR-001", e="EQ-001"),
                           params={"hasta": "2026-10-15T21:10:00-03:00", "limite": 1})
    assert respuesta.json()["ultimaObservacion"] == "2026-10-16T00:09:59Z"


def test_cu15_sin_puntos_es_200_vacio_con_ultima_observacion_null(client):
    respuesta = client.get(RECIENTES.format(p="PAR-002", e="EQ-003"),
                           params={"hasta": "2026-10-16T00:10:00Z"})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"partidoId": "PAR-002", "equipoId": "EQ-003", "estadioId": None,
                                "items": [], "ultimaObservacion": None}


def test_cu15_sin_hasta_usa_la_hora_actual(client):
    # La muestra falsa es de 2026-10-16: ahora no hay puntos y la respuesta es vacía, no error.
    respuesta = client.get(RECIENTES.format(p="PAR-001", e="EQ-001"))
    assert respuesta.status_code == 200
    assert respuesta.json()["items"] == []


@pytest.mark.parametrize("params", [
    {"limite": 0}, {"limite": 61}, {"hasta": "2026-10-16T00:10:00"}, {"hasta": "ayer"},
])
def test_cu15_entrada_invalida_es_400_sin_consultar(client, influx_falso, params):
    _error(client.get(RECIENTES.format(p="PAR-001", e="EQ-001"), params=params), 400, "VALIDACION")
    assert influx_falso.llamadas == []


@pytest.mark.parametrize("partido,equipo", [("PAR-1", "EQ-001"), ("PAR-001", "EQ-01")])
def test_cu15_identificador_invalido_es_400(client, influx_falso, partido, equipo):
    _error(client.get(RECIENTES.format(p=partido, e=equipo)), 400, "VALIDACION")
    assert influx_falso.llamadas == []


def test_cu15_partido_inexistente_es_404_sin_consultar(client, influx_falso):
    _error(client.get(RECIENTES.format(p="PAR-999", e="EQ-001")), 404, "PARTIDO_NO_ENCONTRADO")
    assert influx_falso.llamadas == []


def test_cu15_equipo_que_no_disputa_el_partido_es_404(client, influx_falso):
    cuerpo = _error(client.get(RECIENTES.format(p="PAR-001", e="EQ-003")), 404,
                    "EQUIPO_NO_PARTICIPA")
    assert cuerpo["detalles"] == [{"campo": "equipoId", "problema": "EQ-003 no disputa PAR-001"}]
    assert influx_falso.llamadas == []


# CU-16

def test_cu16_reproduce_la_comparacion_del_hito_8(client):
    equipos = _por_equipo(client.get(COMPARACION.format(p="PAR-001"), params=VENTANA))
    assert equipos["EQ-001"] == {
        "equipoId": "EQ-001", "muestras": 300, "muestrasEsperadas": 300, "posesionMedia": 50.0,
        "pasesNuevos": 30, "tiros": 0, "intervalosInvalidos": 0, "completo": True,
    }
    assert equipos["EQ-002"]["pasesNuevos"] == 25
    assert equipos["EQ-002"]["completo"] is True


def test_cu16_informa_la_ventana_en_utc(client):
    cuerpo = client.get(COMPARACION.format(p="PAR-001"), params={
        "desde": "2026-10-15T21:05:00-03:00", "hasta": "2026-10-15T21:10:00-03:00"}).json()
    assert (cuerpo["desde"], cuerpo["hasta"]) == ("2026-10-16T00:05:00Z", "2026-10-16T00:10:00Z")
    assert [e["equipoId"] for e in cuerpo["equipos"]] == ["EQ-001", "EQ-002"]


def test_cu16_sin_muestra_previa_marca_un_intervalo_invalido(client):
    # A las 00:00:00 no hay muestra anterior: el primer incremento no se puede calcular.
    equipos = _por_equipo(client.get(COMPARACION.format(p="PAR-001"), params={
        "desde": "2026-10-16T00:00:00Z", "hasta": "2026-10-16T00:05:00Z"}))
    assert equipos["EQ-001"]["intervalosInvalidos"] == 1
    assert equipos["EQ-001"]["completo"] is False


def test_cu16_huecos_y_contador_que_retrocede_dan_incompleto(client, influx_falso):
    hueco = datetime(2026, 10, 16, 0, 6, 0, tzinfo=UTC)
    influx_falso.puntos = [p for p in influx_falso.puntos
                           if not (p["equipo_id"] == "EQ-001" and p["time"] == hueco)]
    reinicio = datetime(2026, 10, 16, 0, 7, 0, tzinfo=UTC)
    for p in influx_falso.puntos:
        if p["equipo_id"] == "EQ-002" and p["time"] == reinicio:
            p["pases_acumulados"] = 0
    equipos = _por_equipo(client.get(COMPARACION.format(p="PAR-001"), params=VENTANA))
    assert equipos["EQ-001"]["muestras"] == 299
    assert equipos["EQ-001"]["intervalosInvalidos"] == 1  # separación de 2 s
    assert equipos["EQ-001"]["completo"] is False
    assert equipos["EQ-002"]["intervalosInvalidos"] == 1  # el contador retrocede
    assert equipos["EQ-002"]["completo"] is False


def test_cu16_partido_sin_puntos_es_200_vacio(client):
    respuesta = client.get(COMPARACION.format(p="PAR-002"), params=VENTANA)
    assert respuesta.status_code == 200
    assert respuesta.json()["equipos"] == []


@pytest.mark.parametrize("params", [
    {"desde": "2026-10-16T00:10:00Z", "hasta": "2026-10-16T00:05:00Z"},  # invertido
    {"desde": "2026-10-16T00:05:00Z", "hasta": "2026-10-16T00:05:00Z"},  # vacío
    {"desde": "2026-10-16T00:00:00Z", "hasta": "2026-10-16T00:06:00Z"},  # 6 min
    {"desde": "2026-10-16T00:05:00", "hasta": "2026-10-16T00:10:00Z"},   # sin zona
    {"desde": "2026-10-16T00:05:00Z"},                                    # falta hasta
])
def test_cu16_ventana_invalida_es_400_sin_consultar(client, influx_falso, params):
    _error(client.get(COMPARACION.format(p="PAR-001"), params=params), 400, "VALIDACION")
    assert influx_falso.llamadas == []


def test_cu16_partido_inexistente_es_404(client, influx_falso):
    _error(client.get(COMPARACION.format(p="PAR-999"), params=VENTANA), 404,
           "PARTIDO_NO_ENCONTRADO")
    assert influx_falso.llamadas == []


def test_cu16_ventana_invalida_tiene_prioridad_sobre_el_partido(client):
    params = {"desde": "2026-10-16T00:10:00Z", "hasta": "2026-10-16T00:05:00Z"}
    _error(client.get(COMPARACION.format(p="PAR-999"), params=params), 400, "VALIDACION")


# CU-17

def test_cu17_cinco_intervalos_por_equipo_que_suman_la_comparacion(client):
    evolucion = client.get(EVOLUCION.format(p="PAR-001"), params=VENTANA)
    assert evolucion.status_code == 200, evolucion.text
    cuerpo = evolucion.json()
    assert cuerpo["resolucion"] == "1m"
    comparacion = _por_equipo(client.get(COMPARACION.format(p="PAR-001"), params=VENTANA))
    assert [s["equipoId"] for s in cuerpo["series"]] == ["EQ-001", "EQ-002"]
    for serie in cuerpo["series"]:
        intervalos = serie["intervalos"]
        assert [i["inicio"] for i in intervalos] == [
            f"2026-10-16T00:0{m}:00Z" for m in range(5, 10)]
        assert all(i["muestras"] == i["muestrasEsperadas"] == 60 and i["completo"]
                   for i in intervalos)
        total = comparacion[serie["equipoId"]]
        for medida in ("muestras", "pasesNuevos", "tiros", "intervalosInvalidos"):
            assert sum(i[medida] for i in intervalos) == total[medida], medida


def test_cu17_cinco_minutos_con_bins_cortados_por_la_ventana(client):
    cuerpo = client.get(EVOLUCION.format(p="PAR-001"), params={
        "desde": "2026-10-16T00:02:30Z", "hasta": "2026-10-16T00:07:30Z",
        "resolucion": "5m", "equipoId": "EQ-002"}).json()
    assert [s["equipoId"] for s in cuerpo["series"]] == ["EQ-002"]
    intervalos = cuerpo["series"][0]["intervalos"]
    assert [(i["inicio"], i["muestras"], i["muestrasEsperadas"], i["completo"])
            for i in intervalos] == [
        ("2026-10-16T00:00:00Z", 150, 150, True),
        ("2026-10-16T00:05:00Z", 150, 150, True),
    ]


def test_cu17_intervalo_con_tiro(client):
    cuerpo = client.get(EVOLUCION.format(p="PAR-001"), params={
        "desde": "2026-10-16T00:14:00Z", "hasta": "2026-10-16T00:16:00Z",
        "equipoId": "EQ-001"}).json()
    assert [i["tiros"] for i in cuerpo["series"][0]["intervalos"]] == [0, 1]


def test_cu17_ventana_de_dos_horas_es_valida(client):
    respuesta = client.get(EVOLUCION.format(p="PAR-001"), params={
        "desde": "2026-10-15T23:00:00Z", "hasta": "2026-10-16T01:00:00Z"})
    assert respuesta.status_code == 200
    # Los minutos sin puntos no se devuelven: 20 minutos con datos por equipo.
    assert [len(s["intervalos"]) for s in respuesta.json()["series"]] == [20, 20]


def test_cu17_partido_sin_puntos_es_200_vacio(client):
    respuesta = client.get(EVOLUCION.format(p="PAR-002"), params=VENTANA)
    assert respuesta.status_code == 200
    assert respuesta.json()["series"] == []


@pytest.mark.parametrize("params", [
    {"desde": "2026-10-16T00:00:00Z", "hasta": "2026-10-16T03:00:00Z"},  # 3 h
    {"desde": "2026-10-16T00:10:00Z", "hasta": "2026-10-16T00:05:00Z"},  # invertido
    {**VENTANA, "resolucion": "10m"},
    {**VENTANA, "equipoId": "EQ-1"},
])
def test_cu17_entrada_invalida_es_400_sin_consultar(client, influx_falso, params):
    _error(client.get(EVOLUCION.format(p="PAR-001"), params=params), 400, "VALIDACION")
    assert influx_falso.llamadas == []


def test_cu17_equipo_que_no_disputa_el_partido_es_404(client, influx_falso):
    _error(client.get(EVOLUCION.format(p="PAR-001"), params={**VENTANA, "equipoId": "EQ-004"}),
           404, "EQUIPO_NO_PARTICIPA")
    assert influx_falso.llamadas == []


# Catálogo y dependencia

@pytest.mark.parametrize("url,params", [
    (RECIENTES.format(p="PAR-001", e="EQ-001"), {}),
    (COMPARACION.format(p="PAR-001"), VENTANA),
    (EVOLUCION.format(p="PAR-001"), VENTANA),
])
def test_catalogo_no_cargado_es_503(app, neo4j_falso, influx_falso, url, params):
    neo4j_falso.falla = DependenciaNoDisponible("neo4j")
    sin_cargar = CatalogoPartidos(neo4j_falso, Settings(_env_file=None))
    app.dependency_overrides[obtener_catalogo_partidos] = lambda: sin_cargar
    with TestClient(app) as cliente:
        _error(cliente.get(url, params=params), 503, "DEPENDENCIA_NO_DISPONIBLE")
    assert influx_falso.llamadas == []


@pytest.mark.parametrize("falla,http_status,codigo", [
    (DependenciaNoDisponible("influxdb"), 503, "DEPENDENCIA_NO_DISPONIBLE"),
    (DependenciaTimeout("influxdb"), 504, "DEPENDENCIA_TIMEOUT"),
])
@pytest.mark.parametrize("url,params", [
    (RECIENTES.format(p="PAR-001", e="EQ-001"), {}),
    (COMPARACION.format(p="PAR-001"), VENTANA),
    (EVOLUCION.format(p="PAR-001"), VENTANA),
])
def test_influx_caido_o_lento_nunca_es_200_vacio(client, influx_falso, url, params, falla,
                                                 http_status, codigo):
    influx_falso.falla = falla
    _error(client.get(url, params=params), http_status, codigo)


def test_openapi_documenta_las_tres_rutas(client):
    rutas = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/partidos/{partidoId}/equipos/{equipoId}/estadisticas/recientes" in rutas
    assert "/api/v1/partidos/{partidoId}/estadisticas/comparacion" in rutas
    evolucion = rutas["/api/v1/partidos/{partidoId}/estadisticas/evolucion"]["get"]
    assert {"400", "404", "500", "503", "504"} <= set(evolucion["responses"])
