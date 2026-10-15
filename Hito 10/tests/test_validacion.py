"""El 400 de validación de FastAPI sale con el formato único y código VALIDACION."""


def _error(respuesta) -> dict:
    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["codigo"] == "VALIDACION"
    assert error["requestId"] == respuesta.headers["X-Request-Id"]
    return error


def test_formato_de_identificador_invalido(client):
    error = _error(client.get("/prueba/equipos/EQ-1", params={"limite": 5}))
    assert error["detalles"] == [
        {"campo": "equipoId", "problema": r"no cumple el formato ^EQ-\d{3}$"}
    ]


def test_limite_fuera_de_rango(client):
    error = _error(client.get("/prueba/equipos/EQ-001", params={"limite": 0}))
    assert error["detalles"] == [{"campo": "limite", "problema": "debe ser mayor o igual que 1"}]


def test_parametro_obligatorio_ausente(client):
    error = _error(client.get("/prueba/equipos/EQ-001"))
    assert error["detalles"] == [{"campo": "limite", "problema": "es obligatorio"}]


def test_varios_errores_y_sin_eco_del_valor(client):
    respuesta = client.get("/prueba/equipos/EQ-1", params={"limite": "abc"})
    error = _error(respuesta)
    assert {d["campo"] for d in error["detalles"]} == {"equipoId", "limite"}
    assert "abc" not in respuesta.text


def test_entrada_valida_no_es_error(client):
    respuesta = client.get("/prueba/equipos/EQ-001", params={"limite": 5})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"equipoId": "EQ-001", "limite": 5}
