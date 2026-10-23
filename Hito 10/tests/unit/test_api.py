"""Pruebas sin bases de datos: contrato HTTP, validación, errores e idempotencia con adaptadores falsos."""

from dataclasses import replace

import pytest
import yaml
from fastapi.testclient import TestClient

from app import config
from app.contexto import operacion
from app.errors import TransicionInvalida
from app.main import crear_app
from app.services import Servicios, minutos_de_ventana

CFG = config.cargar()


class Caido(Exception):
    """Excepción de 'driver' para simular una dependencia detenida."""


class Falso:
    """Adaptador en memoria. Cuenta llamadas para comprobar que la validación ocurre antes de consultar."""

    def __init__(self, nombre, caido=False):
        self.nombre, self.caido, self.llamadas = nombre, caido, 0
        self.kv = {}

    def _op(self, op):
        self.llamadas += 1
        with operacion(self.nombre, op, (Caido,)):  # misma traducción de errores que los adaptadores reales
            if self.caido:
                raise Caido()

    def ping(self):
        self._op("ping")

    # mongo
    def buscar_equipo(self, equipo_id):
        self._op("buscar_equipo")
        return {"equipoId": "EQ-001", "codigo": "F01", "nombre": "Seleccion Sintetica 01", "confederacion": "AFC",
                "rankingReferencia": 1, "estado": "PRESELECCIONADO", "region": "ASIA_PACIFICO",
                "sedeBase": {"ciudad": "C", "pais": "P"}, "participacionesMundiales": 1, "titulosMundiales": 0,
                "actualizadoEn": "2026-09-02T00:00:00Z"} if equipo_id == "EQ-001" else None

    # redis
    def leer_equipo(self, equipo_id):
        self._op("leer_cache_equipo")
        return self.kv.get(("eq", equipo_id))

    def guardar_equipo(self, equipo_id, equipo, ttl):
        self._op("guardar_cache_equipo")
        self.kv[("eq", equipo_id)] = equipo

    def obtener_sesion(self, sesion_id):
        self._op("obtener_sesion")
        return None

    def reservar_idempotencia(self, clave, huella, ttl):
        self._op("reservar_idempotencia")
        if clave in self.kv:
            return self.kv[clave]
        self.kv[clave] = {"estado": "EN_CURSO", "huella": huella}
        return None

    def completar_idempotencia(self, clave, huella, resultado, ttl):
        self._op("completar_idempotencia")
        self.kv[clave] = {"estado": "COMPLETADO", "huella": huella, "resultado": resultado}

    def liberar_idempotencia(self, clave):
        self.kv.pop(clave, None)

    # neo4j
    def partido(self, partido_id):
        self._op("partido")
        return {"partidoId": partido_id} if partido_id == "PAR-001" else None

    # cassandra
    def insertar(self, partido_id, comentario_id, usuario_id, contenido, creado_en):
        self._op("insertar_comentario")
        self.kv.setdefault("filas", []).append(comentario_id)
        return {"comentarioId": comentario_id, "partidoId": partido_id, "usuarioId": usuario_id,
                "contenido": contenido, "estado": "visible", "likes": 0, "creadoEn": "2030-06-10T18:00:00.000Z",
                "minuto": "2030-06-10T18:00:00.000Z", "segmento": 0}

    # iris
    def acta(self, codigo):
        self._op("leer_acta")
        return None if codigo != "PAR-001" else {
            "id": "1", "codigo": "PAR-001", "estadioCodigo": "EST-01", "estado": "PENDIENTE",
            "arbitro": {"id": "1", "codigo": "ARB-001", "nombre": "A", "nacionalidad": "F01", "licencia": "L"},
            "eventos": []}

    def cambiar_estado(self, codigo, nuevo):
        self._op("cambiar_estado")
        raise TransicionInvalida(f"Transición no permitida: PENDIENTE -> {nuevo}.")


@pytest.fixture
def entorno():
    fuentes = {n: Falso(n) for n in ("mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris")}
    srv = Servicios(CFG, mongo=fuentes["mongodb"], neo4j=fuentes["neo4j"], cassandra=fuentes["cassandra"],
                    redis=fuentes["redis"], influx=fuentes["influxdb"], iris=fuentes["iris"])
    return TestClient(crear_app(srv)), fuentes


def test_exito_con_traza_y_request_id(entorno):
    cliente, fuentes = entorno
    r = cliente.get("/api/v1/equipos/EQ-001", headers={"X-Request-ID": "prueba-unitaria-01"})
    assert r.status_code == 200
    assert r.headers["X-Request-ID"] == "prueba-unitaria-01"
    cuerpo = r.json()
    assert cuerpo["data"]["equipoId"] == "EQ-001" and cuerpo["meta"]["cache"] == "MISS"
    assert [t["fuente"] for t in cuerpo["meta"]["fuentes"]] == ["redis", "mongodb", "redis"]
    assert cliente.get("/api/v1/equipos/EQ-001").json()["meta"]["cache"] == "HIT"


def test_entrada_invalida_no_consulta_la_fuente(entorno):
    cliente, fuentes = entorno
    r = cliente.get("/api/v1/equipos/equipo-1")
    assert r.status_code == 400
    assert r.json()["error"]["codigo"] == "VALIDACION_FALLIDA"
    assert fuentes["mongodb"].llamadas == 0 and fuentes["redis"].llamadas == 0


def test_ventana_de_comentarios_mayor_a_5_minutos_se_rechaza_antes_de_cassandra(entorno):
    cliente, fuentes = entorno
    r = cliente.get("/api/v1/partidos/PAR-001/comentarios",
                    params={"desde": "2030-06-10T18:00:00Z", "hasta": "2030-06-10T18:10:00Z"})
    assert r.status_code == 400 and fuentes["cassandra"].llamadas == 0


def test_recurso_inexistente(entorno):
    cliente, _ = entorno
    r = cliente.get("/api/v1/equipos/EQ-999")
    assert r.status_code == 404 and r.json()["error"]["codigo"] == "RECURSO_NO_ENCONTRADO"


def test_sesion_ausente(entorno):
    cliente, _ = entorno
    r = cliente.get("/api/v1/sesiones/SES-" + "0" * 24)
    assert r.status_code == 404 and r.json()["error"]["codigo"] == "SESION_NO_VIGENTE"


def test_dependencia_caida_devuelve_503_sin_detalle_tecnico(entorno):
    cliente, fuentes = entorno
    fuentes["iris"].caido = True
    r = cliente.get("/api/v1/actas/PAR-001")
    assert r.status_code == 503
    error = r.json()["error"]
    assert error["codigo"] == "DEPENDENCIA_NO_DISPONIBLE" and error["dependencia"] == "iris"
    assert "Caido" not in error["mensaje"]


def test_redis_caido_degrada_la_ficha_a_mongodb(entorno):
    cliente, fuentes = entorno
    fuentes["redis"].caido = True
    r = cliente.get("/api/v1/equipos/EQ-001")
    assert r.status_code == 200 and r.json()["meta"]["cache"] == "BYPASS" and r.headers["X-Cache"] == "BYPASS"


def test_salud_informa_fuente_caida_con_503(entorno):
    cliente, fuentes = entorno
    fuentes["cassandra"].caido = True
    r = cliente.get("/api/v1/salud")
    assert r.status_code == 503
    estados = {d["fuente"]: d["estado"] for d in r.json()["error"]["detalles"]}
    assert estados["cassandra"] == "no_disponible" and estados["mongodb"] == "ok"


def test_escritura_repetida_no_duplica(entorno):
    cliente, fuentes = entorno
    cuerpo, h = {"usuarioId": "USR-00001", "contenido": "Hola"}, {"Idempotency-Key": "clave-unitaria-001"}
    r1 = cliente.post("/api/v1/partidos/PAR-001/comentarios", json=cuerpo, headers=h)
    r2 = cliente.post("/api/v1/partidos/PAR-001/comentarios", json=cuerpo, headers=h)
    assert (r1.status_code, r2.status_code) == (201, 200)
    assert r2.headers["Idempotent-Replayed"] == "true"
    assert r1.json()["data"]["comentarioId"] == r2.json()["data"]["comentarioId"]
    assert len(fuentes["cassandra"].kv["filas"]) == 1
    r3 = cliente.post("/api/v1/partidos/PAR-001/comentarios", json={**cuerpo, "contenido": "Otro"}, headers=h)
    assert r3.status_code == 409


def test_comentario_sin_idempotency_key_es_invalido(entorno):
    cliente, fuentes = entorno
    r = cliente.post("/api/v1/partidos/PAR-001/comentarios", json={"usuarioId": "USR-00001", "contenido": "x"})
    assert r.status_code == 400 and fuentes["redis"].llamadas == 0


def test_comentario_para_partido_inexistente_libera_la_clave(entorno):
    cliente, fuentes = entorno
    r = cliente.post("/api/v1/partidos/PAR-999/comentarios", json={"usuarioId": "USR-00001", "contenido": "x"},
                     headers={"Idempotency-Key": "clave-unitaria-002"})
    assert r.status_code == 404 and "comentario:PAR-999:clave-unitaria-002" not in fuentes["redis"].kv


def test_transicion_invalida_es_conflicto(entorno):
    cliente, _ = entorno
    r = cliente.put("/api/v1/actas/PAR-001/estado", json={"estado": "FINALIZADO"})
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "TRANSICION_INVALIDA"
    r = cliente.put("/api/v1/actas/PAR-001/estado", json={"estado": "PENDIENTE"})
    assert r.status_code == 200 and r.json()["data"]["cambio"] is False


def test_ruta_inexistente_usa_formato_de_error(entorno):
    cliente, _ = entorno
    r = cliente.get("/api/v1/no-existe")
    assert r.status_code == 404 and r.json()["error"]["codigo"] == "RUTA_NO_ENCONTRADA"


def test_driver_real_de_redis_sin_servicio_responde_error_acotado():
    from app.adapters.redis_kv import RedisKV
    import time
    redis_caido = RedisKV(replace(CFG, redis_port=1, timeout=1))
    srv = Servicios(CFG, mongo=None, neo4j=None, cassandra=None, redis=redis_caido, influx=None, iris=None)
    inicio = time.perf_counter()
    r = TestClient(crear_app(srv)).get("/api/v1/sesiones/SES-" + "0" * 24)
    assert r.status_code in (503, 504) and r.json()["error"]["dependencia"] == "redis"
    assert r.json()["error"]["codigo"] == {
        503: "DEPENDENCIA_NO_DISPONIBLE", 504: "DEPENDENCIA_TIMEOUT"}[r.status_code]
    assert time.perf_counter() - inicio < 5


def test_minutos_de_ventana():
    from datetime import datetime, timezone
    d = datetime(2030, 6, 10, 18, 0, 30, tzinfo=timezone.utc)
    h = datetime(2030, 6, 10, 18, 2, 10, tzinfo=timezone.utc)
    assert [m.minute for m in minutos_de_ventana(d, h)] == [0, 1, 2]
    assert len(minutos_de_ventana(d.replace(second=0), d.replace(minute=3, second=0))) == 3  # hasta exclusivo


def test_openapi_versionado_coincide_con_la_aplicacion(entorno):
    cliente, _ = entorno
    publicado = yaml.safe_load((config.RAIZ / "openapi" / "openapi.yaml").read_text(encoding="utf-8"))
    assert publicado == cliente.get("/openapi.json").json(), "Regenerar con scripts/exportar_openapi.py"
    respuestas = publicado["paths"]["/api/v1/equipos/{equipoId}"]["get"]["responses"]
    assert {"200", "400", "404", "500", "503", "504"} <= set(respuestas) and "422" not in respuestas


@pytest.mark.parametrize("tipo,estado,codigo", [
    ("TimeoutError", 504, "DEPENDENCIA_TIMEOUT"),
    ("ConnectionError", 503, "DEPENDENCIA_NO_DISPONIBLE"),
    ("AuthenticationError", 503, "DEPENDENCIA_NO_DISPONIBLE"),
    ("defecto", 500, "ERROR_INTERNO"),
])
def test_fallas_identificables_y_error_interno_seguros(entorno, monkeypatch, caplog, tipo, estado, codigo):
    """Excepciones inyectadas. No son cortes reales de Redis."""
    from redis import exceptions
    cliente, fuentes = entorno
    secreto = "valor-privado-no-publicable"
    error = ValueError(secreto) if tipo == "defecto" else getattr(exceptions, tipo)(secreto)

    def fallar(_):
        with operacion("redis", "obtener_sesion", (exceptions.RedisError,)):
            raise error

    monkeypatch.setattr(fuentes["redis"], "obtener_sesion", fallar)
    r = cliente.get("/api/v1/sesiones/SES-" + "0" * 24, headers={"X-Request-ID": "h11-error-unitario"})
    assert r.status_code == estado and r.json()["error"]["codigo"] == codigo
    assert r.headers["X-Request-ID"] == "h11-error-unitario"
    assert secreto not in r.text and secreto not in caplog.text


def test_timeout_conserva_degradacion_de_cache_y_salud(entorno, monkeypatch):
    from app.errors import DependenciaTimeout
    cliente, fuentes = entorno

    def fallar(*_):
        raise DependenciaTimeout("Tiempo agotado", dependencia="redis")

    monkeypatch.setattr(fuentes["redis"], "leer_equipo", fallar)
    monkeypatch.setattr(fuentes["redis"], "ping", fallar)
    r = cliente.get("/api/v1/equipos/EQ-001")
    assert r.status_code == 200 and r.headers["X-Cache"] == "BYPASS"
    assert cliente.get("/api/v1/salud").status_code == 503


def test_timeout_no_se_deduce_de_cualquier_error_del_driver():
    from app.contexto import es_timeout
    from pymongo.errors import OperationFailure, ServerSelectionTimeoutError
    from cassandra import OperationTimedOut
    from cassandra.cluster import NoHostAvailable
    import httpx
    assert es_timeout(ServerSelectionTimeoutError("seleccion agotada"))
    assert es_timeout(httpx.ReadTimeout("lectura agotada"))
    assert not es_timeout(OperationFailure("credenciales rechazadas", code=18))
    assert es_timeout(NoHostAvailable("sin hosts", {"nodo": OperationTimedOut()}))
    assert not es_timeout(NoHostAvailable("causas diferentes", {
        "uno": OperationTimedOut(), "otro": ConnectionRefusedError()}))
    assert not es_timeout(RuntimeError("error IRIS sin causa tipada"))
