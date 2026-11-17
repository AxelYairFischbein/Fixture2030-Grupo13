"""Errores reales del driver simulados sin saturar el Redis compartido."""

from types import SimpleNamespace

from fastapi.testclient import TestClient
from redis.exceptions import OutOfMemoryError

from app.adapters.redis_kv import RedisKV
from app.config import cargar
from app.main import crear_app
from app.services import Servicios


def sin_memoria(*args, **kwargs):
    raise OutOfMemoryError("Escritura rechazada")


def entorno():
    cfg = cargar()
    redis = RedisKV(cfg)
    redis._crear = sin_memoria
    redis._r = SimpleNamespace(get=lambda *a: None, set=sin_memoria)
    equipo = {"equipoId": "EQ-001", "codigo": "F01", "nombre": "Seleccion Sintetica 01",
              "confederacion": "AFC", "rankingReferencia": 1, "estado": "PRESELECCIONADO",
              "region": "ASIA_PACIFICO", "sedeBase": {"ciudad": "C", "pais": "P"},
              "participacionesMundiales": 1, "titulosMundiales": 0, "actualizadoEn": "2026-09-02T00:00:00Z"}
    mongo = SimpleNamespace(buscar_equipo=lambda _: equipo)
    return TestClient(crear_app(Servicios(cfg, mongo=mongo, neo4j=None, cassandra=None,
                                         redis=redis, influx=None, iris=None)))


def test_noeviction_rechaza_sesion_con_error_tipado():
    r = entorno().post("/api/v1/sesiones", json={"usuarioId": "USR-00001"})
    assert r.status_code == 503
    assert r.json()["error"]["codigo"] == "DEPENDENCIA_NO_DISPONIBLE"
    assert r.json()["error"]["dependencia"] == "redis"


def test_noeviction_cache_fallida_conserva_lectura_mongo():
    r = entorno().get("/api/v1/equipos/EQ-001")
    assert r.status_code == 200 and r.headers["X-Cache"] == "BYPASS"
    assert r.json()["data"]["equipoId"] == "EQ-001"
