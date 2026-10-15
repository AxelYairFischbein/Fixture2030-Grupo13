"""AdaptadorRedis sin Docker: claves, traducción de excepciones y log sin credenciales."""

import logging
from unittest.mock import MagicMock

import pytest
from redis.exceptions import (
    AuthenticationError,
    BusyLoadingError,
    ConnectionError,
    ResponseError,
    TimeoutError,
)

from app.adapters.redis_adaptador import TTL_FICHA_S, TTL_SESION_S, AdaptadorRedis
from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio

SESION = "SES-PRUEBA-3f9a0000000000000000000000000000"


def _adaptador(cliente: MagicMock | None = None, **opciones) -> tuple[AdaptadorRedis, MagicMock]:
    cliente = cliente or MagicMock()
    return AdaptadorRedis(Settings(_env_file=None, **opciones), cliente=cliente), cliente


def test_servidor_inaccesible_es_dependencia_no_disponible():
    # Driver real contra un puerto cerrado: rechazo (ConnectionError) o, en Windows,
    # vencimiento del connect (TimeoutError "Timeout connecting…"). Ambos → 503.
    adaptador = AdaptadorRedis(Settings(_env_file=None, redis_port=1))
    try:
        with pytest.raises(DependenciaNoDisponible) as exc:
            adaptador.leer_ficha_cacheada("EQ-001")
        assert exc.value.dependencia == "redis"
        assert adaptador.ping() is False
    finally:
        adaptador.cerrar()


@pytest.mark.parametrize("excepcion, esperada", [
    (ConnectionError("Error 10061 connecting"), DependenciaNoDisponible),
    (BusyLoadingError("loading"), DependenciaNoDisponible),
    (TimeoutError("Timeout connecting to server"), DependenciaNoDisponible),
    (TimeoutError("Timeout reading from socket"), DependenciaTimeout),
])
def test_traduccion_de_fallas_de_red(excepcion, esperada):
    adaptador, cliente = _adaptador()
    cliente.get.side_effect = excepcion
    with pytest.raises(esperada):
        adaptador.leer_ficha_cacheada("EQ-001")


@pytest.mark.parametrize("excepcion", [
    AuthenticationError("invalid username-password pair"),
    ResponseError("WRONGTYPE Operation against a key holding the wrong kind of value"),
])
def test_configuracion_o_tipo_incorrecto_es_error_interno_sin_filtrar_mensaje(excepcion):
    adaptador, cliente = _adaptador()
    cliente.delete.side_effect = excepcion
    with pytest.raises(ErrorDominio) as exc:
        adaptador.cerrar_sesion(SESION)
    assert type(exc.value) is ErrorDominio
    assert exc.value.codigo == "ERROR_INTERNO"
    assert str(excepcion) not in exc.value.mensaje


def test_claves_con_el_prefijo_configurado():
    adaptador, cliente = _adaptador(redis_prefijo="fixture2030:h10:test:")
    adaptador.cerrar_sesion(SESION)
    cliente.delete.assert_called_once_with(f"fixture2030:h10:test:sesion:{SESION}")
    adaptador.invalidar_ficha_cacheada("EQ-001")
    cliente.delete.assert_called_with("fixture2030:h10:test:cache:equipo:EQ-001")


def test_ficha_se_guarda_como_json_con_ttl_300():
    adaptador, cliente = _adaptador()
    adaptador.guardar_ficha_cacheada("EQ-001", {"equipoId": "EQ-001", "nombre": "Selección"})
    cliente.set.assert_called_once_with(
        "fixture2030:h7:demo:cache:equipo:EQ-001",
        '{"equipoId": "EQ-001", "nombre": "Selección"}', ex=TTL_FICHA_S,
    )


def test_copia_ilegible_es_miss():
    adaptador, cliente = _adaptador()
    cliente.get.return_value = "{no es json"
    assert adaptador.leer_ficha_cacheada("EQ-001") is None


def test_leer_sesion_ausente_devuelve_none():
    adaptador, cliente = _adaptador()
    pipe = cliente.pipeline.return_value.__enter__.return_value
    pipe.execute.return_value = [{}, -2]
    assert adaptador.leer_sesion(SESION) is None


def test_leer_sesion_devuelve_campos_y_ttl():
    adaptador, cliente = _adaptador()
    pipe = cliente.pipeline.return_value.__enter__.return_value
    pipe.execute.return_value = [{"usuario_id": "USR-00001", "estado": "activa", "rol": "lector"}, 99]
    assert adaptador.leer_sesion(SESION) == {
        "usuario_id": "USR-00001", "estado": "activa", "rol": "lector", "ttl": 99,
    }
    cliente.pipeline.assert_called_once_with(transaction=True)


@pytest.mark.parametrize("respuesta, esperado", [
    (0, {"resultado": "no_vigente"}),
    (-1, {"resultado": "rol_no_autorizado"}),
    (["USR-00003", "operador", 1800],
     {"resultado": "ok", "usuario_id": "USR-00003", "rol": "operador", "ttl": 1800}),
])
def test_renovar_interpreta_el_script(respuesta, esperado):
    adaptador, cliente = _adaptador()
    script = cliente.register_script.return_value
    script.return_value = respuesta
    assert adaptador.renovar_sesion(SESION, "operador") == esperado
    script.assert_called_once_with(
        keys=[f"fixture2030:h7:demo:sesion:{SESION}"], args=["operador", TTL_SESION_S]
    )


def test_renovar_sin_rol_envia_argumento_vacio():
    adaptador, cliente = _adaptador()
    script = cliente.register_script.return_value
    script.return_value = 0
    adaptador.renovar_sesion(SESION)
    assert script.call_args.kwargs["args"] == ["", TTL_SESION_S]


def test_el_log_no_registra_el_id_de_sesion(caplog):
    adaptador, cliente = _adaptador()
    cliente.register_script.return_value.side_effect = TimeoutError("timeout")
    with caplog.at_level(logging.INFO, logger="app.adapters.redis"):
        with pytest.raises(DependenciaTimeout):
            adaptador.renovar_sesion(SESION)
    assert "operacion=renovar_sesion resultado=DEPENDENCIA_TIMEOUT" in caplog.text
    assert SESION not in caplog.text
