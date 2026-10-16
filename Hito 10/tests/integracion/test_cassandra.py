"""Integración con el Cassandra del Hito 6 (muestra de carga_muestra.cql) y el Redis del Hito 7.

El partido se valida contra el catálogo cargado desde Neo4j (Hito 5). Si Neo4j no está
levantado, se inyecta un catálogo estático con PAR-001…PAR-064 para no exigir ese contenedor.

Las escrituras usan PAR-064, un autor de prueba aleatorio y una Idempotency-Key nueva; al
terminar se borran las filas por clave completa en las dos tablas y la clave en Redis.
"""

import secrets
import uuid
from datetime import UTC, datetime

import pytest
from cassandra.cluster import Cluster
from cassandra.io.asyncioreactor import AsyncioConnection
from fastapi.testclient import TestClient

from app.adapters.cassandra_adaptador import minuto_de, segmento
from app.dependencias import obtener_catalogo_partidos
from app.main import create_app
from app.services.catalogo_partidos import CARGADO

pytestmark = pytest.mark.integration

URL = "/api/v1/partidos/PAR-001/comentarios"
URL_ESCRITURA = "/api/v1/partidos/PAR-064/comentarios"
Q1 = {"minuto": "2030-06-10T18:01:00Z"}
Q2 = {"desde": "2030-06-10T18:00:30Z", "hasta": "2030-06-10T18:02:10Z"}


class CatalogoEstatico:
    """Sustituto del catálogo cuando Neo4j no está levantado: los 64 partidos del Fixture."""

    PARTIDOS = {f"PAR-{n:03d}" for n in range(1, 65)}

    def validar_partido(self, partido_id):
        from app.services.partidos import partido_no_encontrado

        if partido_id not in self.PARTIDOS:
            raise partido_no_encontrado(partido_id)
        return ()

    def estado(self):
        return {"estado": CARGADO, "partidos": len(self.PARTIDOS), "ultimaCarga": None}


@pytest.fixture(scope="module")
def cassandra_directa(settings_reales):
    cluster = Cluster([settings_reales.cassandra_hosts], port=settings_reales.cassandra_port,
                      connection_class=AsyncioConnection, connect_timeout=3)
    try:
        sesion = cluster.connect(settings_reales.cassandra_keyspace)
    except Exception:
        cluster.shutdown()
        pytest.skip('Cassandra del Hito 6 no responde: docker compose -f "Hito 6/docker-compose.yml" '
                    "up -d y ejecutar esquema.cql y carga_muestra.cql")
    muestra = sesion.execute(
        "SELECT comentario_id FROM comentarios_por_partido WHERE partido_id = 'PAR-001' "
        "AND minuto = '2030-06-10T18:00:00Z' AND segmento = 2").all()
    if not muestra:
        cluster.shutdown()
        pytest.skip("Falta la muestra del Hito 6: ejecutar scripts/carga_muestra.cql")
    yield sesion
    cluster.shutdown()


@pytest.fixture(scope="module")
def cliente_api(settings_reales, redis_directo, cassandra_directa):
    app = create_app(settings_reales)
    with TestClient(app) as cliente:
        if app.state.catalogo_partidos.estado()["estado"] != CARGADO:
            app.dependency_overrides[obtener_catalogo_partidos] = CatalogoEstatico
        yield cliente


@pytest.fixture
def escrituras(settings_reales, redis_directo, cassandra_directa):
    """Registra los comentarios creados por la prueba y los borra al terminar."""
    creados: list[dict] = []
    yield creados
    for c in creados:
        creado_en = datetime.fromisoformat(c["creadoEn"])
        cassandra_directa.execute(
            "DELETE FROM comentarios_por_partido WHERE partido_id = %s AND minuto = %s "
            "AND segmento = %s AND creado_en = %s AND comentario_id = %s",
            (c["partidoId"], minuto_de(creado_en), segmento(c["comentarioId"]), creado_en,
             c["comentarioId"]))
        cassandra_directa.execute(
            "DELETE FROM comentarios_por_usuario WHERE usuario_id = %s AND dia = %s "
            "AND creado_en = %s AND comentario_id = %s",
            (c["usuarioId"], creado_en.date(), creado_en, c["comentarioId"]))
        redis_directo.delete(
            f"{settings_reales.redis_prefijo}idem:comentario:{c['comentarioId']}")


def _filas(cassandra_directa, comentario: dict, creado_en: str | None = None) -> tuple[int, int]:
    """Cantidad de filas con la clave completa del comentario en cada tabla."""
    instante = datetime.fromisoformat(creado_en or comentario["creadoEn"])
    por_partido = cassandra_directa.execute(
        "SELECT COUNT(*) FROM comentarios_por_partido WHERE partido_id = %s AND minuto = %s "
        "AND segmento = %s AND creado_en = %s AND comentario_id = %s",
        (comentario["partidoId"], minuto_de(instante), segmento(comentario["comentarioId"]),
         instante, comentario["comentarioId"])).one()[0]
    por_usuario = cassandra_directa.execute(
        "SELECT COUNT(*) FROM comentarios_por_usuario WHERE usuario_id = %s AND dia = %s "
        "AND creado_en = %s AND comentario_id = %s",
        (comentario["usuarioId"], instante.date(), instante, comentario["comentarioId"])).one()[0]
    return por_partido, por_usuario


def _ids(respuesta) -> list[str]:
    assert respuesta.status_code == 200, respuesta.text
    return [i["comentarioId"] for i in respuesta.json()["items"]]


def test_salud_informa_cassandra_disponible(cliente_api):
    assert cliente_api.get("/api/v1/salud").json()["dependencias"]["cassandra"] == "disponible"


# Lecturas contra la muestra del Hito 6 (consultas.cql)

def test_cu08_q1_minuto(cliente_api, sesiones):
    moderador, _ = sesiones(rol="moderador", usuario_id="USR-00009")
    assert _ids(cliente_api.get(URL, params=Q1, headers={"X-Session-Id": moderador})) == [
        "MUESTRA-008", "MUESTRA-007", "MUESTRA-005", "MUESTRA-006", "MUESTRA-004"]
    assert _ids(cliente_api.get(URL, params=Q1)) == ["MUESTRA-008", "MUESTRA-005", "MUESTRA-006"]


def test_cu08_q2_ventana_y_cursor(cliente_api, sesiones):
    moderador, _ = sesiones(rol="moderador", usuario_id="USR-00009")
    cabeceras = {"X-Session-Id": moderador}
    assert _ids(cliente_api.get(URL, params=Q2, headers=cabeceras)) == [
        "MUESTRA-009", "MUESTRA-008", "MUESTRA-007", "MUESTRA-005", "MUESTRA-006", "MUESTRA-004",
        "MUESTRA-003", "MUESTRA-002"]
    pagina1 = cliente_api.get(URL, params=Q2 | {"limite": 4}, headers=cabeceras)
    assert _ids(pagina1) == ["MUESTRA-009", "MUESTRA-008", "MUESTRA-007", "MUESTRA-005"]
    cursor = pagina1.json()["siguienteCursor"]
    pagina2 = cliente_api.get(URL, params=Q2 | {"limite": 4, "antesDe": cursor}, headers=cabeceras)
    assert _ids(pagina2) == ["MUESTRA-006", "MUESTRA-004", "MUESTRA-003", "MUESTRA-002"]


def test_cu08_ventana_mayor_a_5_minutos_es_400(cliente_api):
    respuesta = cliente_api.get(URL, params={"desde": "2030-06-10T18:00:00Z",
                                             "hasta": "2030-06-10T18:06:00Z"})
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"


def test_cu08_partido_inexistente_es_404(cliente_api):
    respuesta = cliente_api.get("/api/v1/partidos/PAR-999/comentarios")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "PARTIDO_NO_ENCONTRADO"


def test_cu10_q3_historial(cliente_api, sesiones):
    propio, _ = sesiones(rol="lector", usuario_id="USR-00001")
    respuesta = cliente_api.get("/api/v1/usuarios/USR-00001/comentarios",
                                params={"dia": "2030-06-10"}, headers={"X-Session-Id": propio})
    assert _ids(respuesta) == ["MUESTRA-010", "MUESTRA-008", "MUESTRA-005", "MUESTRA-011",
                               "MUESTRA-003", "MUESTRA-001"]
    ajeno, _ = sesiones(rol="lector", usuario_id="USR-00002")
    denegado = cliente_api.get("/api/v1/usuarios/USR-00001/comentarios",
                               params={"dia": "2030-06-10"}, headers={"X-Session-Id": ajeno})
    assert denegado.status_code == 403


# Escrituras: publicación idempotente y moderación

def test_cu09_publicacion_idempotente_y_cu20_moderacion(cliente_api, sesiones, cassandra_directa,
                                                         escrituras):
    usuario = f"USR-9{secrets.randbelow(10_000):04d}"
    autor, _ = sesiones(rol="lector", usuario_id=usuario)
    moderador, _ = sesiones(rol="moderador", usuario_id="USR-00009")
    clave = str(uuid.uuid4())
    cabeceras = {"X-Session-Id": autor, "Idempotency-Key": clave}

    sin_sesion = cliente_api.post(URL_ESCRITURA, json={"contenido": "Sin sesión"},
                                  headers={"Idempotency-Key": str(uuid.uuid4())})
    assert sin_sesion.status_code == 401

    creado = cliente_api.post(URL_ESCRITURA, json={"contenido": "Prueba de integración"},
                              headers=cabeceras)
    assert creado.status_code == 201, creado.text
    comentario = creado.json()
    escrituras.append(comentario)
    assert (comentario["comentarioId"], comentario["usuarioId"], comentario["estado"],
            comentario["likes"]) == (clave, usuario, "visible", 0)
    assert _filas(cassandra_directa, comentario) == (1, 1)

    # Reintento: mismo comentario y las filas no cambian.
    reintento = cliente_api.post(URL_ESCRITURA, json={"contenido": "Prueba de integración"},
                                 headers=cabeceras)
    assert (reintento.status_code, reintento.json()) == (201, comentario)
    assert _filas(cassandra_directa, comentario) == (1, 1)

    # Misma clave con otro body → 409.
    conflicto = cliente_api.post(URL_ESCRITURA, json={"contenido": "Otro texto"}, headers=cabeceras)
    assert conflicto.status_code == 409
    assert conflicto.json()["error"]["codigo"] == "IDEMPOTENCY_KEY_REUTILIZADA"

    # Recién publicado: aparece en CU-08 sin parámetros (últimos 60 s).
    assert _ids(cliente_api.get(URL_ESCRITURA)).count(clave) == 1

    # Visible en CU-08 (modo minuto) y en CU-10 con las mismas claves.
    minuto = minuto_de(datetime.fromisoformat(comentario["creadoEn"])).isoformat()
    lectura = cliente_api.get(URL_ESCRITURA, params={"minuto": minuto, "limite": 20})
    assert _ids(lectura).count(clave) == 1
    dia = comentario["creadoEn"][:10]
    historial_url = f"/api/v1/usuarios/{usuario}/comentarios"
    historial = cliente_api.get(historial_url, params={"dia": dia}, headers={"X-Session-Id": autor})
    assert _ids(historial) == [clave]

    # CU-20 con un creadoEn equivocado: 404 y no se fabrica un comentario fantasma.
    equivocado = "2030-06-10T18:01:21.000Z"
    ruta = f"{URL_ESCRITURA}/{clave}"
    no_encontrado = cliente_api.patch(ruta, json={"creadoEn": equivocado, "estado": "oculto"},
                                      headers={"X-Session-Id": moderador})
    assert no_encontrado.status_code == 404
    assert no_encontrado.json()["error"]["codigo"] == "COMENTARIO_NO_ENCONTRADO"
    assert _filas(cassandra_directa, comentario, equivocado) == (0, 0)

    # CU-20 oculta el comentario en las dos representaciones.
    moderado = cliente_api.patch(ruta, json={"creadoEn": comentario["creadoEn"], "estado": "oculto"},
                                 headers={"X-Session-Id": moderador})
    assert moderado.status_code == 200, moderado.text
    assert (moderado.json()["estadoAnterior"], moderado.json()["estado"],
            moderado.json()["cambio"]) == ("visible", "oculto", True)
    assert clave not in _ids(cliente_api.get(URL_ESCRITURA, params={"minuto": minuto}))
    assert clave in _ids(cliente_api.get(URL_ESCRITURA, params={"minuto": minuto},
                                         headers={"X-Session-Id": moderador}))
    historial = cliente_api.get(historial_url, params={"dia": dia}, headers={"X-Session-Id": autor})
    assert historial.json()["items"][0]["estado"] == "oculto"
    repetido = cliente_api.patch(ruta, json={"creadoEn": comentario["creadoEn"], "estado": "oculto"},
                                 headers={"X-Session-Id": moderador})
    assert repetido.json()["cambio"] is False
    assert _filas(cassandra_directa, comentario) == (1, 1)

    # Un reintento de la publicación no deshace la moderación.
    tardio = cliente_api.post(URL_ESCRITURA, json={"contenido": "Prueba de integración"},
                              headers=cabeceras)
    assert (tardio.status_code, tardio.json()["estado"]) == (201, "oculto")


# Cassandra no disponible: la API apunta a un puerto sin servicio (no se detiene el contenedor)

def test_cassandra_no_disponible_es_503(settings_reales, redis_directo, sesiones):
    caido = settings_reales.model_copy(update={"cassandra_port": 1, "cassandra_connect_timeout_s": 1})
    app = create_app(caido)
    with TestClient(app) as cliente:
        if app.state.catalogo_partidos.estado()["estado"] != CARGADO:
            app.dependency_overrides[obtener_catalogo_partidos] = CatalogoEstatico
        lectura = cliente.get(URL, params=Q1)
        assert lectura.status_code == 503  # nunca 200 []
        assert lectura.json()["error"]["codigo"] == "DEPENDENCIA_NO_DISPONIBLE"
        autor, _ = sesiones(rol="lector", usuario_id="USR-90000")
        clave = str(uuid.uuid4())
        publicacion = cliente.post(URL_ESCRITURA, json={"contenido": "x"},
                                   headers={"X-Session-Id": autor, "Idempotency-Key": clave})
        assert publicacion.status_code == 503
        assert cliente.get("/api/v1/salud").json()["dependencias"]["cassandra"] == "no_disponible"
    redis_directo.delete(f"{settings_reales.redis_prefijo}idem:comentario:{clave}")
