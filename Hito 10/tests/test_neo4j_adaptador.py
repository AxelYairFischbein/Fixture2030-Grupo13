"""AdaptadorNeo4j sin Docker: traducción de excepciones, consultas fijas y conversión de fechas."""

import re
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from neo4j.time import DateTime

from app.adapters import neo4j_adaptador
from app.adapters.neo4j_adaptador import AdaptadorNeo4j
from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio

CONSULTAS = (
    neo4j_adaptador.AGENDA_EQUIPO, neo4j_adaptador.EVENTOS_PARTIDO,
    neo4j_adaptador.PARTIDOS_POR_FECHA, neo4j_adaptador.CATALOGO_PARTIDOS,
)


def _error_neo4j(codigo: str) -> Neo4jError:
    return Neo4jError._hydrate_neo4j(code=codigo, message="detalle del servidor")


def _driver(filas: list[dict] | None = None, falla: Exception | None = None) -> MagicMock:
    driver = MagicMock()
    sesion = driver.session.return_value.__enter__.return_value
    if falla is not None:
        sesion.run.side_effect = falla
    else:
        registros = []
        for fila in filas or []:
            registro = MagicMock()
            registro.data.return_value = fila
            registros.append(registro)
        sesion.run.return_value = registros
    return driver


def _adaptador(driver: MagicMock) -> AdaptadorNeo4j:
    return AdaptadorNeo4j(Settings(_env_file=None), driver=driver)


def _sesion(driver: MagicMock) -> MagicMock:
    return driver.session.return_value.__enter__.return_value


def test_servidor_inaccesible_es_dependencia_no_disponible():
    # Driver real contra un puerto cerrado: ServiceUnavailable → 503.
    settings = Settings(_env_file=None, neo4j_uri="bolt://127.0.0.1:1",
                        neo4j_connection_timeout_s=0.5)
    adaptador = AdaptadorNeo4j(settings)
    try:
        with pytest.raises(DependenciaNoDisponible) as exc:
            adaptador.agenda_equipo("EQ-001", 20)
        assert exc.value.dependencia == "neo4j"
        assert adaptador.ping() is False
    finally:
        adaptador.cerrar()


@pytest.mark.parametrize("excepcion, esperada", [
    (ServiceUnavailable("sin servidor"), DependenciaNoDisponible),
    (SessionExpired("sesión vencida"), DependenciaNoDisponible),
    (_error_neo4j("Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration"),
     DependenciaTimeout),
    (_error_neo4j("Neo.TransientError.Transaction.TransactionTimedOut"), DependenciaTimeout),
])
def test_traduccion_de_fallas_de_red_y_timeout(excepcion, esperada):
    with pytest.raises(esperada):
        _adaptador(_driver(falla=excepcion)).eventos_partido("PAR-001", 50)


@pytest.mark.parametrize("codigo", [
    "Neo.ClientError.Security.Unauthorized",
    "Neo.ClientError.Statement.SyntaxError",
])
def test_otra_falla_del_driver_es_error_interno_sin_filtrar_mensaje(codigo):
    with pytest.raises(ErrorDominio) as exc:
        _adaptador(_driver(falla=_error_neo4j(codigo))).agenda_equipo("EQ-001", 20)
    assert type(exc.value) is ErrorDominio
    assert exc.value.codigo == "ERROR_INTERNO"
    assert "servidor" not in exc.value.mensaje


def test_consultas_parametrizadas_con_limite_y_sin_estado():
    for cypher in CONSULTAS:
        assert "LIMIT $limite" in cypher
        assert not re.search(r"\bp\.estado\b|\bestado\s*:", cypher)
        assert "elementId" not in cypher and "id(" not in cypher


def test_tx_timeout_de_la_seccion_6_3_y_lectura_en_la_base_configurada():
    driver = _driver([{"equipoId": "EQ-001", "partidos": []}])
    _adaptador(driver).agenda_equipo("EQ-001", 20)
    consulta, parametros = _sesion(driver).run.call_args.args
    assert consulta.timeout == 3.0
    assert parametros == {"equipoId": "EQ-001", "limite": 20}
    assert driver.session.call_args.kwargs["database"] == "neo4j"


def test_agenda_sin_filas_es_equipo_inexistente():
    assert _adaptador(_driver([])).agenda_equipo("EQ-999", 20) is None


def test_agenda_con_lista_vacia_es_vacio_valido():
    assert _adaptador(_driver([{"equipoId": "EQ-005", "partidos": []}])).agenda_equipo(
        "EQ-005", 20) == []


def test_eventos_sin_filas_es_partido_inexistente():
    assert _adaptador(_driver([])).eventos_partido("PAR-999", 50) is None


def test_datetime_de_neo4j_se_convierte_a_utc():
    inicio = DateTime(2030, 6, 10, 15, 0, 0, tzinfo=timezone(timedelta(hours=-3)))
    fila = {"partidoId": "PAR-001", "inicio": inicio, "grupo": "G01", "fase": "GRUPOS_MUESTRA",
            "estadio": {"estadioId": "EST-01", "nombre": "E", "ciudad": "C"}}
    driver = _driver([fila])
    desde, hasta = datetime(2030, 6, 10, tzinfo=UTC), datetime(2030, 6, 11, tzinfo=UTC)
    partidos = _adaptador(driver).partidos_por_fecha(desde, hasta, None, 64)
    assert partidos[0]["inicio"] == datetime(2030, 6, 10, 18, tzinfo=UTC)
    assert partidos[0]["inicio"].tzinfo == UTC
    _, parametros = _sesion(driver).run.call_args.args
    assert parametros == {"desde": desde, "hasta": hasta, "estadioId": None, "limite": 64}


def test_catalogo_como_diccionario_de_tuplas():
    driver = _driver([{"partidoId": "PAR-001", "equipos": ["EQ-001", "EQ-002"]}])
    assert _adaptador(driver).cargar_catalogo_partidos() == {"PAR-001": ("EQ-001", "EQ-002")}
