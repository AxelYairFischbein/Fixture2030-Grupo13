"""Pruebas contra las seis fuentes reales (contenedores de los Hitos 4 a 9 y .env local).

Cada prueba que escribe limpia lo que crea: el comentario en Cassandra, la sesión en Redis y el acta
temporal de IRIS. La muestra canónica (por ejemplo PAR-001 en IRIS) nunca se modifica.
"""

import time
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import crear_app, servicios_reales

pytestmark = pytest.mark.integracion
CFG = config.cargar()
API = "/api/v1"


@pytest.fixture(scope="module")
def app_real():
    srv = servicios_reales(CFG)
    cliente = TestClient(crear_app(srv))
    r = cliente.get(f"{API}/salud")
    if r.status_code != 200:
        pytest.skip(f"Fuentes no disponibles: {r.json()['error'].get('detalles')}")
    return cliente, srv


def fuentes(r):
    return {t["fuente"] for t in r.json()["meta"]["fuentes"]}


# --- Una request válida por módulo, verificando que llega a su fuente ----------------------------
def test_mongodb_listado_paginado(app_real):
    cliente, _ = app_real
    r = cliente.get(f"{API}/equipos", params={"confederacion": "UEFA", "pagina": 2, "tamanio": 5})
    assert r.status_code == 200 and fuentes(r) == {"mongodb"}
    assert len(r.json()["data"]) == 5 and r.json()["meta"]["paginacion"]["total"] == 10
    assert all(e["confederacion"] == "UEFA" for e in r.json()["data"])


def test_mongodb_y_redis_cache_aside_e_invalidacion(app_real):
    cliente, _ = app_real
    assert cliente.delete(f"{API}/equipos/EQ-002/cache").status_code == 204
    assert cliente.delete(f"{API}/equipos/EQ-002/cache").status_code == 204  # idempotente
    primera = cliente.get(f"{API}/equipos/EQ-002")
    segunda = cliente.get(f"{API}/equipos/EQ-002")
    assert primera.headers["X-Cache"] == "MISS" and fuentes(primera) == {"redis", "mongodb"}
    assert segunda.headers["X-Cache"] == "HIT" and fuentes(segunda) == {"redis"}
    assert primera.json()["data"] == segunda.json()["data"]


def test_mongodb_plantel_filtrado_y_equipo_inexistente(app_real):
    cliente, _ = app_real
    r = cliente.get(f"{API}/equipos/EQ-001/jugadores", params={"posicion": "ARQUERO"})
    assert r.status_code == 200 and [j["numeroCamiseta"] for j in r.json()["data"]] == [1, 2, 3]
    assert cliente.get(f"{API}/equipos/EQ-999/jugadores").status_code == 404


def test_neo4j_partido_con_eventos_y_agenda(app_real):
    cliente, _ = app_real
    r = cliente.get(f"{API}/partidos/PAR-001")
    assert r.status_code == 200 and fuentes(r) == {"neo4j"}
    p = r.json()["data"]
    assert {e["rol"] for e in p["equipos"]} == {"LOCAL", "VISITANTE"} and p["estadio"]["estadioId"] == "EST-01"
    assert len(p["eventos"]) == 2 and all(len(v["involucrados"]) == 2 for v in p["eventos"])
    agenda = cliente.get(f"{API}/equipos/EQ-001/partidos").json()["data"]
    assert [a["rivalId"] for a in agenda] == ["EQ-002", "EQ-003"]


def test_neo4j_partido_inexistente(app_real):
    cliente, _ = app_real
    r = cliente.get(f"{API}/partidos/PAR-999")
    assert r.status_code == 404 and r.json()["error"]["codigo"] == "RECURSO_NO_ENCONTRADO"


def test_cassandra_ventana_y_cursor(app_real):
    cliente, _ = app_real
    params = {"desde": "2030-06-10T18:00:30Z", "hasta": "2030-06-10T18:02:10Z", "limite": 3}
    vistos, cursor = [], None
    while True:
        r = cliente.get(f"{API}/partidos/PAR-001/comentarios", params={**params, **({"cursor": cursor} if cursor else {})})
        assert r.status_code == 200 and fuentes(r) == {"cassandra"} and r.json()["data"]["particiones"] == 12
        vistos += [c["comentarioId"] for c in r.json()["data"]["items"]]
        cursor = r.json()["meta"]["paginacion"]["siguienteCursor"]
        if not cursor:
            break
    # Muestra del Hito 6: Q2 devuelve ocho comentarios en [18:00:30, 18:02:10), sin repetidos.
    assert len(vistos) == 8 == len(set(vistos)) and "MUESTRA-010" not in vistos and "MUESTRA-002" in vistos


def test_cassandra_ventana_vacia_valida(app_real):
    cliente, _ = app_real
    r = cliente.get(f"{API}/partidos/PAR-050/comentarios",
                    params={"desde": "2030-06-10T18:00:00Z", "hasta": "2030-06-10T18:01:00Z"})
    assert r.status_code == 200 and r.json()["data"]["items"] == []


def test_cassandra_escritura_repetida_no_duplica(app_real):
    cliente, srv = app_real
    clave = "integracion-" + uuid.uuid4().hex[:12]
    cuerpo = {"usuarioId": "USR-00042", "contenido": "Prueba de integración del Hito 10"}
    r1 = cliente.post(f"{API}/partidos/PAR-064/comentarios", json=cuerpo, headers={"Idempotency-Key": clave})
    r2 = cliente.post(f"{API}/partidos/PAR-064/comentarios", json=cuerpo, headers={"Idempotency-Key": clave})
    c = r1.json()["data"]
    try:
        assert (r1.status_code, r2.status_code) == (201, 200) and r2.json()["data"] == c
        assert fuentes(r1) == {"redis", "neo4j", "cassandra"} and fuentes(r2) == {"redis"}
        creado = datetime.fromisoformat(c["creadoEn"].replace("Z", "+00:00"))
        ventana = {"desde": (creado - timedelta(seconds=1)).isoformat(), "hasta": (creado + timedelta(seconds=1)).isoformat()}
        items = cliente.get(f"{API}/partidos/PAR-064/comentarios", params=ventana).json()["data"]["items"]
        assert [i["comentarioId"] for i in items].count(c["comentarioId"]) == 1
    finally:
        sesion = srv.cassandra._conectar()
        ks = CFG.cassandra_keyspace
        sesion.execute(f"DELETE FROM {ks}.comentarios_por_partido WHERE partido_id=%s AND minuto=%s AND segmento=%s "
                       "AND creado_en=%s AND comentario_id=%s",
                       ("PAR-064", datetime.fromisoformat(c["minuto"].replace("Z", "+00:00")), c["segmento"],
                        datetime.fromisoformat(c["creadoEn"].replace("Z", "+00:00")), c["comentarioId"]))
        sesion.execute(f"DELETE FROM {ks}.comentarios_por_usuario WHERE usuario_id=%s AND dia=%s AND creado_en=%s "
                       "AND comentario_id=%s",
                       ("USR-00042", datetime.fromisoformat(c["creadoEn"].replace("Z", "+00:00")).date(),
                        datetime.fromisoformat(c["creadoEn"].replace("Z", "+00:00")), c["comentarioId"]))


def test_redis_sesion_ciclo_de_vida(app_real):
    cliente, _ = app_real
    sesion = cliente.post(f"{API}/sesiones", json={"usuarioId": "USR-00001"}).json()["data"]
    r = cliente.get(f"{API}/sesiones/{sesion['sesionId']}")
    assert r.status_code == 200 and 0 < r.json()["data"]["expiraEnSegundos"] <= CFG.sesion_ttl
    assert cliente.delete(f"{API}/sesiones/{sesion['sesionId']}").status_code == 204
    assert cliente.delete(f"{API}/sesiones/{sesion['sesionId']}").status_code == 204
    assert cliente.get(f"{API}/sesiones/{sesion['sesionId']}").json()["error"]["codigo"] == "SESION_NO_VIGENTE"


def test_redis_sesion_vencida():
    from app.adapters.redis_kv import RedisKV
    from app.services import Servicios
    srv = Servicios(CFG, mongo=None, neo4j=None, cassandra=None, redis=RedisKV(CFG, sesion_ttl=1),
                    influx=None, iris=None)
    cliente = TestClient(crear_app(srv))
    sesion = cliente.post(f"{API}/sesiones", json={"usuarioId": "USR-00001"}).json()["data"]
    assert cliente.get(f"{API}/sesiones/{sesion['sesionId']}").status_code == 200
    time.sleep(2.1)
    r = cliente.get(f"{API}/sesiones/{sesion['sesionId']}")
    assert r.status_code == 404 and r.json()["error"]["codigo"] == "SESION_NO_VIGENTE"


def test_influx_ventana_reciente_y_limites(app_real):
    cliente, _ = app_real
    r = cliente.get(f"{API}/partidos/PAR-001/estadisticas", params={"intervalo": "1m"})
    assert r.status_code == 200 and fuentes(r) == {"influxdb"}
    datos = r.json()["data"]
    if not datos["puntos"]:
        pytest.skip("Sin puntos retenidos: ejecutar scripts/cargar_muestra_influx.py")
    assert {p["equipoId"] for p in datos["puntos"]} == {"EQ-001", "EQ-002"}
    solo = cliente.get(f"{API}/partidos/PAR-001/estadisticas",
                       params={"equipoId": "EQ-002", "desde": datos["desde"], "hasta": datos["hasta"]})
    assert {p["equipoId"] for p in solo.json()["data"]["puntos"]} == {"EQ-002"}
    grande = cliente.get(f"{API}/partidos/PAR-001/estadisticas",
                         params={"desde": "2026-10-01T00:00:00Z", "hasta": "2026-10-03T00:00:00Z", "intervalo": "10s"})
    assert grande.status_code == 400


def test_influx_ventana_sin_puntos(app_real):
    cliente, _ = app_real
    r = cliente.get(f"{API}/partidos/PAR-001/estadisticas",
                    params={"desde": "2026-01-01T00:00:00Z", "hasta": "2026-01-01T01:00:00Z"})
    assert r.status_code == 200 and r.json()["data"]["puntos"] == []


@pytest.fixture
def acta_temporal(app_real):
    """Acta H10-TEMPORAL con el árbitro de la muestra; se borra al terminar."""
    import iris
    _, srv = app_real
    codigo = "H10-TEMPORAL"

    def crear(conexion):
        nativo = iris.createIRIS(conexion)
        if nativo.classMethodValue("FixtureH9.Partido", "PorCodigoExists", codigo):
            raise RuntimeError("Quedó un acta temporal de una ejecución anterior; revisar sin borrar a ciegas.")
        p = nativo.classMethodObject("FixtureH9.Partido", "%New")
        p.set("Codigo", codigo)
        p.set("EstadioCodigo", "EST-02")
        p.set("Arbitro", nativo.classMethodObject("FixtureH9.Arbitro", "PorCodigoOpen", "ARB-001"))
        assert nativo.classMethodValue("%SYSTEM.Status", "IsOK", p.invoke("%Save")) == 1
        return p.invoke("%Id")

    pid = srv.iris._ejecutar("prueba_crear_acta", crear)
    yield codigo
    srv.iris._ejecutar("prueba_borrar_acta",
                       lambda c: iris.createIRIS(c).classMethodValue("FixtureH9.Partido", "%DeleteId", pid))


def test_iris_transiciones_validadas(app_real, acta_temporal):
    cliente, _ = app_real
    url = f"{API}/actas/{acta_temporal}/estado"
    assert cliente.put(url, json={"estado": "FINALIZADO"}).status_code == 409  # salto inválido
    r = cliente.put(url, json={"estado": "EN_JUEGO"})
    assert r.status_code == 200 and r.json()["data"]["cambio"] is True and fuentes(r) == {"iris"}
    assert cliente.put(url, json={"estado": "EN_JUEGO"}).json()["data"]["cambio"] is False  # repetición
    assert cliente.put(url, json={"estado": "FINALIZADO"}).json()["data"]["acta"]["estado"] == "FINALIZADO"
    r = cliente.put(url, json={"estado": "EN_JUEGO"})
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "TRANSICION_INVALIDA"
    assert cliente.get(f"{API}/actas/{acta_temporal}").json()["data"]["estado"] == "FINALIZADO"


def test_iris_acta_muestra_y_inexistente(app_real):
    cliente, _ = app_real
    r = cliente.get(f"{API}/actas/PAR-001")
    assert r.status_code == 200 and fuentes(r) == {"iris"}
    acta = r.json()["data"]
    assert acta["arbitro"]["codigo"] == "ARB-001" and sorted(e["id"] for e in acta["eventos"]) == ["1||1", "1||2"]
    assert cliente.get(f"{API}/actas/NO-EXISTE").status_code == 404


# --- Dependencia detenida: cada driver real apuntando a un puerto sin servicio -------------------------
CAIDAS = {
    "mongodb": (dict(mongo_port=1), "/equipos"),
    "neo4j": (dict(neo4j_uri="bolt://127.0.0.1:1"), "/partidos/PAR-001"),
    "cassandra": (dict(cassandra_port=1), "/partidos/PAR-001/comentarios?desde=2030-06-10T18:00:00Z&hasta=2030-06-10T18:01:00Z"),
    "redis": (dict(redis_port=1), "/sesiones/SES-" + "0" * 24),
    "influxdb": (dict(influx_url="http://127.0.0.1:1"), "/partidos/PAR-001/estadisticas"),
    "iris": (dict(iris_port=1), "/actas/PAR-001"),
}


@pytest.mark.parametrize("fuente", CAIDAS)
def test_dependencia_detenida_responde_503_acotado(fuente):
    cambios, ruta = CAIDAS[fuente]
    cliente = TestClient(crear_app(servicios_reales(replace(CFG, timeout=1, **cambios))))
    inicio = time.perf_counter()
    r = cliente.get(API + ruta)
    duracion = time.perf_counter() - inicio
    assert r.status_code == 503, r.text
    assert r.json()["error"]["dependencia"] == fuente and "127.0.0.1" not in r.text
    assert duracion < 8, f"{fuente} tardó {duracion:.1f} s"
