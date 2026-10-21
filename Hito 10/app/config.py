"""Configuración leída del entorno. Los secretos viven en .env, excluido de Git."""

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _cargar_env(ruta: Path = RAIZ / ".env") -> None:
    # Las variables ya definidas en el entorno tienen prioridad sobre el archivo.
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip())


def _texto(nombre: str, defecto: str = "") -> str:
    return os.environ.get(nombre, defecto).strip()


def _token_influx() -> str:
    if _texto("INFLUX_TOKEN"):
        return _texto("INFLUX_TOKEN")
    ruta = _texto("INFLUX_TOKEN_FILE")
    if ruta:
        archivo = Path(ruta) if Path(ruta).is_absolute() else RAIZ / ruta
        if archivo.exists():
            return archivo.read_text(encoding="utf-8").strip()
    return ""


@dataclass(frozen=True)
class Config:
    timeout: float
    mongo_host: str
    mongo_port: int
    mongo_db: str
    mongo_user: str
    mongo_password: str
    neo4j_uri: str
    neo4j_database: str
    neo4j_user: str
    neo4j_password: str
    cassandra_hosts: list[str]
    cassandra_port: int
    cassandra_keyspace: str
    redis_host: str
    redis_port: int
    redis_password: str
    redis_prefix: str
    sesion_ttl: int
    cache_equipo_ttl: int
    idempotencia_ttl: int
    influx_url: str
    influx_db: str
    influx_token: str
    iris_host: str
    iris_port: int
    iris_namespace: str
    iris_user: str
    iris_password: str


def cargar() -> Config:
    _cargar_env()
    return Config(
        timeout=float(_texto("DEP_TIMEOUT_SEGUNDOS", "3")),
        mongo_host=_texto("MONGO_HOST", "127.0.0.1"),
        mongo_port=int(_texto("MONGO_PORT", "27017")),
        mongo_db=_texto("MONGO_DB", "fixture2030"),
        mongo_user=_texto("MONGO_USER"),
        mongo_password=_texto("MONGO_PASSWORD"),
        neo4j_uri=_texto("NEO4J_URI", "bolt://127.0.0.1:7687"),
        neo4j_database=_texto("NEO4J_DATABASE", "neo4j"),
        neo4j_user=_texto("NEO4J_USER", "neo4j"),
        neo4j_password=_texto("NEO4J_PASSWORD"),
        cassandra_hosts=_texto("CASSANDRA_HOSTS", "127.0.0.1").split(","),
        cassandra_port=int(_texto("CASSANDRA_PORT", "9042")),
        cassandra_keyspace=_texto("CASSANDRA_KEYSPACE", "fixture2030_comentarios"),
        redis_host=_texto("REDIS_HOST", "127.0.0.1"),
        redis_port=int(_texto("REDIS_PORT", "16379")),
        redis_password=_texto("REDIS_PASSWORD"),
        redis_prefix=_texto("REDIS_PREFIX", "fixture2030:h10"),
        sesion_ttl=int(_texto("SESION_TTL_SEGUNDOS", "1800")),
        cache_equipo_ttl=int(_texto("CACHE_EQUIPO_TTL_SEGUNDOS", "300")),
        idempotencia_ttl=int(_texto("IDEMPOTENCIA_TTL_SEGUNDOS", "86400")),
        influx_url=_texto("INFLUX_URL", "http://127.0.0.1:8181"),
        influx_db=_texto("INFLUX_DB", "fixture2030_h8"),
        influx_token=_token_influx(),
        iris_host=_texto("IRIS_HOST", "127.0.0.1"),
        iris_port=int(_texto("IRIS_PORT", "1972")),
        iris_namespace=_texto("IRIS_NAMESPACE", "USER"),
        iris_user=_texto("IRIS_USER"),
        iris_password=_texto("IRIS_PASSWORD"),
    )
