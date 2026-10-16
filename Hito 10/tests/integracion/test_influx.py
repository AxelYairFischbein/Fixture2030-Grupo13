"""Integración con el InfluxDB 3 Core del Hito 8 (muestra de scripts/carga_lotes.py).

La ventana de prueba se toma de Hito 8/datos/muestra.json porque las fechas son las de la
carga, no las del calendario 2030: CU-16 y CU-17 usan [fin − 300 s, fin), igual que
consultas_temporales.py y agregaciones.py. Con la carga del 2026-10-15 la ventana es
[2026-10-16T00:12:00Z, 2026-10-16T00:17:00Z).

El partido se valida contra el catálogo cargado desde Neo4j (Hito 5). Si Neo4j no está
levantado, se inyecta un catálogo estático con los participantes de PAR-001 y PAR-002.
"""

import json
import socket
import threading
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.adapters.influx_adaptador import AdaptadorInflux
from app.config.settings import RAIZ_HITO10
from app.dependencias import obtener_adaptador_influx, obtener_catalogo_partidos
from app.main import create_app
from app.services.catalogo_partidos import CARGADO
from app.services.partidos import partido_no_encontrado

pytestmark = pytest.mark.integration

MUESTRA = RAIZ_HITO10.parent / "Hito 8" / "datos" / "muestra.json"
RECIENTES = "/api/v1/partidos/{p}/equipos/{e}/estadisticas/recientes"
COMPARACION = "/api/v1/partidos/{p}/estadisticas/comparacion"
EVOLUCION = "/api/v1/partidos/{p}/estadisticas/evolucion"


class CatalogoEstatico:
    """Sustituto del catálogo cuando Neo4j no está levantado: los partidos de la muestra."""

    PARTIDOS = {"PAR-001": ("EQ-001", "EQ-002"), "PAR-002": ("EQ-003", "EQ-004")}

    def validar_partido(self, partido_id):
        if partido_id not in self.PARTIDOS:
            raise partido_no_encontrado(partido_id)
        return self.PARTIDOS[partido_id]

    def validar_participacion(self, partido_id, equipo_id):
        from app.errors import NoEncontrado

        if equipo_id not in self.validar_partido(partido_id):
            raise NoEncontrado("EQUIPO_NO_PARTICIPA")

    def estado(self):
        return {"estado": CARGADO, "partidos": len(self.PARTIDOS), "ultimaCarga": None}


def _iso(instante: datetime) -> str:
    return instante.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture(scope="module")
def muestra() -> dict:
    if not MUESTRA.exists():
        pytest.skip("Falta Hito 8/datos/muestra.json: ejecutar la carga del Hito 8")
    datos = json.loads(MUESTRA.read_text(encoding="utf-8"))
    fin = datetime.fromtimestamp(datos["fin"], UTC)
    return {**datos, "fin_dt": fin, "ventana": {"desde": _iso(fin - timedelta(seconds=300)),
                                                "hasta": _iso(fin)}}


@pytest.fixture(scope="module")
def cliente_api(settings_reales, muestra):
    try:
        app = create_app(settings_reales)
    except RuntimeError:
        pytest.skip("Falta el token de InfluxDB (INFLUX_TOKEN_FILE en Hito 10/.env)")
    with TestClient(app) as cliente:
        if not app.state.adaptador_influx.ping():
            pytest.skip('InfluxDB del Hito 8 no responde: docker compose -f "Hito 8/docker-compose.yml" up -d')
        if app.state.catalogo_partidos.estado()["estado"] != CARGADO:
            app.dependency_overrides[obtener_catalogo_partidos] = CatalogoEstatico
        yield cliente


def _por_equipo(respuesta) -> dict[str, dict]:
    assert respuesta.status_code == 200, respuesta.text
    return {e["equipoId"]: e for e in respuesta.json()["equipos"]}


def test_salud_informa_influxdb_disponible(cliente_api):
    assert cliente_api.get("/api/v1/salud").json()["dependencias"]["influxdb"] == "disponible"


def test_cu16_reproduce_la_comparacion_del_hito_8(cliente_api, muestra):
    equipos = _por_equipo(cliente_api.get(COMPARACION.format(p="PAR-001"),
                                          params=muestra["ventana"]))
    assert equipos == {
        "EQ-001": {"equipoId": "EQ-001", "muestras": 300, "muestrasEsperadas": 300,
                   "posesionMedia": 49.975, "pasesNuevos": 30, "tiros": 1,
                   "intervalosInvalidos": 0, "completo": True},
        "EQ-002": {"equipoId": "EQ-002", "muestras": 300, "muestrasEsperadas": 300,
                   "posesionMedia": 50.025, "pasesNuevos": 25, "tiros": 1,
                   "intervalosInvalidos": 0, "completo": True},
    }


def test_cu17_sumas_por_minuto_coinciden_con_cu16(cliente_api, muestra):
    ventana = muestra["ventana"]
    comparacion = _por_equipo(cliente_api.get(COMPARACION.format(p="PAR-001"), params=ventana))
    respuesta = cliente_api.get(EVOLUCION.format(p="PAR-001"), params=ventana)
    assert respuesta.status_code == 200, respuesta.text
    series = respuesta.json()["series"]
    assert [s["equipoId"] for s in series] == ["EQ-001", "EQ-002"]
    inicio = muestra["fin_dt"] - timedelta(seconds=300)
    for serie in series:
        intervalos = serie["intervalos"]
        assert [i["inicio"] for i in intervalos] == [
            _iso(inicio + timedelta(minutes=m)) for m in range(5)]
        assert all(i["muestras"] == 60 and i["completo"] for i in intervalos)
        total = comparacion[serie["equipoId"]]
        for medida in ("muestras", "pasesNuevos", "tiros", "intervalosInvalidos"):
            assert sum(i[medida] for i in intervalos) == total[medida], medida
    assert [sum(i["pasesNuevos"] for i in s["intervalos"]) for s in series] == [30, 25]


def test_cu17_cinco_minutos_con_bins_cortados_conserva_los_totales(cliente_api, muestra):
    # Los bins de 5 min están alineados a la época; la ventana de la muestra puede cortarlos.
    fin = muestra["fin_dt"]
    inicio = fin - timedelta(seconds=300)
    respuesta = cliente_api.get(EVOLUCION.format(p="PAR-001"), params={
        **muestra["ventana"], "resolucion": "5m", "equipoId": "EQ-002"})
    assert respuesta.status_code == 200, respuesta.text
    [serie] = respuesta.json()["series"]
    intervalos = serie["intervalos"]
    bins = sorted({_iso(datetime.fromtimestamp(s - s % 300, UTC))
                   for s in range(int(inicio.timestamp()), int(fin.timestamp()))})
    assert [i["inicio"] for i in intervalos] == bins
    assert all(i["muestras"] == i["muestrasEsperadas"] and i["completo"] for i in intervalos)
    assert (sum(i["muestras"] for i in intervalos), sum(i["pasesNuevos"] for i in intervalos),
            sum(i["tiros"] for i in intervalos)) == (300, 25, 1)


def test_cu15_ultimas_cinco_observaciones(cliente_api, muestra):
    fin = muestra["fin_dt"]
    respuesta = cliente_api.get(RECIENTES.format(p="PAR-001", e="EQ-001"),
                                params={"hasta": _iso(fin)})
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estadioId"] == "EST-01"
    assert [i["time"] for i in cuerpo["items"]] == [
        _iso(fin - timedelta(seconds=s)) for s in range(1, 6)]
    assert cuerpo["ultimaObservacion"] == _iso(fin - timedelta(seconds=1))


def test_ventana_fuera_de_la_carga_es_200_vacio(cliente_api, muestra):
    despues = muestra["fin_dt"] + timedelta(days=1)
    ventana = {"desde": _iso(despues), "hasta": _iso(despues + timedelta(minutes=5))}
    assert cliente_api.get(COMPARACION.format(p="PAR-001"), params=ventana).json()["equipos"] == []
    assert cliente_api.get(EVOLUCION.format(p="PAR-001"), params=ventana).json()["series"] == []
    recientes = cliente_api.get(RECIENTES.format(p="PAR-001", e="EQ-001"),
                                params={"hasta": ventana["hasta"]}).json()
    assert recientes["items"] == [] and recientes["ultimaObservacion"] is None


def test_desde_posterior_a_hasta_es_400(cliente_api, muestra):
    ventana = muestra["ventana"]
    invertida = {"desde": ventana["hasta"], "hasta": ventana["desde"]}
    respuesta = cliente_api.get(COMPARACION.format(p="PAR-001"), params=invertida)
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"


def test_cu17_ventana_de_tres_horas_es_400(cliente_api, muestra):
    fin = muestra["fin_dt"]
    respuesta = cliente_api.get(EVOLUCION.format(p="PAR-001"), params={
        "desde": _iso(fin - timedelta(hours=3)), "hasta": _iso(fin)})
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"


def test_partido_y_equipo_validados_contra_el_catalogo(cliente_api, muestra):
    respuesta = cliente_api.get(COMPARACION.format(p="PAR-999"), params=muestra["ventana"])
    assert respuesta.json()["error"]["codigo"] == "PARTIDO_NO_ENCONTRADO"
    respuesta = cliente_api.get(RECIENTES.format(p="PAR-001", e="EQ-003"))
    assert respuesta.json()["error"]["codigo"] == "EQUIPO_NO_PARTICIPA"


def test_token_incorrecto_es_500_sin_detalles(cliente_api, settings_reales, muestra, tmp_path):
    archivo = tmp_path / "otro.token"
    archivo.write_text("token-incorrecto", encoding="utf-8")
    incorrecto = AdaptadorInflux(settings_reales.model_copy(update={"influx_token_file": archivo}))
    cliente_api.app.dependency_overrides[obtener_adaptador_influx] = lambda: incorrecto
    try:
        respuesta = cliente_api.get(COMPARACION.format(p="PAR-001"), params=muestra["ventana"])
    finally:
        cliente_api.app.dependency_overrides.pop(obtener_adaptador_influx)
        incorrecto.cerrar()
    assert respuesta.status_code == 500
    error = respuesta.json()["error"]
    assert error["codigo"] == "ERROR_INTERNO" and error["detalles"] == []
    assert "authenticated" not in respuesta.text and "token" not in respuesta.text.lower()


def test_influx_inaccesible_es_503(cliente_api, settings_reales, muestra):
    # Puerto local sin servicio: la conexión se rechaza (o vence el connect) → 503.
    caido = AdaptadorInflux(settings_reales.model_copy(
        update={"influx_url": "http://127.0.0.1:1", "influx_timeout_s": 1.0}))
    cliente_api.app.dependency_overrides[obtener_adaptador_influx] = lambda: caido
    try:
        respuesta = cliente_api.get(COMPARACION.format(p="PAR-001"), params=muestra["ventana"])
    finally:
        cliente_api.app.dependency_overrides.pop(obtener_adaptador_influx)
        caido.cerrar()
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["codigo"] == "DEPENDENCIA_NO_DISPONIBLE"


def test_lectura_lenta_es_504(cliente_api, settings_reales, muestra):
    # Un servidor local acepta la conexión y nunca responde: vence el timeout de lectura.
    servidor = socket.create_server(("127.0.0.1", 0))
    aceptadas: list[socket.socket] = []
    hilo = threading.Thread(target=lambda: aceptadas.append(servidor.accept()[0]), daemon=True)
    hilo.start()
    lento = AdaptadorInflux(settings_reales.model_copy(update={
        "influx_url": f"http://127.0.0.1:{servidor.getsockname()[1]}", "influx_timeout_s": 0.5}))
    cliente_api.app.dependency_overrides[obtener_adaptador_influx] = lambda: lento
    try:
        respuesta = cliente_api.get(EVOLUCION.format(p="PAR-001"), params=muestra["ventana"])
    finally:
        cliente_api.app.dependency_overrides.pop(obtener_adaptador_influx)
        lento.cerrar()
        for conexion in aceptadas:
            conexion.close()
        servidor.close()
    assert respuesta.status_code == 504
    assert respuesta.json()["error"]["codigo"] == "DEPENDENCIA_TIMEOUT"
