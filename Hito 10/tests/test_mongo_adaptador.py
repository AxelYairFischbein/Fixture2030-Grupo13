"""AdaptadorMongo sin Docker: traducción de excepciones y conversión de resultados."""

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from pymongo.errors import (
    AutoReconnect,
    ExecutionTimeout,
    NetworkTimeout,
    OperationFailure,
    ServerSelectionTimeoutError,
)

from app.adapters.mongo_adaptador import AdaptadorMongo
from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio


def _adaptador_con(cliente: MagicMock) -> AdaptadorMongo:
    return AdaptadorMongo(Settings(_env_file=None), cliente=cliente)


def _cliente_que_lanza(excepcion: Exception) -> MagicMock:
    cliente = MagicMock()
    cliente.__getitem__.return_value.equipos.find_one.side_effect = excepcion
    return cliente


def test_servidor_inaccesible_es_dependencia_no_disponible():
    # Driver real contra un puerto cerrado: ServerSelectionTimeoutError → 503.
    settings = Settings(_env_file=None, mongo_port=1, mongo_server_selection_timeout_s=0.2)
    adaptador = AdaptadorMongo(settings)
    try:
        with pytest.raises(DependenciaNoDisponible) as exc:
            adaptador.obtener_equipo("EQ-001")
        assert exc.value.dependencia == "mongodb"
        assert adaptador.ping() is False
    finally:
        adaptador.cerrar()


@pytest.mark.parametrize("excepcion, esperada", [
    (ServerSelectionTimeoutError("sin servidor"), DependenciaNoDisponible),
    (AutoReconnect("conexión perdida"), DependenciaNoDisponible),
    (NetworkTimeout("timed out"), DependenciaTimeout),
    (ExecutionTimeout("operation exceeded time limit"), DependenciaTimeout),
])
def test_traduccion_de_fallas_de_red(excepcion, esperada):
    with pytest.raises(esperada):
        _adaptador_con(_cliente_que_lanza(excepcion)).obtener_equipo("EQ-001")


def test_otra_falla_del_driver_es_error_interno_sin_filtrar_mensaje():
    falla = OperationFailure("Authentication failed. usuario=admin", code=18)
    with pytest.raises(ErrorDominio) as exc:
        _adaptador_con(_cliente_que_lanza(falla)).obtener_equipo("EQ-001")
    assert type(exc.value) is ErrorDominio
    assert exc.value.codigo == "ERROR_INTERNO"
    assert "Authentication" not in exc.value.mensaje


def test_proyeccion_explicita_sin_id_y_fecha_iso():
    cliente = MagicMock()
    jugadores = cliente.__getitem__.return_value.jugadores
    jugadores.find_one.return_value = {"jugadorId": "JUG-0001",
                                       "fechaNacimiento": datetime(1998, 3, 12)}
    jugador = _adaptador_con(cliente).obtener_jugador("JUG-0001")
    assert jugador["fechaNacimiento"] == date(1998, 3, 12)
    filtro, proyeccion = jugadores.find_one.call_args.args
    assert filtro == {"jugadorId": "JUG-0001"}
    assert proyeccion["_id"] == 0
    assert not {"origen", "esDatoSintetico", "creadoEn", "actualizadoEn"} & set(proyeccion)
