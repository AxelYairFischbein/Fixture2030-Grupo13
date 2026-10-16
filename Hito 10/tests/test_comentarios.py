"""CU-08, CU-09, CU-10 y CU-20 con Cassandra, Redis y Neo4j falsos (sin Docker).

El catálogo de partidos del conftest contiene PAR-001, PAR-002 y PAR-033 (Neo4j falso).
La muestra de CassandraFalso reproduce carga_muestra.cql del Hito 6.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.dependencias import obtener_catalogo_partidos
from app.errors import DependenciaNoDisponible, DependenciaTimeout
from app.services.catalogo_partidos import CatalogoPartidos
from app.services.comentarios import ServicioComentarios, obtener_servicio_comentarios

URL = "/api/v1/partidos/PAR-001/comentarios"
LECTOR, MODERADOR, OTRO = "SES-PRUEBA-LECTOR", "SES-PRUEBA-MODERADOR", "SES-PRUEBA-OTRO"


@pytest.fixture(autouse=True)
def sesiones(redis_falso):
    redis_falso.crear_sesion(LECTOR, usuario_id="USR-00001", rol="lector", ttl=1000)
    redis_falso.crear_sesion(MODERADOR, usuario_id="USR-00009", rol="moderador", ttl=1000)
    redis_falso.crear_sesion(OTRO, usuario_id="USR-00002", rol="lector", ttl=1000)


def _error(respuesta, http_status: int, codigo: str) -> dict:
    assert respuesta.status_code == http_status, respuesta.text
    error = respuesta.json()["error"]
    assert error["codigo"] == codigo
    assert error["requestId"] == respuesta.headers["X-Request-Id"]
    return error


def _sesion(sesion_id: str) -> dict:
    return {"X-Session-Id": sesion_id}


def _publicacion(sesion_id: str = LECTOR, clave: str | None = None) -> dict:
    return {"X-Session-Id": sesion_id, "Idempotency-Key": clave or str(uuid.uuid4())}


def _ids(respuesta) -> list[str]:
    return [item["comentarioId"] for item in respuesta.json()["items"]]


def _con_reloj(app, cassandra_falso, redis_falso, catalogo, instante: datetime) -> None:
    app.dependency_overrides[obtener_servicio_comentarios] = lambda: ServicioComentarios(
        cassandra_falso, redis_falso, catalogo, reloj=lambda: instante)


# CU-08 · leer comentarios de un partido

def test_cu08_minuto_anonimo_solo_visibles_sin_tocar_redis(client, cassandra_falso, redis_falso):
    respuesta = client.get(URL, params={"minuto": "2030-06-10T18:01:30Z"})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["partidoId"] == "PAR-001"
    assert _ids(respuesta) == ["MUESTRA-008", "MUESTRA-005", "MUESTRA-006"]
    assert cuerpo["siguienteCursor"] is None
    assert cuerpo["items"][0] == {
        "comentarioId": "MUESTRA-008", "usuarioId": "USR-00001",
        "creadoEn": "2030-06-10T18:01:59.000Z", "contenido": "Comentario de muestra 008",
        "estado": "visible", "likes": 1,
    }
    assert redis_falso.llamadas == []
    assert cassandra_falso.llamadas == ["leer_por_partido"]


def test_cu08_moderador_recibe_todos_los_estados(client, redis_falso):
    respuesta = client.get(URL, params={"minuto": "2030-06-10T18:01:00Z"}, headers=_sesion(MODERADOR))
    assert respuesta.status_code == 200
    # Hito 6, consultas.cql Q1.
    assert _ids(respuesta) == ["MUESTRA-008", "MUESTRA-007", "MUESTRA-005", "MUESTRA-006",
                               "MUESTRA-004"]
    assert redis_falso.sesiones[MODERADOR]["ttl"] == 1800  # la sesión enviada se renueva


def test_cu08_lector_con_sesion_solo_ve_visibles(client):
    respuesta = client.get(URL, params={"minuto": "2030-06-10T18:01:00Z"}, headers=_sesion(LECTOR))
    assert _ids(respuesta) == ["MUESTRA-008", "MUESTRA-005", "MUESTRA-006"]


def test_cu08_ventana_entre_minutos(client):
    params = {"desde": "2030-06-10T18:00:30Z", "hasta": "2030-06-10T18:02:10Z"}
    moderador = client.get(URL, params=params, headers=_sesion(MODERADOR))
    # Hito 6, consultas.cql Q2: [18:00:30, 18:02:10) excluye MUESTRA-001 y MUESTRA-010.
    assert _ids(moderador) == ["MUESTRA-009", "MUESTRA-008", "MUESTRA-007", "MUESTRA-005",
                               "MUESTRA-006", "MUESTRA-004", "MUESTRA-003", "MUESTRA-002"]
    anonimo = client.get(URL, params=params)
    assert _ids(anonimo) == ["MUESTRA-009", "MUESTRA-008", "MUESTRA-005", "MUESTRA-006",
                             "MUESTRA-003"]


def test_cu08_ventana_con_offset_se_normaliza_a_utc(client):
    params = {"desde": "2030-06-10T15:00:30-03:00", "hasta": "2030-06-10T15:02:10-03:00"}
    assert len(_ids(client.get(URL, params=params))) == 5


def test_cu08_cursor_antes_de(client):
    params = {"minuto": "2030-06-10T18:01:00Z", "limite": 3}
    pagina1 = client.get(URL, params=params, headers=_sesion(MODERADOR))
    assert _ids(pagina1) == ["MUESTRA-008", "MUESTRA-007", "MUESTRA-005"]
    cursor = pagina1.json()["siguienteCursor"]
    assert cursor == "2030-06-10T18:01:20.000Z|MUESTRA-005"
    pagina2 = client.get(URL, params=params | {"antesDe": cursor}, headers=_sesion(MODERADOR))
    assert _ids(pagina2) == ["MUESTRA-006", "MUESTRA-004"]
    assert pagina2.json()["siguienteCursor"] is None


def test_cu08_por_defecto_son_los_ultimos_60_segundos(app, cassandra_falso, redis_falso, catalogo):
    # Ventana [18:01:10, 18:02:10): cruza el cambio de minuto. Con solo el minuto actual
    # (18:02) se vería únicamente MUESTRA-009.
    _con_reloj(app, cassandra_falso, redis_falso, catalogo, datetime(2030, 6, 10, 18, 2, 10, tzinfo=UTC))
    with TestClient(app) as cliente:
        anonimo = cliente.get(URL)
        moderador = cliente.get(URL, headers=_sesion(MODERADOR))
        limite = cliente.get(URL, params={"limite": 21})
    assert _ids(anonimo) == ["MUESTRA-009", "MUESTRA-008", "MUESTRA-005", "MUESTRA-006"]
    assert _ids(moderador) == ["MUESTRA-009", "MUESTRA-008", "MUESTRA-007", "MUESTRA-005",
                               "MUESTRA-006"]
    _error(limite, 400, "VALIDACION")


def test_cu08_por_defecto_excluye_lo_anterior_a_60_segundos(app, cassandra_falso, redis_falso,
                                                             catalogo):
    _con_reloj(app, cassandra_falso, redis_falso, catalogo, datetime(2030, 6, 10, 18, 3, 6, tzinfo=UTC))
    with TestClient(app) as cliente:
        respuesta = cliente.get(URL)
    # [18:02:06, 18:03:06): MUESTRA-009 (18:02:05) queda afuera; MUESTRA-010 (18:02:10) entra.
    assert _ids(respuesta) == ["MUESTRA-010"]


def test_cu08_minuto_sin_comentarios_es_200_vacio(client):
    respuesta = client.get(URL, params={"minuto": "2030-06-10T19:00:00Z"})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"partidoId": "PAR-001", "items": [], "siguienteCursor": None}


@pytest.mark.parametrize("params", [
    {"desde": "2030-06-10T18:00:00Z", "hasta": "2030-06-10T18:05:01Z"},   # ventana > 5 min
    {"desde": "2030-06-10T18:02:00Z", "hasta": "2030-06-10T18:01:00Z"},   # invertida
    {"desde": "2030-06-10T18:01:00Z", "hasta": "2030-06-10T18:01:00Z"},   # vacía
    {"desde": "2030-06-10T18:01:00Z"},                                    # falta hasta
    {"minuto": "2030-06-10T18:01:00Z", "desde": "2030-06-10T18:01:00Z",
     "hasta": "2030-06-10T18:02:00Z"},                                    # dos modos
    {"minuto": "2030-06-10T18:01:00"},                                    # sin zona
    {"minuto": "2030-06-10T18:01:00Z", "limite": 21},                     # máximo 20 por minuto
    {"desde": "2030-06-10T18:00:00Z", "hasta": "2030-06-10T18:01:00Z", "limite": 51},
    {"minuto": "2030-06-10T18:01:00Z", "limite": 0},
    {"minuto": "2030-06-10T18:01:00Z", "antesDe": "sin-separador"},
    {"minuto": "2030-06-10T18:01:00Z", "antesDe": "ayer|MUESTRA-001"},
    {"minuto": "2030-06-10T18:01:00Z", "antesDe": "2030-06-10T18:01:00|MUESTRA-001"},
    {"minuto": "2030-06-10T18:01:00Z", "antesDe": "2030-06-10T18:01:00Z|MUESTRA 001"},
])
def test_cu08_entrada_invalida_es_400_sin_consultar(client, cassandra_falso, redis_falso, neo4j_falso,
                                                    params):
    _error(client.get(URL, params=params, headers=_sesion(MODERADOR)), 400, "VALIDACION")
    assert cassandra_falso.llamadas == []
    assert redis_falso.llamadas == []
    assert neo4j_falso.llamadas == []


def test_cu08_ventana_de_5_minutos_exactos_es_valida(client):
    params = {"desde": "2030-06-10T18:00:00Z", "hasta": "2030-06-10T18:05:00Z", "limite": 50}
    assert client.get(URL, params=params).status_code == 200


def test_cu08_partido_formato_invalido_es_400(client, cassandra_falso):
    _error(client.get("/api/v1/partidos/PAR-1/comentarios"), 400, "VALIDACION")
    assert cassandra_falso.llamadas == []


def test_cu08_partido_fuera_del_catalogo_es_404_sin_consultar_cassandra(client, cassandra_falso):
    error = _error(client.get("/api/v1/partidos/PAR-999/comentarios"), 404, "PARTIDO_NO_ENCONTRADO")
    assert error["detalles"] == [{"campo": "partidoId", "problema": "PAR-999 no existe"}]
    assert cassandra_falso.llamadas == []


def test_cu08_catalogo_no_cargado_es_503(app, neo4j_falso, cassandra_falso):
    neo4j_falso.falla = DependenciaNoDisponible("neo4j")
    sin_cargar = CatalogoPartidos(neo4j_falso, Settings(_env_file=None))
    app.dependency_overrides[obtener_catalogo_partidos] = lambda: sin_cargar
    with TestClient(app) as cliente:
        _error(cliente.get(URL), 503, "DEPENDENCIA_NO_DISPONIBLE")
    assert cassandra_falso.llamadas == []


def test_cu08_sesion_invalida_es_401_sin_consultar_cassandra(client, cassandra_falso):
    _error(client.get(URL, headers=_sesion("SES-PRUEBA-NO-EXISTE")), 401, "SESION_NO_VIGENTE")
    assert cassandra_falso.llamadas == []


def test_cu08_redis_caido_con_sesion_es_503(client, redis_falso, cassandra_falso):
    redis_falso.falla = DependenciaNoDisponible("redis")
    _error(client.get(URL, headers=_sesion(MODERADOR)), 503, "DEPENDENCIA_NO_DISPONIBLE")
    assert cassandra_falso.llamadas == []


@pytest.mark.parametrize("falla, http_status, codigo", [
    (DependenciaNoDisponible("cassandra"), 503, "DEPENDENCIA_NO_DISPONIBLE"),
    (DependenciaTimeout("cassandra"), 504, "DEPENDENCIA_TIMEOUT"),
])
def test_cu08_cassandra_caida_nunca_es_200_vacio(client, cassandra_falso, falla, http_status, codigo):
    cassandra_falso.falla = falla
    _error(client.get(URL, params={"minuto": "2030-06-10T18:01:00Z"}), http_status, codigo)


# CU-09 · publicar un comentario

def test_cu09_publica_con_claves_calculadas_por_el_servidor(app, cassandra_falso, redis_falso,
                                                            catalogo):
    ahora = datetime(2030, 6, 10, 21, 30, 15, 123456, tzinfo=UTC)
    _con_reloj(app, cassandra_falso, redis_falso, catalogo, ahora)
    clave = "3F9A0C1E-6B3D-4F7A-9D55-2A1B7C9E4D10"
    with TestClient(app) as cliente:
        respuesta = cliente.post(URL, json={"contenido": "Gran jugada"},
                                 headers=_publicacion(clave=clave))
        assert respuesta.status_code == 201
        assert respuesta.json() == {
            "comentarioId": clave.lower(), "partidoId": "PAR-001", "usuarioId": "USR-00001",
            "creadoEn": "2030-06-10T21:30:15.123Z", "contenido": "Gran jugada",
            "estado": "visible", "likes": 0,
        }
        # Visible en CU-08 (minuto) y en CU-10 con las mismas claves.
        lectura = cliente.get(URL, params={"minuto": "2030-06-10T21:30:00Z"})
        assert _ids(lectura) == [clave.lower()]
        historial = cliente.get("/api/v1/usuarios/USR-00001/comentarios",
                                params={"dia": "2030-06-10"}, headers=_sesion(LECTOR))
        assert _ids(historial)[0] == clave.lower()
    assert len(cassandra_falso.filas_por_partido) == 12
    assert len(cassandra_falso.filas_por_usuario) == 12
    assert redis_falso.sesiones[LECTOR]["ttl"] == 1800  # publicar es actividad


def test_cu09_reintento_con_la_misma_clave_no_duplica(client, cassandra_falso):
    cabeceras = _publicacion()
    primera = client.post(URL, json={"contenido": "Hola"}, headers=cabeceras)
    segunda = client.post(URL, json={"contenido": "Hola"}, headers=cabeceras)
    assert (primera.status_code, segunda.status_code) == (201, 201)
    assert segunda.json() == primera.json()
    assert len(cassandra_falso.filas_por_partido) == 12
    assert len(cassandra_falso.filas_por_usuario) == 12
    assert cassandra_falso.llamadas.count("insertar_comentario") == 1


def test_cu09_reintento_no_deshace_una_moderacion(client, cassandra_falso):
    cabeceras = _publicacion()
    creado = client.post(URL, json={"contenido": "Hola"}, headers=cabeceras).json()
    moderado = client.patch(f"{URL}/{creado['comentarioId']}", headers=_sesion(MODERADOR),
                            json={"creadoEn": creado["creadoEn"], "estado": "oculto"})
    assert moderado.status_code == 200
    reintento = client.post(URL, json={"contenido": "Hola"}, headers=cabeceras)
    assert reintento.status_code == 201
    assert reintento.json()["estado"] == "oculto"
    assert reintento.json()["creadoEn"] == creado["creadoEn"]


def test_cu09_timeout_de_escritura_es_504_y_el_reintento_reutiliza_creado_en(
        app, cassandra_falso, redis_falso, catalogo):
    instantes = iter([datetime(2030, 6, 10, 21, 0, 0, 500000, tzinfo=UTC),
                      datetime(2030, 6, 10, 21, 0, 9, tzinfo=UTC)])
    app.dependency_overrides[obtener_servicio_comentarios] = lambda: ServicioComentarios(
        cassandra_falso, redis_falso, catalogo, reloj=lambda: next(instantes))
    cabeceras = _publicacion()
    with TestClient(app) as cliente:
        cassandra_falso.falla_escritura = DependenciaTimeout("cassandra")
        error = _error(cliente.post(URL, json={"contenido": "Hola"}, headers=cabeceras),
                       504, "DEPENDENCIA_TIMEOUT")
        assert "misma Idempotency-Key" in error["mensaje"]
        cassandra_falso.falla_escritura = None
        reintento = cliente.post(URL, json={"contenido": "Hola"}, headers=cabeceras)
    assert reintento.status_code == 201
    assert reintento.json()["creadoEn"] == "2030-06-10T21:00:00.500Z"
    assert len(cassandra_falso.filas_por_partido) == 12


@pytest.mark.parametrize("ruta, contenido", [
    (URL, "Otro texto"),
    ("/api/v1/partidos/PAR-002/comentarios", "Hola"),
])
def test_cu09_misma_clave_con_otro_body_es_409(client, cassandra_falso, ruta, contenido):
    cabeceras = _publicacion()
    assert client.post(URL, json={"contenido": "Hola"}, headers=cabeceras).status_code == 201
    _error(client.post(ruta, json={"contenido": contenido}, headers=cabeceras),
           409, "IDEMPOTENCY_KEY_REUTILIZADA")
    assert cassandra_falso.llamadas.count("insertar_comentario") == 1


def test_cu09_misma_clave_de_otro_autor_es_409(client):
    clave = str(uuid.uuid4())
    assert client.post(URL, json={"contenido": "Hola"}, headers=_publicacion(LECTOR, clave)).status_code == 201
    _error(client.post(URL, json={"contenido": "Hola"}, headers=_publicacion(OTRO, clave)),
           409, "IDEMPOTENCY_KEY_REUTILIZADA")


def test_cu09_sin_sesion_es_401_sin_escribir(client, cassandra_falso, redis_falso):
    _error(client.post(URL, json={"contenido": "Hola"},
                       headers={"Idempotency-Key": str(uuid.uuid4())}), 401, "SESION_REQUERIDA")
    assert cassandra_falso.llamadas == []
    assert redis_falso.idempotencia == {}


def test_cu09_sesion_vencida_es_401(client, redis_falso, cassandra_falso):
    redis_falso.crear_sesion("SES-PRUEBA-VENCIDA", ttl=-2)
    _error(client.post(URL, json={"contenido": "Hola"}, headers=_publicacion("SES-PRUEBA-VENCIDA")),
           401, "SESION_NO_VIGENTE")
    assert cassandra_falso.llamadas == []


@pytest.mark.parametrize("cuerpo, cabeceras", [
    ({"contenido": "Hola"}, {"X-Session-Id": LECTOR}),                              # sin clave
    ({"contenido": "Hola"}, {"X-Session-Id": LECTOR, "Idempotency-Key": "abc"}),   # no es UUID
    ({"contenido": ""}, None),
    ({"contenido": "x" * 281}, None),
    ({"contenido": "Hola", "usuarioId": "USR-00002"}, None),                        # campo extra
    ({"contenido": "Hola", "estado": "oculto"}, None),
    ({}, None),
    ({"contenido": 5}, None),
])
def test_cu09_entrada_invalida_es_400_sin_tocar_bases(client, cassandra_falso, redis_falso,
                                                      cuerpo, cabeceras):
    _error(client.post(URL, json=cuerpo, headers=cabeceras or _publicacion()), 400, "VALIDACION")
    assert cassandra_falso.llamadas == []
    assert redis_falso.llamadas == []


def test_cu09_contenido_de_280_caracteres_es_valido(client):
    assert client.post(URL, json={"contenido": "x" * 280}, headers=_publicacion()).status_code == 201


def test_cu09_partido_inexistente_es_404_sin_consumir_la_clave(client, cassandra_falso, redis_falso):
    cabeceras = _publicacion()
    _error(client.post("/api/v1/partidos/PAR-999/comentarios", json={"contenido": "Hola"},
                       headers=cabeceras), 404, "PARTIDO_NO_ENCONTRADO")
    assert cassandra_falso.llamadas == []
    assert redis_falso.idempotencia == {}
    assert client.post(URL, json={"contenido": "Hola"}, headers=cabeceras).status_code == 201


def test_cu09_redis_caido_es_503_sin_escribir(client, redis_falso, cassandra_falso):
    redis_falso.falla = DependenciaNoDisponible("redis")
    _error(client.post(URL, json={"contenido": "Hola"}, headers=_publicacion()),
           503, "DEPENDENCIA_NO_DISPONIBLE")
    assert cassandra_falso.llamadas == []


def test_cu09_cassandra_caida_es_503(client, cassandra_falso):
    cassandra_falso.falla_escritura = DependenciaNoDisponible("cassandra")
    _error(client.post(URL, json={"contenido": "Hola"}, headers=_publicacion()),
           503, "DEPENDENCIA_NO_DISPONIBLE")


# CU-10 · historial diario de un autor

HISTORIAL = "/api/v1/usuarios/USR-00001/comentarios"


def test_cu10_el_propio_autor_ve_su_dia(client):
    respuesta = client.get(HISTORIAL, params={"dia": "2030-06-10"}, headers=_sesion(LECTOR))
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["usuarioId"], cuerpo["dia"]) == ("USR-00001", "2030-06-10")
    # Hito 6 Q3 (incluye PAR-002: el historial no se limita a un partido).
    assert _ids(respuesta) == ["MUESTRA-010", "MUESTRA-008", "MUESTRA-005", "MUESTRA-011",
                               "MUESTRA-003", "MUESTRA-001"]
    assert cuerpo["items"][3]["partidoId"] == "PAR-002"
    assert cuerpo["siguienteCursor"] is None


def test_cu10_moderador_ve_el_historial_de_otro(client):
    respuesta = client.get("/api/v1/usuarios/USR-00003/comentarios", params={"dia": "2030-06-10"},
                           headers=_sesion(MODERADOR))
    assert _ids(respuesta) == ["MUESTRA-007", "MUESTRA-004"]
    assert [i["estado"] for i in respuesta.json()["items"]] == ["pendiente", "oculto"]


def test_cu10_cursor(client):
    params = {"dia": "2030-06-10", "limite": 2}
    pagina1 = client.get(HISTORIAL, params=params, headers=_sesion(LECTOR)).json()
    assert pagina1["siguienteCursor"] == "2030-06-10T18:01:59.000Z|MUESTRA-008"
    pagina2 = client.get(HISTORIAL, params=params | {"antesDe": pagina1["siguienteCursor"]},
                         headers=_sesion(LECTOR))
    assert _ids(pagina2) == ["MUESTRA-005", "MUESTRA-011"]


def test_cu10_otro_usuario_es_403_sin_renovar(client, redis_falso, cassandra_falso):
    _error(client.get(HISTORIAL, params={"dia": "2030-06-10"}, headers=_sesion(OTRO)),
           403, "ROL_NO_AUTORIZADO")
    assert redis_falso.sesiones[OTRO]["ttl"] == 1000
    assert "renovar_sesion" not in redis_falso.llamadas
    assert cassandra_falso.llamadas == []


def test_cu10_sin_sesion_es_401(client, cassandra_falso):
    _error(client.get(HISTORIAL, params={"dia": "2030-06-10"}), 401, "SESION_REQUERIDA")
    assert cassandra_falso.llamadas == []


def test_cu10_dia_sin_comentarios_es_200_vacio(client):
    respuesta = client.get(HISTORIAL, params={"dia": "2030-06-12"}, headers=_sesion(LECTOR))
    assert respuesta.status_code == 200
    assert respuesta.json()["items"] == []


@pytest.mark.parametrize("ruta, params", [
    ("/api/v1/usuarios/USR-1/comentarios", {"dia": "2030-06-10"}),
    (HISTORIAL, {}),
    (HISTORIAL, {"dia": "2030-02-30"}),
    (HISTORIAL, {"dia": "2030-06-10", "limite": 21}),
    (HISTORIAL, {"dia": "2030-06-10", "antesDe": "x|y|z"}),
])
def test_cu10_entrada_invalida_es_400(client, cassandra_falso, redis_falso, ruta, params):
    _error(client.get(ruta, params=params, headers=_sesion(LECTOR)), 400, "VALIDACION")
    assert cassandra_falso.llamadas == []
    assert redis_falso.llamadas == []


def test_cu10_cassandra_timeout_es_504(client, cassandra_falso):
    cassandra_falso.falla = DependenciaTimeout("cassandra")
    _error(client.get(HISTORIAL, params={"dia": "2030-06-10"}, headers=_sesion(LECTOR)),
           504, "DEPENDENCIA_TIMEOUT")


# CU-20 · moderar un comentario

def _moderar(client, comentario_id="MUESTRA-005", creado_en="2030-06-10T18:01:20.000Z",
             estado="oculto", sesion_id=MODERADOR, partido="PAR-001"):
    return client.patch(f"/api/v1/partidos/{partido}/comentarios/{comentario_id}",
                        json={"creadoEn": creado_en, "estado": estado}, headers=_sesion(sesion_id))


def test_cu20_oculta_en_las_dos_representaciones(client, cassandra_falso):
    respuesta = _moderar(client)
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "comentarioId": "MUESTRA-005", "partidoId": "PAR-001", "usuarioId": "USR-00001",
        "creadoEn": "2030-06-10T18:01:20.000Z", "estadoAnterior": "visible", "estado": "oculto",
        "cambio": True,
    }
    app_ = client.get(URL, params={"minuto": "2030-06-10T18:01:00Z"})
    assert "MUESTRA-005" not in _ids(app_)
    mod = client.get(URL, params={"minuto": "2030-06-10T18:01:00Z"}, headers=_sesion(MODERADOR))
    assert "MUESTRA-005" in _ids(mod)
    historial = client.get(HISTORIAL, params={"dia": "2030-06-10"}, headers=_sesion(LECTOR)).json()
    assert {i["comentarioId"]: i["estado"] for i in historial["items"]}["MUESTRA-005"] == "oculto"
    assert len(cassandra_falso.filas_por_partido) == 11


def test_cu20_mismo_estado_es_cambio_false_sin_escribir(client, cassandra_falso):
    respuesta = _moderar(client, estado="visible")
    assert respuesta.status_code == 200
    assert (respuesta.json()["estadoAnterior"], respuesta.json()["cambio"]) == ("visible", False)
    assert cassandra_falso.escrituras() == 0


def test_cu20_pendiente_a_visible_y_restaurar_oculto(client):
    assert _moderar(client, "MUESTRA-007", "2030-06-10T18:01:45Z", "visible").json()["cambio"] is True
    restaurado = _moderar(client, "MUESTRA-004", "2030-06-10T18:01:05.000Z", "visible").json()
    assert (restaurado["estadoAnterior"], restaurado["estado"]) == ("oculto", "visible")


def test_cu20_creado_en_equivocado_es_404_sin_escribir(client, cassandra_falso):
    _error(_moderar(client, creado_en="2030-06-10T18:01:21.000Z"), 404, "COMENTARIO_NO_ENCONTRADO")
    assert cassandra_falso.escrituras() == 0
    assert len(cassandra_falso.filas_por_partido) == 11


def test_cu20_comentario_de_otro_partido_es_404(client):
    _error(_moderar(client, "MUESTRA-011", "2030-06-10T18:01:10.000Z"), 404, "COMENTARIO_NO_ENCONTRADO")


def test_cu20_partido_fuera_del_catalogo_es_404(client, cassandra_falso):
    _error(_moderar(client, partido="PAR-999"), 404, "PARTIDO_NO_ENCONTRADO")
    assert cassandra_falso.llamadas == []


def test_cu20_lector_es_403_sin_renovar(client, redis_falso, cassandra_falso):
    _error(_moderar(client, sesion_id=LECTOR), 403, "ROL_NO_AUTORIZADO")
    assert redis_falso.sesiones[LECTOR]["ttl"] == 1000
    assert cassandra_falso.llamadas == []


def test_cu20_sin_sesion_es_401(client, cassandra_falso):
    respuesta = client.patch(f"{URL}/MUESTRA-005",
                             json={"creadoEn": "2030-06-10T18:01:20.000Z", "estado": "oculto"})
    _error(respuesta, 401, "SESION_REQUERIDA")
    assert cassandra_falso.llamadas == []


@pytest.mark.parametrize("cuerpo", [
    {"creadoEn": "2030-06-10T18:01:20.000Z", "estado": "pendiente"},   # volver a pendiente
    {"creadoEn": "2030-06-10T18:01:20.000Z", "estado": "borrado"},
    {"creadoEn": "2030-06-10T18:01:20", "estado": "oculto"},           # sin zona
    {"creadoEn": "2030-06-10T18:01:20.000500Z", "estado": "oculto"},   # sub-milisegundo
    {"estado": "oculto"},
    {"creadoEn": "2030-06-10T18:01:20.000Z", "estado": "oculto", "likes": 3},
])
def test_cu20_entrada_invalida_es_400(client, cassandra_falso, redis_falso, cuerpo):
    _error(client.patch(f"{URL}/MUESTRA-005", json=cuerpo, headers=_sesion(MODERADOR)),
           400, "VALIDACION")
    assert cassandra_falso.llamadas == []
    assert redis_falso.llamadas == []


def test_cu20_comentario_id_invalido_es_400(client):
    _error(_moderar(client, comentario_id="MUESTRA_005"), 400, "VALIDACION")


def test_cu20_timeout_de_escritura_es_504(client, cassandra_falso):
    cassandra_falso.falla_escritura = DependenciaTimeout("cassandra")
    error = _error(_moderar(client), 504, "DEPENDENCIA_TIMEOUT")
    assert "Reintente" in error["mensaje"]


def test_openapi_describe_las_rutas_de_comentarios(client):
    rutas = client.get("/openapi.json").json()["paths"]
    assert set(rutas["/api/v1/partidos/{partidoId}/comentarios"]) == {"get", "post"}
    assert set(rutas["/api/v1/partidos/{partidoId}/comentarios/{comentarioId}"]) == {"patch"}
    assert "409" in rutas["/api/v1/partidos/{partidoId}/comentarios"]["post"]["responses"]
    assert "get" in rutas["/api/v1/usuarios/{usuarioId}/comentarios"]
