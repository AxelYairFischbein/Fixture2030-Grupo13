"""Formato de error único (§6.1) y códigos HTTP (§6.2)."""

import pytest


def _assert_formato(respuesta, http_status: int, codigo: str) -> dict:
    assert respuesta.status_code == http_status
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"error"}
    error = cuerpo["error"]
    assert set(error) == {"codigo", "mensaje", "requestId", "detalles"}
    assert error["codigo"] == codigo
    assert error["mensaje"]
    assert isinstance(error["detalles"], list)
    assert error["requestId"] == respuesta.headers["X-Request-Id"]
    return error


def test_no_encontrado_de_dominio_con_detalles(client):
    error = _assert_formato(client.get("/prueba/no-encontrado"), 404, "PARTIDO_NO_ENCONTRADO")
    assert error["detalles"] == [{"campo": "partidoId", "problema": "PAR-999 no existe"}]


@pytest.mark.parametrize(
    ("ruta", "http_status", "codigo"),
    [
        ("/prueba/conflicto", 409, "TRANSICION_NO_PERMITIDA"),
        ("/prueba/caida", 503, "DEPENDENCIA_NO_DISPONIBLE"),
        ("/prueba/timeout", 504, "DEPENDENCIA_TIMEOUT"),
    ],
)
def test_excepciones_de_dominio_a_http(client, ruta, http_status, codigo):
    _assert_formato(client.get(ruta), http_status, codigo)


def test_error_inesperado_es_500_sin_filtrar_detalles(client):
    respuesta = client.get("/prueba/inesperado")
    error = _assert_formato(respuesta, 500, "ERROR_INTERNO")
    assert "secreto" not in respuesta.text
    assert "mongodb://" not in respuesta.text
    assert error["detalles"] == []


def test_ruta_inexistente(client):
    _assert_formato(client.get("/api/v1/no-existe"), 404, "RUTA_NO_ENCONTRADA")


def test_metodo_no_permitido(client):
    respuesta = client.delete("/api/v1/salud")
    _assert_formato(respuesta, 405, "METODO_NO_PERMITIDO")
    assert "GET" in respuesta.headers["Allow"]
