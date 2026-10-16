"""Integración con el IRIS del Hito 9 (CU-18, CU-19) y el Redis del Hito 7 (sesión operador).

PAR-001 solo se lee. Las transiciones se prueban sobre partidos temporales que crea y
borra cada prueba (tests/integracion/iris_temporal.py). Requiere el envoltorio
FixtureH10.Servicio cargado (scripts/cargar_servicio_iris.ps1).
"""

import pytest
from fastapi.testclient import TestClient

from app.adapters.iris_adaptador import CLASE_SERVICIO
from app.main import create_app
from tests.integracion import iris_temporal

pytestmark = pytest.mark.integration

URL_ACTA = "/api/v1/partidos/{}/acta"
URL_TRANSICION = "/api/v1/partidos/{}/acta/transiciones"


@pytest.fixture(scope="module")
def iris_directo(settings_reales):
    if "completar_localmente" in (settings_reales.iris_user,
                                  settings_reales.iris_password.get_secret_value()):
        pytest.skip("IRIS_USER / IRIS_PASSWORD de Hito 10/.env tienen el valor de relleno")
    try:
        conexion, nativo = iris_temporal.conectar(settings_reales)
    except Exception:
        pytest.skip("IRIS del Hito 9 no responde o rechaza las credenciales: "
                    'docker compose -f "Hito 9/docker-compose.yml" up -d')
    try:
        nativo.classMethodString(CLASE_SERVICIO, "Version")
    except Exception:
        conexion.close()
        pytest.skip(f"Falta cargar {CLASE_SERVICIO}: .\\scripts\\cargar_servicio_iris.ps1")
    yield nativo
    conexion.close()


@pytest.fixture(scope="module")
def cliente_api(settings_reales, iris_directo, redis_directo):
    with TestClient(create_app(settings_reales)) as cliente:
        yield cliente


@pytest.fixture
def temporal(iris_directo):
    """Fábrica de partidos temporales: se borran al terminar aunque la prueba falle."""
    creados: list[str] = []

    def crear() -> str:
        codigo = iris_temporal.crear(iris_directo)
        creados.append(codigo)
        return codigo

    yield crear
    for codigo in creados:
        iris_temporal.borrar(iris_directo, codigo)


@pytest.fixture
def operador(sesiones):
    sesion_id, _ = sesiones(rol="operador", usuario_id="USR-00003")
    return {"X-Session-Id": sesion_id}


def _transicionar(cliente, partido_id, nuevo, encabezados):
    return cliente.post(URL_TRANSICION.format(partido_id), json={"nuevoEstado": nuevo},
                        headers=encabezados)


def test_salud_informa_iris_disponible(cliente_api):
    assert cliente_api.get("/api/v1/salud").json()["dependencias"]["iris"] == "disponible"


def test_cu18_acta_de_par001_coincide_con_la_demo_del_hito9(cliente_api):
    respuesta = cliente_api.get(URL_ACTA.format("PAR-001"))
    assert respuesta.status_code == 200
    acta = respuesta.json()
    assert (acta["partidoId"], acta["estadioId"], acta["estado"]) == ("PAR-001", "EST-01", "PENDIENTE")
    assert acta["arbitro"]["codigo"] == "ARB-001"
    assert set(acta["arbitro"]) == {"codigo", "nombre", "nacionalidad"}
    assert [(e["tipo"], e["minuto"]) for e in acta["eventos"]] == [("TARJETA", 15), ("CAMBIO", 75)]
    assert all(e["jugador"]["codigo"] == "JUG-0001" for e in acta["eventos"])
    for prohibido in ("LIC-DEMO", "Licencia", "FixtureH9", "||"):
        assert prohibido not in respuesta.text


def test_cu18_partido_del_calendario_sin_acta_es_404(cliente_api):
    respuesta = cliente_api.get(URL_ACTA.format("PAR-002"))
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "ACTA_NO_ENCONTRADA"


def test_cu18_acta_temporal_sin_eventos(cliente_api, temporal):
    codigo = temporal()
    acta = cliente_api.get(URL_ACTA.format(codigo)).json()
    assert (acta["estado"], acta["eventos"]) == ("PENDIENTE", [])


def test_cu19_lista_de_control_sobre_partido_temporal(cliente_api, temporal, operador):
    codigo = temporal()
    en_juego = _transicionar(cliente_api, codigo, "EN_JUEGO", operador)
    assert en_juego.status_code == 200
    assert en_juego.json() == {"partidoId": codigo, "estadoAnterior": "PENDIENTE",
                               "estadoActual": "EN_JUEGO", "cambio": True}

    repetida = _transicionar(cliente_api, codigo, "EN_JUEGO", operador)
    assert repetida.status_code == 200
    assert repetida.json()["cambio"] is False
    assert repetida.json()["estadoActual"] == "EN_JUEGO"

    finalizado = _transicionar(cliente_api, codigo, "FINALIZADO", operador)
    assert finalizado.status_code == 200
    assert (finalizado.json()["estadoAnterior"], finalizado.json()["estadoActual"]) == ("EN_JUEGO", "FINALIZADO")

    reabrir = _transicionar(cliente_api, codigo, "EN_JUEGO", operador)
    assert reabrir.status_code == 409
    assert reabrir.json()["error"]["codigo"] == "TRANSICION_NO_PERMITIDA"
    assert "estado actual FINALIZADO" in reabrir.json()["error"]["detalles"][0]["problema"]
    assert cliente_api.get(URL_ACTA.format(codigo)).json()["estado"] == "FINALIZADO"

    repetida_final = _transicionar(cliente_api, codigo, "FINALIZADO", operador)
    assert repetida_final.status_code == 200
    assert repetida_final.json()["cambio"] is False


def test_cu19_pendiente_a_finalizado_es_409_y_no_cambia(cliente_api, temporal, operador):
    codigo = temporal()
    respuesta = _transicionar(cliente_api, codigo, "FINALIZADO", operador)
    assert respuesta.status_code == 409
    assert cliente_api.get(URL_ACTA.format(codigo)).json()["estado"] == "PENDIENTE"


def test_cu19_acta_inexistente_es_404(cliente_api, operador):
    respuesta = _transicionar(cliente_api, "PAR-002", "EN_JUEGO", operador)
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "ACTA_NO_ENCONTRADA"


def test_cu19_rol_lector_es_403_y_no_cambia(cliente_api, temporal, sesiones):
    codigo = temporal()
    sesion_id, _ = sesiones(rol="lector")
    respuesta = _transicionar(cliente_api, codigo, "EN_JUEGO", {"X-Session-Id": sesion_id})
    assert respuesta.status_code == 403
    assert cliente_api.get(URL_ACTA.format(codigo)).json()["estado"] == "PENDIENTE"


def test_cu19_pendiente_como_destino_es_400(cliente_api, temporal, operador):
    codigo = temporal()
    assert _transicionar(cliente_api, codigo, "PENDIENTE", operador).status_code == 400


def test_par001_sigue_pendiente(cliente_api):
    # Ninguna prueba de transición toca la muestra del Hito 9.
    assert cliente_api.get(URL_ACTA.format("PAR-001")).json()["estado"] == "PENDIENTE"
