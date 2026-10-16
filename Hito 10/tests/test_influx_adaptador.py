"""AdaptadorInflux sin Docker: cuerpo de la consulta, parámetros y traducción de errores.

Un httpx.MockTransport hace de InfluxDB: registra cada request y responde lo que la prueba
indique (filas JSON, un código HTTP o una excepción de httpx).
"""

import json
import logging
from datetime import UTC, datetime

import httpx
import pytest

from app.adapters.influx_adaptador import AdaptadorInflux
from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio

TOKEN = "token-secreto-de-la-prueba"
DESDE = datetime(2026, 10, 16, 0, 12, tzinfo=UTC)
HASTA = datetime(2026, 10, 16, 0, 17, tzinfo=UTC)


class InfluxSimulado:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.respuesta: httpx.Response | Exception = httpx.Response(200, json=[])

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta

    def cuerpo(self) -> dict:
        return json.loads(self.requests[-1].content)


@pytest.fixture
def simulado() -> InfluxSimulado:
    return InfluxSimulado()


@pytest.fixture
def adaptador(simulado, tmp_path) -> AdaptadorInflux:
    archivo = tmp_path / "admin.token"
    archivo.write_text(TOKEN + "\n", encoding="utf-8")
    settings = Settings(_env_file=None, influx_token_file=archivo)
    adaptador = AdaptadorInflux(settings)
    # Mismo cliente que crearía el adaptador, con el transporte simulado.
    adaptador._cliente = httpx.Client(
        base_url=settings.influx_url, headers=adaptador._cliente.headers,
        transport=httpx.MockTransport(simulado))
    return adaptador


def test_recientes_envia_los_valores_del_usuario_como_parametros(adaptador, simulado):
    simulado.respuesta = httpx.Response(200, json=[
        {"time": "2026-10-16T00:16:59", "estadio_id": "EST-01", "posesion_pct": 46.5,
         "pases_acumulados": 7849, "tiros_intervalo": 0}])
    filas = adaptador.ultimas_observaciones("PAR-001", "EQ-001", DESDE, HASTA, 5)

    request = simulado.requests[-1]
    assert request.method == "POST" and request.url.path == "/api/v3/query_sql"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    cuerpo = simulado.cuerpo()
    assert cuerpo["db"] == "fixture2030_h8" and cuerpo["format"] == "json"
    assert cuerpo["params"] == {"partido": "PAR-001", "equipo": "EQ-001",
                                "desde": "2026-10-16T00:12:00.000000Z",
                                "hasta": "2026-10-16T00:17:00.000000Z", "limite": 5}
    for valor in ("PAR-001", "EQ-001", "2026-10-16"):
        assert valor not in cuerpo["q"]
    assert "$partido" in cuerpo["q"] and "LIMIT $limite" in cuerpo["q"]
    assert filas[0]["time"] == datetime(2026, 10, 16, 0, 16, 59, tzinfo=UTC)


def test_comparar_incluye_la_muestra_previa_y_usa_el_paso(adaptador, simulado):
    adaptador.comparar("PAR-001", DESDE, HASTA)
    cuerpo = simulado.cuerpo()
    assert cuerpo["params"] == {"partido": "PAR-001", "previo": "2026-10-16T00:11:59.000000Z",
                                "desde": "2026-10-16T00:12:00.000000Z",
                                "hasta": "2026-10-16T00:17:00.000000Z"}
    sql = cuerpo["q"]
    assert "LAG(pases_acumulados)" in sql and "time >= $previo" in sql
    assert "INTERVAL '1 seconds'" in sql and "GROUP BY equipo_id" in sql
    assert "PAR-001" not in sql


@pytest.mark.parametrize("resolucion,intervalo", [("1m", "1 minute"), ("5m", "5 minutes")])
def test_evolucion_usa_date_bin_y_filtro_de_equipo_opcional(adaptador, simulado, resolucion,
                                                             intervalo):
    simulado.respuesta = httpx.Response(200, json=[
        {"inicio": "2026-10-16T00:12:00", "equipo_id": "EQ-001", "muestras": 60}])
    filas = adaptador.evolucion("PAR-001", None, DESDE, HASTA, resolucion)
    assert f"DATE_BIN(INTERVAL '{intervalo}'" in simulado.cuerpo()["q"]
    assert "$equipo" not in simulado.cuerpo()["q"]
    assert filas[0]["inicio"] == datetime(2026, 10, 16, 0, 12, tzinfo=UTC)

    adaptador.evolucion("PAR-001", "EQ-002", DESDE, HASTA, resolucion)
    assert "equipo_id = $equipo" in simulado.cuerpo()["q"]
    assert simulado.cuerpo()["params"]["equipo"] == "EQ-002"
    assert "EQ-002" not in simulado.cuerpo()["q"]


@pytest.mark.parametrize("respuesta,excepcion", [
    (httpx.ConnectError("rechazada"), DependenciaNoDisponible),
    (httpx.ConnectTimeout("sin conexión"), DependenciaNoDisponible),
    (httpx.RemoteProtocolError("cortada"), DependenciaNoDisponible),
    (httpx.ReadTimeout("lenta"), DependenciaTimeout),
    (httpx.Response(503, text="no disponible"), DependenciaNoDisponible),
    (httpx.Response(500, text="falla"), DependenciaNoDisponible),
])
def test_traduce_fallas_de_conexion_y_5xx(adaptador, simulado, respuesta, excepcion):
    simulado.respuesta = respuesta
    with pytest.raises(excepcion):
        adaptador.comparar("PAR-001", DESDE, HASTA)


@pytest.mark.parametrize("estado", [401, 403])
def test_credencial_rechazada_es_error_interno_sin_detalles(adaptador, simulado, caplog, estado):
    simulado.respuesta = httpx.Response(estado, json={"error": "the request was not authenticated"})
    with caplog.at_level(logging.INFO, logger="app.adapters.influx"):
        with pytest.raises(ErrorDominio) as exc:
            adaptador.comparar("PAR-001", DESDE, HASTA)
    assert type(exc.value) is ErrorDominio
    assert exc.value.http_status == 500 and exc.value.codigo == "ERROR_INTERNO"
    assert exc.value.__cause__ is None  # nada del request ni del token encadenado
    assert f"http={estado} motivo=credencial_rechazada" in caplog.text
    assert TOKEN not in caplog.text and "authenticated" not in caplog.text


@pytest.mark.parametrize("respuesta", [
    httpx.Response(400, text="error de SQL"),
    httpx.Response(404, text="database not found"),
    httpx.Response(200, text="no es json"),
    httpx.Response(200, json={"no": "es una lista"}),
])
def test_respuesta_inesperada_es_error_interno(adaptador, simulado, respuesta):
    simulado.respuesta = respuesta
    with pytest.raises(ErrorDominio) as exc:
        adaptador.comparar("PAR-001", DESDE, HASTA)
    assert type(exc.value) is ErrorDominio


def test_el_log_no_registra_token_ni_sql(adaptador, simulado, caplog):
    with caplog.at_level(logging.INFO, logger="app.adapters.influx"):
        adaptador.comparar("PAR-001", DESDE, HASTA)
    assert "dependencia=influxdb operacion=comparar resultado=ok" in caplog.text
    assert TOKEN not in caplog.text and "SELECT" not in caplog.text and "PAR-001" not in caplog.text


def test_ping(adaptador, simulado):
    simulado.respuesta = httpx.Response(200, text="OK")
    assert adaptador.ping() is True
    assert simulado.requests[-1].url.path == "/health"
    simulado.respuesta = httpx.ConnectError("rechazada")
    assert adaptador.ping() is False
    simulado.respuesta = httpx.Response(401)
    assert adaptador.ping() is False


@pytest.mark.parametrize("contenido", [None, "", "   \n"])
def test_token_ausente_o_vacio_impide_crear_el_adaptador(tmp_path, contenido):
    archivo = tmp_path / "admin.token"
    if contenido is not None:
        archivo.write_text(contenido, encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        AdaptadorInflux(Settings(_env_file=None, influx_token_file=archivo))
    assert "INFLUX_TOKEN_FILE" in str(exc.value)
    assert str(tmp_path) not in str(exc.value)
