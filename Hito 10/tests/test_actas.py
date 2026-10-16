"""CU-18 y CU-19 sobre IRIS (falso) con sesiones de Redis (falso)."""

import pytest

from app.errors import DependenciaNoDisponible, DependenciaTimeout

URL_ACTA = "/api/v1/partidos/{}/acta"
URL_TRANSICION = "/api/v1/partidos/{}/acta/transiciones"
OPERADOR = "SES-PRUEBA-operador-0001"
LECTOR = "SES-PRUEBA-lector-0001"


@pytest.fixture
def sesiones(redis_falso):
    redis_falso.crear_sesion(OPERADOR, usuario_id="USR-00003", rol="operador")
    redis_falso.crear_sesion(LECTOR, rol="lector")


def _transicionar(client, partido_id, nuevo, sesion=OPERADOR):
    encabezados = {"X-Session-Id": sesion} if sesion else {}
    return client.post(URL_TRANSICION.format(partido_id), json={"nuevoEstado": nuevo},
                       headers=encabezados)


# CU-18

def test_cu18_acta_de_par001(client):
    respuesta = client.get(URL_ACTA.format("PAR-001"))
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["partidoId"], cuerpo["estadioId"], cuerpo["estado"]) == ("PAR-001", "EST-01", "PENDIENTE")
    assert cuerpo["arbitro"] == {"codigo": "ARB-001", "nombre": "Arbitro Sintetico 01",
                                 "nacionalidad": "F01"}
    assert [(e["tipo"], e["minuto"]) for e in cuerpo["eventos"]] == [("TARJETA", 15), ("CAMBIO", 75)]
    assert cuerpo["eventos"][0]["jugador"] == {"codigo": "JUG-0001", "nombre": "Nombre0001 Apellido0001",
                                               "numero": 1, "posicion": "ARQUERO"}


def test_cu18_no_expone_ids_licencia_ni_clases(client):
    texto = client.get(URL_ACTA.format("PAR-001")).text
    for prohibido in ("Licencia", "licencia", "LIC-", "%ID", "FixtureH9", "FixtureH10", "||"):
        assert prohibido not in texto


def test_cu18_acta_inexistente_es_404(client):
    # PAR-002 existe en el calendario de Neo4j pero no tiene acta en IRIS.
    respuesta = client.get(URL_ACTA.format("PAR-002"))
    assert respuesta.status_code == 404
    error = respuesta.json()["error"]
    assert error["codigo"] == "ACTA_NO_ENCONTRADA"
    assert error["detalles"] == [{"campo": "partidoId", "problema": "PAR-002 no tiene acta"}]


def test_cu18_acta_sin_eventos_es_lista_vacia(client):
    respuesta = client.get(URL_ACTA.format("PAR-900"))
    assert respuesta.status_code == 200
    assert respuesta.json()["eventos"] == []


def test_cu18_formato_invalido_es_400_sin_consultar_iris(client, iris_falso):
    respuesta = client.get(URL_ACTA.format("PAR-1"))
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"
    assert iris_falso.llamadas == []


@pytest.mark.parametrize("falla, http, codigo", [
    (DependenciaNoDisponible("iris"), 503, "DEPENDENCIA_NO_DISPONIBLE"),
    (DependenciaTimeout("iris"), 504, "DEPENDENCIA_TIMEOUT"),
])
def test_cu18_dependencia_caida(client, iris_falso, falla, http, codigo):
    iris_falso.falla = falla
    respuesta = client.get(URL_ACTA.format("PAR-001"))
    assert respuesta.status_code == http
    assert respuesta.json()["error"]["codigo"] == codigo


# CU-19

def test_cu19_recorrido_completo_y_reapertura_rechazada(client, iris_falso, sesiones):
    en_juego = _transicionar(client, "PAR-900", "EN_JUEGO")
    assert en_juego.status_code == 200
    assert en_juego.json() == {"partidoId": "PAR-900", "estadoAnterior": "PENDIENTE",
                               "estadoActual": "EN_JUEGO", "cambio": True}
    finalizado = _transicionar(client, "PAR-900", "FINALIZADO")
    assert finalizado.status_code == 200
    assert finalizado.json()["estadoAnterior"] == "EN_JUEGO"
    assert finalizado.json()["estadoActual"] == "FINALIZADO"

    reabrir = _transicionar(client, "PAR-900", "EN_JUEGO")
    assert reabrir.status_code == 409
    error = reabrir.json()["error"]
    assert error["codigo"] == "TRANSICION_NO_PERMITIDA"
    assert "estado actual FINALIZADO" in error["detalles"][0]["problema"]
    assert client.get(URL_ACTA.format("PAR-900")).json()["estado"] == "FINALIZADO"


def test_cu19_repetir_la_transicion_es_200_sin_cambio(client, iris_falso, sesiones):
    _transicionar(client, "PAR-900", "EN_JUEGO")
    cambios = iris_falso.cambios
    repetida = _transicionar(client, "PAR-900", "EN_JUEGO")
    assert repetida.status_code == 200
    assert repetida.json() == {"partidoId": "PAR-900", "estadoAnterior": "EN_JUEGO",
                               "estadoActual": "EN_JUEGO", "cambio": False}
    assert iris_falso.cambios == cambios  # no se llamó a CambiarEstado


def test_cu19_pendiente_a_finalizado_es_409(client, sesiones):
    respuesta = _transicionar(client, "PAR-900", "FINALIZADO")
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "TRANSICION_NO_PERMITIDA"
    assert client.get(URL_ACTA.format("PAR-900")).json()["estado"] == "PENDIENTE"


def test_cu19_acta_inexistente_es_404(client, sesiones):
    respuesta = _transicionar(client, "PAR-002", "EN_JUEGO")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "ACTA_NO_ENCONTRADA"


@pytest.mark.parametrize("cuerpo", [
    {"nuevoEstado": "PENDIENTE"},
    {"nuevoEstado": "en_juego"},
    {"nuevoEstado": "EN_JUEGO", "estado": "FINALIZADO"},
    {},
])
def test_cu19_cuerpo_invalido_es_400_sin_tocar_redis_ni_iris(client, redis_falso, iris_falso,
                                                              sesiones, cuerpo):
    respuesta = client.post(URL_TRANSICION.format("PAR-900"), json=cuerpo,
                            headers={"X-Session-Id": OPERADOR})
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"
    assert redis_falso.llamadas == []
    assert iris_falso.llamadas == []


def test_cu19_formato_de_partido_invalido_es_400(client, iris_falso, sesiones):
    assert _transicionar(client, "PAR-9999", "EN_JUEGO").status_code == 400
    assert iris_falso.llamadas == []


def test_cu19_sin_sesion_es_401(client, iris_falso):
    respuesta = _transicionar(client, "PAR-900", "EN_JUEGO", sesion=None)
    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "SESION_REQUERIDA"
    assert iris_falso.llamadas == []


def test_cu19_sesion_no_vigente_es_401(client, iris_falso):
    respuesta = _transicionar(client, "PAR-900", "EN_JUEGO", sesion="SES-PRUEBA-inexistente")
    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "SESION_NO_VIGENTE"
    assert iris_falso.llamadas == []


def test_cu19_sin_rol_operador_es_403(client, iris_falso, sesiones):
    respuesta = _transicionar(client, "PAR-900", "EN_JUEGO", sesion=LECTOR)
    assert respuesta.status_code == 403
    assert respuesta.json()["error"]["codigo"] == "ROL_NO_AUTORIZADO"
    assert iris_falso.llamadas == []


def test_cu19_redis_caido_es_503_sin_tocar_iris(client, redis_falso, iris_falso, sesiones):
    redis_falso.falla = DependenciaNoDisponible("redis")
    assert _transicionar(client, "PAR-900", "EN_JUEGO").status_code == 503
    assert iris_falso.llamadas == []


@pytest.mark.parametrize("falla, http", [
    (DependenciaNoDisponible("iris"), 503),
    (DependenciaTimeout("iris"), 504),
])
def test_cu19_iris_caido(client, iris_falso, sesiones, falla, http):
    iris_falso.falla = falla
    assert _transicionar(client, "PAR-900", "EN_JUEGO").status_code == http
