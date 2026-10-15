"""Propagación del encabezado X-Request-Id y log de acceso."""

import logging
import uuid

import pytest


def _es_uuid(valor: str) -> bool:
    try:
        uuid.UUID(valor)
    except ValueError:
        return False
    return True


def test_acepta_el_uuid_del_cliente(client):
    propio = str(uuid.uuid4())
    respuesta = client.get("/api/v1/salud", headers={"X-Request-Id": propio})
    assert respuesta.headers["X-Request-Id"] == propio


def test_genera_uno_si_no_viene(client):
    respuesta = client.get("/api/v1/salud")
    assert _es_uuid(respuesta.headers["X-Request-Id"])


@pytest.mark.parametrize("invalido", ["abc", "1234", "<script>", "x" * 300])
def test_reemplaza_uno_invalido(client, invalido):
    respuesta = client.get("/api/v1/salud", headers={"X-Request-Id": invalido})
    assert respuesta.headers["X-Request-Id"] != invalido
    assert _es_uuid(respuesta.headers["X-Request-Id"])


@pytest.mark.parametrize("ruta", ["/prueba/no-encontrado", "/prueba/inesperado", "/no-existe"])
def test_el_error_lleva_el_mismo_request_id(client, ruta):
    propio = str(uuid.uuid4())
    respuesta = client.get(ruta, headers={"X-Request-Id": propio})
    assert respuesta.headers["X-Request-Id"] == propio
    assert respuesta.json()["error"]["requestId"] == propio


class _Captura(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.registros: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.registros.append(record)


def test_log_de_acceso_con_request_id_y_sin_sesion(client):
    from app.config.logging import FiltroRequestId

    logger = logging.getLogger("app")
    captura = _Captura()
    captura.addFilter(FiltroRequestId())
    logger.addHandler(captura)
    try:
        propio = str(uuid.uuid4())
        client.get(
            "/api/v1/salud",
            headers={"X-Request-Id": propio, "X-Session-Id": "SES-PRUEBA-no-debe-loguearse"},
        )
    finally:
        logger.removeHandler(captura)

    acceso = [r for r in captura.registros if r.name == "app.acceso"]
    assert len(acceso) == 1
    linea = acceso[0].getMessage()
    assert acceso[0].request_id == propio
    assert "metodo=GET" in linea and "ruta=/api/v1/salud" in linea and "estado=200" in linea
    assert "duracion_ms=" in linea
    assert all("SES-PRUEBA" not in r.getMessage() for r in captura.registros)
