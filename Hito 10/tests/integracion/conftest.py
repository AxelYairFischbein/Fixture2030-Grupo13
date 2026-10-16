"""Fixtures comunes de las pruebas de integración contra los contenedores.

Settings se arma desde Hito 10/.env de forma explícita: el conftest raíz reemplaza
las variables de entorno por valores ficticios para las pruebas unitarias.

Las sesiones de prueba se crean con IDs aleatorios y la misma estructura y EVAL que
Hito 7/scripts/carga_muestra.redis, y se borran al terminar. Los IDs no se imprimen.
"""

import secrets

import pytest
from dotenv import dotenv_values
from redis import Redis

from app.config.settings import RAIZ_HITO10, Settings

# Creación atómica de la sesión con TIME del servidor (Hito 7, carga_muestra.redis).
LUA_CREAR = (
    "local t=redis.call('TIME')[1]; "
    "redis.call('HSET',KEYS[1],'sesion_id',ARGV[1],'usuario_id',ARGV[2],"
    "'ultima_actividad',t,'estado','activa','rol',ARGV[3]); "
    "redis.call('EXPIRE',KEYS[1],ARGV[4]); return redis.call('TTL',KEYS[1])"
)


@pytest.fixture(scope="session")
def settings_reales() -> Settings:
    archivo = RAIZ_HITO10 / ".env"
    if not archivo.exists():
        pytest.skip("Falta Hito 10/.env con las credenciales locales")
    valores = {k.lower(): v for k, v in dotenv_values(archivo).items() if v}
    if "completar_localmente" in (valores.get("mongo_user"), valores.get("mongo_password")):
        pytest.skip("MONGO_USER / MONGO_PASSWORD de Hito 10/.env tienen el valor de relleno")
    return Settings(_env_file=None, **valores)


@pytest.fixture(scope="module")
def redis_directo(settings_reales):
    cliente = Redis(host=settings_reales.redis_host, port=settings_reales.redis_port,
                    db=settings_reales.redis_db, decode_responses=True, socket_timeout=2,
                    socket_connect_timeout=2)
    try:
        cliente.ping()
    except Exception:
        pytest.skip("Redis del Hito 7 no responde en el puerto configurado: "
                    'docker compose -f "Hito 7/docker-compose.yml" up -d')
    yield cliente
    cliente.close()


@pytest.fixture
def sesiones(settings_reales, redis_directo):
    """Fábrica de sesiones de prueba: devuelve (id, clave) y limpia al terminar."""
    creadas: list[str] = []

    def crear(rol: str = "lector", ttl: int = 1800, usuario_id: str = "USR-00001"):
        sesion_id = f"SES-PRUEBA-{secrets.token_hex(16)}"
        clave = f"{settings_reales.redis_prefijo}sesion:{sesion_id}"
        redis_directo.eval(LUA_CREAR, 1, clave, sesion_id, usuario_id, rol, ttl)
        creadas.append(clave)
        return sesion_id, clave

    yield crear
    if creadas:
        redis_directo.delete(*creadas)
