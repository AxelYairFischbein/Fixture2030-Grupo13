"""AdaptadorIris con una conexión falsa: SQL parametrizado, conversión y traducción de errores."""

import logging

import iris.dbapi
import pytest

from app.adapters.iris_adaptador import (
    CLASE_SERVICIO,
    SEL_EVENTOS,
    SEL_PARTIDO,
    AdaptadorIris,
    clasificar,
    interpretar_transicion,
)
from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio

FILA_PARTIDO = ("EST-01", "PENDIENTE", "ARB-001", "Arbitro Sintetico 01", "F01")
FILAS_EVENTOS = [
    ("TARJETA", 15, "JUG-0001", "Nombre0001 Apellido0001", 1, "ARQUERO"),
    ("CAMBIO", 75, "JUG-0001", "Nombre0001 Apellido0001", 1, "ARQUERO"),
]


class CursorFalso:
    def __init__(self, conexion) -> None:
        self._conexion = conexion
        self._filas: list[tuple] = []

    def setQueryTimeout(self, segundos) -> None:
        self._conexion.timeouts.append(segundos)

    def execute(self, sql, parametros) -> None:
        self._conexion.consultas.append((sql, list(parametros)))
        if self._conexion.falla is not None:
            raise self._conexion.falla
        self._filas = self._conexion.respuestas.get(sql, [])

    def fetchall(self):
        return list(self._filas)

    def close(self) -> None:
        pass


class ConexionFalsa:
    def __init__(self) -> None:
        self.respuestas = {SEL_PARTIDO: [FILA_PARTIDO], SEL_EVENTOS: FILAS_EVENTOS, "SELECT 1": [(1,)]}
        self.consultas: list[tuple] = []
        self.timeouts: list[int] = []
        self.falla: Exception | None = None
        self.cerrada = False

    def cursor(self):
        return CursorFalso(self)

    def close(self) -> None:
        self.cerrada = True


class NativoFalso:
    def __init__(self) -> None:
        self.respuesta = "OK|PENDIENTE|EN_JUEGO"
        self.falla: Exception | None = None
        self.llamadas: list[tuple] = []

    def classMethodString(self, clase, metodo, *argumentos):
        self.llamadas.append((clase, metodo, *argumentos))
        if self.falla is not None:
            raise self.falla
        return self.respuesta


@pytest.fixture
def piezas():
    return {"conexiones": [], "nativo": NativoFalso(), "falla_al_conectar": None}


@pytest.fixture
def adaptador(piezas):
    def conectar():
        if piezas["falla_al_conectar"] is not None:
            raise piezas["falla_al_conectar"]
        conexion = ConexionFalsa()
        piezas["conexiones"].append(conexion)
        return conexion, piezas["nativo"]

    return AdaptadorIris(Settings(_env_file=None), conectar=conectar)


def test_leer_acta_con_parametros_y_sin_ids(adaptador, piezas):
    acta = adaptador.leer_acta("PAR-001")
    assert acta["estado"] == "PENDIENTE" and acta["estadioId"] == "EST-01"
    assert acta["arbitro"] == {"codigo": "ARB-001", "nombre": "Arbitro Sintetico 01", "nacionalidad": "F01"}
    assert [(e["tipo"], e["minuto"]) for e in acta["eventos"]] == [("TARJETA", 15), ("CAMBIO", 75)]
    conexion = piezas["conexiones"][0]
    # El código viaja como parámetro, nunca dentro del SQL.
    assert conexion.consultas == [(SEL_PARTIDO, ["PAR-001"]), (SEL_EVENTOS, ["PAR-001"])]
    assert all("PAR-001" not in sql for sql, _ in conexion.consultas)
    assert conexion.timeouts == [3, 3]


def test_sql_no_proyecta_id_ni_licencia():
    for sql in (SEL_PARTIDO, SEL_EVENTOS):
        proyeccion = sql.upper().split("FROM")[0]
        assert "LICENCIA" not in proyeccion
        assert "%ID" not in proyeccion and ".ID," not in proyeccion
        assert "UPDATE" not in sql.upper()


def test_leer_acta_inexistente_devuelve_none(adaptador, piezas):
    adaptador.leer_acta("PAR-001")
    piezas["conexiones"][0].respuestas[SEL_PARTIDO] = []
    assert adaptador.leer_acta("PAR-002") is None


def test_la_conexion_se_reutiliza(adaptador, piezas):
    adaptador.leer_acta("PAR-001")
    adaptador.leer_acta("PAR-001")
    assert len(piezas["conexiones"]) == 1


def test_transicionar_invoca_el_envoltorio(adaptador, piezas):
    assert adaptador.transicionar("PAR-901", "EN_JUEGO") == {
        "resultado": "OK", "anterior": "PENDIENTE", "actual": "EN_JUEGO"}
    assert piezas["nativo"].llamadas == [(CLASE_SERVICIO, "Transicionar", "PAR-901", "EN_JUEGO", 2)]


@pytest.mark.parametrize("respuesta, esperado", [
    ("SIN_CAMBIO|EN_JUEGO|EN_JUEGO", {"resultado": "SIN_CAMBIO", "anterior": "EN_JUEGO", "actual": "EN_JUEGO"}),
    ("NO_ENCONTRADO||", {"resultado": "NO_ENCONTRADO", "anterior": None, "actual": None}),
    ("TRANSICION_NO_PERMITIDA|FINALIZADO|FINALIZADO",
     {"resultado": "TRANSICION_NO_PERMITIDA", "anterior": "FINALIZADO", "actual": "FINALIZADO"}),
])
def test_interpretar_transicion(respuesta, esperado):
    assert interpretar_transicion(respuesta) == esperado


def test_bloqueado_es_timeout():
    with pytest.raises(DependenciaTimeout):
        interpretar_transicion("BLOQUEADO||")


@pytest.mark.parametrize("respuesta", ["ERROR||", "", "OK", "DESCONOCIDO|a|b"])
def test_respuesta_de_error_o_desconocida_es_500(respuesta):
    with pytest.raises(ErrorDominio) as exc:
        interpretar_transicion(respuesta)
    assert exc.value.codigo == "ERROR_INTERNO"


@pytest.mark.parametrize("mensaje, tipo", [
    ("<COMMUNICATION LINK ERROR> Failed to connect to server; Details: Error code: 10061", "no_disponible"),
    ("<COMMUNICATION LINK ERROR> Failed to connect to server; Details: Access Denied", "no_disponible"),
    ("<COMMUNICATION LINK ERROR> Connection reset", "no_disponible"),
    ("Query timed out", "timeout"),
    ("<CLASS DOES NOT EXIST> *FixtureH10.Servicio", "envoltorio_ausente"),
    ("[SQLCODE: <-30>:<Table or view not found>]", "interno"),
])
def test_clasificar_mensajes_del_sdk(mensaje, tipo):
    assert clasificar(iris.dbapi.OperationalError(mensaje)) == tipo


def test_clasificar_timeouterror_antes_que_oserror():
    assert clasificar(TimeoutError()) == "timeout"
    assert clasificar(ConnectionRefusedError()) == "no_disponible"


def test_falla_al_conectar_es_503_y_reintenta(adaptador, piezas):
    piezas["falla_al_conectar"] = iris.dbapi.OperationalError(
        "<COMMUNICATION LINK ERROR> Failed to connect to server; Details: Access Denied")
    with pytest.raises(DependenciaNoDisponible):
        adaptador.leer_acta("PAR-001")
    piezas["falla_al_conectar"] = None
    assert adaptador.leer_acta("PAR-001") is not None


def test_enlace_caido_descarta_la_conexion(adaptador, piezas):
    adaptador.leer_acta("PAR-001")
    piezas["conexiones"][0].falla = iris.dbapi.OperationalError("<COMMUNICATION LINK ERROR> reset")
    with pytest.raises(DependenciaNoDisponible):
        adaptador.leer_acta("PAR-001")
    assert piezas["conexiones"][0].cerrada
    adaptador.leer_acta("PAR-001")
    assert len(piezas["conexiones"]) == 2


def test_timeout_de_consulta_es_504(adaptador, piezas):
    adaptador.leer_acta("PAR-001")
    piezas["conexiones"][0].falla = iris.dbapi.OperationalError("Query timed out")
    with pytest.raises(DependenciaTimeout):
        adaptador.leer_acta("PAR-001")


def test_envoltorio_ausente_es_500_y_lo_explica_en_el_log(adaptador, piezas, caplog):
    piezas["nativo"].falla = RuntimeError("<CLASS DOES NOT EXIST> *FixtureH10.Servicio")
    with caplog.at_level(logging.INFO, logger="app.adapters.iris"), pytest.raises(ErrorDominio) as exc:
        adaptador.transicionar("PAR-901", "EN_JUEGO")
    assert exc.value.codigo == "ERROR_INTERNO"
    assert "falta cargar FixtureH10.Servicio" in caplog.text


def test_error_sql_es_500_sin_sql_en_el_log(adaptador, piezas, caplog):
    adaptador.leer_acta("PAR-001")
    piezas["conexiones"][0].falla = iris.dbapi.ProgrammingError("[SQLCODE: <-30>] detalle")
    with caplog.at_level(logging.INFO, logger="app.adapters.iris"), pytest.raises(ErrorDominio):
        adaptador.leer_acta("PAR-001")
    assert "SELECT" not in caplog.text and "PAR-001" not in caplog.text
    assert "detalle" not in caplog.text


def test_ping(adaptador, piezas):
    assert adaptador.ping() is True
    piezas["falla_al_conectar"] = iris.dbapi.OperationalError("<COMMUNICATION LINK ERROR> Failed to connect")
    adaptador.cerrar()
    assert adaptador.ping() is False
