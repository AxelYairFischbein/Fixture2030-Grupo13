"""CU-11, CU-12, CU-13 y CU-14 con el adaptador Redis falso, y la dependencia sesion_requerida."""

from typing import Annotated

import pytest
from fastapi import Depends, Path
from fastapi.testclient import TestClient

from app.errors import DependenciaNoDisponible, DependenciaTimeout
from app.services.sesiones import Autorizacion, sesion_requerida

SESION = "SES-PRUEBA-0001"
URL = "/api/v1/sesiones/actual"


def _error(respuesta, http_status: int, codigo: str) -> dict:
    assert respuesta.status_code == http_status
    error = respuesta.json()["error"]
    assert error["codigo"] == codigo
    assert error["requestId"] == respuesta.headers["X-Request-Id"]
    return error


def _con_sesion(sesion_id: str = SESION) -> dict:
    return {"X-Session-Id": sesion_id}


# CU-11 · consultar la sesión vigente

def test_cu11_sesion_vigente_sin_renovar(client, redis_falso):
    redis_falso.crear_sesion(SESION, usuario_id="USR-00007", rol="moderador", ttl=1200)
    respuesta = client.get(URL, headers=_con_sesion())
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "usuarioId": "USR-00007", "rol": "moderador", "estado": "activa", "expiraEnSegundos": 1200,
    }
    # Una inspección no es actividad: no cambia el TTL ni ultima_actividad.
    assert redis_falso.sesiones[SESION]["ttl"] == 1200
    assert redis_falso.llamadas == ["leer_sesion"]


def test_cu11_respuesta_sin_id_ni_ultima_actividad(client, redis_falso):
    redis_falso.crear_sesion(SESION)
    cuerpo = client.get(URL, headers=_con_sesion()).json()
    assert "ultima_actividad" not in cuerpo and "ultimaActividad" not in cuerpo
    assert SESION not in str(cuerpo)


@pytest.mark.parametrize("preparar", [
    pytest.param(lambda r: None, id="ausente"),
    pytest.param(lambda r: r.crear_sesion(SESION, ttl=-1), id="sin-vencimiento"),
    pytest.param(lambda r: r.crear_sesion(SESION, ttl=-2), id="vencida"),
    pytest.param(lambda r: r.crear_sesion(SESION, estado="cerrada"), id="estado-no-activa"),
])
def test_cu11_sesion_no_vigente(client, redis_falso, preparar):
    preparar(redis_falso)
    _error(client.get(URL, headers=_con_sesion()), 401, "SESION_NO_VIGENTE")


def test_cu11_sin_encabezado_no_consulta_redis(client, redis_falso):
    _error(client.get(URL), 401, "SESION_REQUERIDA")
    assert redis_falso.llamadas == []


@pytest.mark.parametrize("sesion_id", ["corta", "SES_CON_GUION_BAJO", "x" * 65, "SES PRUEBA 01"])
def test_cu11_formato_invalido_es_400_sin_consultar_redis(client, redis_falso, sesion_id):
    error = _error(client.get(URL, headers=_con_sesion(sesion_id)), 400, "VALIDACION")
    assert error["detalles"][0]["campo"] == "X-Session-Id"
    assert sesion_id not in str(error)
    assert redis_falso.llamadas == []


@pytest.mark.parametrize("falla, http_status, codigo", [
    (DependenciaNoDisponible("redis"), 503, "DEPENDENCIA_NO_DISPONIBLE"),
    (DependenciaTimeout("redis"), 504, "DEPENDENCIA_TIMEOUT"),
])
def test_cu11_redis_caido_no_es_401(client, redis_falso, falla, http_status, codigo):
    redis_falso.crear_sesion(SESION)
    redis_falso.falla = falla
    _error(client.get(URL, headers=_con_sesion()), http_status, codigo)


# CU-12 · registrar actividad

def test_cu12_renueva_ttl_y_ultima_actividad(client, redis_falso):
    redis_falso.crear_sesion(SESION, ttl=40)
    respuesta = client.post(f"{URL}/actividad", headers=_con_sesion())
    assert respuesta.status_code == 200
    assert respuesta.json() == {"expiraEnSegundos": 1800}
    assert redis_falso.sesiones[SESION]["ttl"] == 1800
    assert redis_falso.sesiones[SESION]["ultima_actividad"] == "1900000001"


def test_cu12_sesion_ausente_no_se_recrea(client, redis_falso):
    _error(client.post(f"{URL}/actividad", headers=_con_sesion()), 401, "SESION_NO_VIGENTE")
    assert SESION not in redis_falso.sesiones


def test_cu12_timeout_no_informa_ttl(client, redis_falso):
    redis_falso.crear_sesion(SESION)
    redis_falso.falla = DependenciaTimeout("redis")
    respuesta = client.post(f"{URL}/actividad", headers=_con_sesion())
    _error(respuesta, 504, "DEPENDENCIA_TIMEOUT")
    assert "expiraEnSegundos" not in respuesta.text


def test_cu12_sin_encabezado(client):
    _error(client.post(f"{URL}/actividad"), 401, "SESION_REQUERIDA")


# CU-13 · cerrar la sesión

def test_cu13_cierre_y_cierre_repetido_son_204(client, redis_falso):
    redis_falso.crear_sesion(SESION)
    primera = client.delete(URL, headers=_con_sesion())
    assert primera.status_code == 204 and primera.content == b""
    assert client.delete(URL, headers=_con_sesion()).status_code == 204
    _error(client.get(URL, headers=_con_sesion()), 401, "SESION_NO_VIGENTE")


def test_cu13_despues_del_cierre_la_actividad_es_401(client, redis_falso):
    redis_falso.crear_sesion(SESION)
    client.delete(URL, headers=_con_sesion())
    _error(client.post(f"{URL}/actividad", headers=_con_sesion()), 401, "SESION_NO_VIGENTE")
    assert SESION not in redis_falso.sesiones


def test_cu13_redis_caido_es_503_no_204(client, redis_falso):
    redis_falso.crear_sesion(SESION)
    redis_falso.falla = DependenciaNoDisponible("redis")
    _error(client.delete(URL, headers=_con_sesion()), 503, "DEPENDENCIA_NO_DISPONIBLE")


# CU-14 · invalidar la ficha cacheada (rol operador)

URL_CACHE = "/api/v1/cache/equipos/EQ-001"


def test_cu14_operador_invalida_y_renueva(client, redis_falso):
    redis_falso.crear_sesion(SESION, rol="operador", ttl=10)
    redis_falso.fichas["EQ-001"] = {"equipoId": "EQ-001"}
    respuesta = client.delete(URL_CACHE, headers=_con_sesion())
    assert respuesta.status_code == 204
    assert "EQ-001" not in redis_falso.fichas
    assert redis_falso.sesiones[SESION]["ttl"] == 1800


def test_cu14_sin_copia_tambien_es_204(client, redis_falso):
    redis_falso.crear_sesion(SESION, rol="operador")
    assert client.delete(URL_CACHE, headers=_con_sesion()).status_code == 204
    assert client.delete(URL_CACHE, headers=_con_sesion()).status_code == 204


def test_cu14_lector_es_403_sin_invalidar_ni_renovar(client, redis_falso):
    redis_falso.crear_sesion(SESION, rol="lector", ttl=10)
    redis_falso.fichas["EQ-001"] = {"equipoId": "EQ-001"}
    _error(client.delete(URL_CACHE, headers=_con_sesion()), 403, "ROL_NO_AUTORIZADO")
    assert "EQ-001" in redis_falso.fichas
    assert redis_falso.sesiones[SESION]["ttl"] == 10


def test_cu14_sin_sesion_es_401(client, redis_falso):
    _error(client.delete(URL_CACHE), 401, "SESION_REQUERIDA")
    assert redis_falso.llamadas == []


def test_cu14_equipo_invalido_es_400_antes_de_tocar_redis(client, redis_falso):
    # Sesión válida + equipoId inválido: 400 sin consultar ni renovar la sesión.
    redis_falso.crear_sesion(SESION, rol="operador", ttl=10)
    _error(client.delete("/api/v1/cache/equipos/EQ-1", headers=_con_sesion()), 400, "VALIDACION")
    assert redis_falso.llamadas == []
    assert redis_falso.sesiones[SESION]["ttl"] == 10


def test_cu14_equipo_invalido_sin_sesion_tambien_es_400(client, redis_falso):
    _error(client.delete("/api/v1/cache/equipos/EQ-1"), 400, "VALIDACION")


def test_cu14_redis_caido_es_503(client, redis_falso):
    redis_falso.crear_sesion(SESION, rol="operador")
    redis_falso.falla = DependenciaNoDisponible("redis")
    _error(client.delete(URL_CACHE, headers=_con_sesion()), 503, "DEPENDENCIA_NO_DISPONIBLE")


# sesion_requerida(rol=None) · dependencia reutilizable para las fases siguientes

@pytest.fixture
def client_protegido(app):
    @app.get("/prueba/protegida/{equipoId}")
    def protegida(
        equipoId: Annotated[str, Path(pattern=r"^EQ-\d{3}$")],
        auth: Annotated[Autorizacion, Depends(sesion_requerida())],
    ) -> dict:
        sesion = auth.exigir()
        return {"usuarioId": sesion.usuario_id, "rol": sesion.rol,
                "expiraEnSegundos": sesion.expira_en_segundos}

    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente


def test_sesion_requerida_sin_rol_acepta_cualquier_sesion_vigente(client_protegido, redis_falso):
    redis_falso.crear_sesion(SESION, usuario_id="USR-00042", rol="lector", ttl=5)
    respuesta = client_protegido.get("/prueba/protegida/EQ-001", headers=_con_sesion())
    assert respuesta.status_code == 200
    assert respuesta.json() == {"usuarioId": "USR-00042", "rol": "lector", "expiraEnSegundos": 1800}


def test_sesion_requerida_rechaza_sesion_vencida(client_protegido, redis_falso):
    redis_falso.crear_sesion(SESION, ttl=-2)
    _error(client_protegido.get("/prueba/protegida/EQ-001", headers=_con_sesion()),
           401, "SESION_NO_VIGENTE")


def test_sesion_requerida_valida_la_entrada_antes_que_la_sesion(client_protegido, redis_falso):
    redis_falso.crear_sesion(SESION)
    _error(client_protegido.get("/prueba/protegida/EQ-1", headers=_con_sesion()), 400, "VALIDACION")
    assert redis_falso.llamadas == []
