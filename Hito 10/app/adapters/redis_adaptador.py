"""Adaptador de Redis (Hito 7): sesiones y ficha de equipo cacheada.

Respeta el modelo del Hito 7: claves `<prefijo>sesion:<id>` (Hash con sesion_id,
usuario_id, ultima_actividad, estado y rol) y `<prefijo>cache:equipo:<id>`
(String JSON con SET EX 300). El prefijo sale de la configuración. Una sesión
es válida solo si existe, tiene estado=activa y TTL > 0; la comprobación y la
renovación ocurren en un único script Lua. Traduce las excepciones de redis-py
a las de app.errors. Nada de redis-py sale de acá.

El ID de sesión es una credencial: no se registra en el log (ni la clave que lo
contiene).
"""

import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import AuthenticationError, ConnectionError, RedisError, TimeoutError
from redis.retry import Retry

from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio

DEPENDENCIA = "redis"

# Valores fijados por el contrato (casos_de_uso.md CU-01 y CU-12, Hito 7).
TTL_SESION_S = 1800
TTL_FICHA_S = 300

logger = logging.getLogger("app.adapters.redis")

# Script de actividad del Hito 7 (scripts/sesiones.redis) con la comprobación de rol.
# Devuelve 0 si la sesión no es válida (ausente, sin TTL o estado distinto de activa),
# -1 si no tiene el rol pedido (sin renovar: un intento rechazado no es actividad) y,
# si es válida, actualiza ultima_actividad con TIME del servidor, renueva el TTL y
# devuelve {usuario_id, rol, ttl}. Todo ocurre sin intercalación: un DEL concurrente
# sucede antes (y la renovación devuelve 0) o después (y elimina la sesión renovada).
LUA_RENOVAR = """
if redis.call('TTL', KEYS[1]) <= 0 or redis.call('HGET', KEYS[1], 'estado') ~= 'activa' then
  return 0
end
local rol = redis.call('HGET', KEYS[1], 'rol') or ''
if ARGV[1] ~= '' and rol ~= ARGV[1] then
  return -1
end
redis.call('HSET', KEYS[1], 'ultima_actividad', redis.call('TIME')[1])
redis.call('EXPIRE', KEYS[1], ARGV[2])
return {redis.call('HGET', KEYS[1], 'usuario_id') or '', rol, redis.call('TTL', KEYS[1])}
"""


def _es_timeout_de_conexion(exc: TimeoutError) -> bool:
    """redis-py usa la misma clase para el timeout de conexión y el de lectura; solo el
    mensaje los distingue ("Timeout connecting to server" en redis 8.1)."""
    return str(exc).startswith("Timeout connecting")


class AdaptadorRedis:
    def __init__(self, settings: Settings, cliente: Redis | None = None) -> None:
        # Sin reintentos automáticos: el timeout de §6.3 (0,5 s) es el límite real.
        # El cliente conecta al primer comando: la API arranca aunque Redis esté caído.
        self._cliente = cliente or Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password.get_secret_value() if settings.redis_password else None,
            socket_connect_timeout=settings.redis_connect_timeout_s,
            socket_timeout=settings.redis_socket_timeout_s,
            retry=Retry(NoBackoff(), 0),
            decode_responses=True,
            client_name="fixture2030-h10",
        )
        self._prefijo = settings.redis_prefijo
        self._renovar = self._cliente.register_script(LUA_RENOVAR)

    def cerrar(self) -> None:
        self._cliente.close()

    def _clave_sesion(self, sesion_id: str) -> str:
        return f"{self._prefijo}sesion:{sesion_id}"

    def _clave_ficha(self, equipo_id: str) -> str:
        return f"{self._prefijo}cache:equipo:{equipo_id}"

    @contextmanager
    def _traducir(self, operacion: str) -> Iterator[None]:
        """Traduce excepciones del driver y registra dependencia, resultado y duración."""
        inicio = time.perf_counter()
        resultado = "ok"
        try:
            yield
        except AuthenticationError as exc:
            # Hereda de ConnectionError, pero es configuración: 500 con el tipo solo en el log.
            resultado = f"ERROR_INTERNO tipo={type(exc).__name__}"
            raise ErrorDominio() from exc
        except TimeoutError as exc:
            if _es_timeout_de_conexion(exc):
                # No se llegó a conectar ni a enviar nada: la fuente no está disponible.
                # (En Windows un puerto cerrado no rechaza dentro de los 0,5 s: vence el connect.)
                resultado = "DEPENDENCIA_NO_DISPONIBLE"
                raise DependenciaNoDisponible(DEPENDENCIA) from exc
            resultado = "DEPENDENCIA_TIMEOUT"
            raise DependenciaTimeout(DEPENDENCIA) from exc
        except ConnectionError as exc:
            resultado = "DEPENDENCIA_NO_DISPONIBLE"
            raise DependenciaNoDisponible(DEPENDENCIA) from exc
        except RedisError as exc:
            resultado = f"ERROR_INTERNO tipo={type(exc).__name__}"
            raise ErrorDominio() from exc
        finally:
            duracion_ms = (time.perf_counter() - inicio) * 1000
            logger.info(
                "dependencia=%s operacion=%s resultado=%s duracion_ms=%.1f",
                DEPENDENCIA, operacion, resultado, duracion_ms,
            )

    # Sesiones (CU-11, CU-12, CU-13)

    def leer_sesion(self, sesion_id: str) -> dict | None:
        """HGETALL + TTL en un MULTI. Devuelve los campos más "ttl", o None si no existe.

        No renueva: una inspección no es actividad (Hito 7).
        """
        clave = self._clave_sesion(sesion_id)
        with self._traducir("leer_sesion"):
            with self._cliente.pipeline(transaction=True) as pipe:
                pipe.hgetall(clave)
                pipe.ttl(clave)
                campos, ttl = pipe.execute()
        if not campos:
            return None
        return {**campos, "ttl": int(ttl)}

    def renovar_sesion(self, sesion_id: str, rol_requerido: str | None = None) -> dict:
        """Valida y renueva la sesión en un único EVAL.

        Devuelve {"resultado": "ok", "usuario_id", "rol", "ttl"} o
        {"resultado": "no_vigente"} / {"resultado": "rol_no_autorizado"}.
        Nunca recrea una sesión ausente.
        """
        with self._traducir("renovar_sesion"):
            respuesta = self._renovar(
                keys=[self._clave_sesion(sesion_id)], args=[rol_requerido or "", TTL_SESION_S]
            )
        if respuesta == 0:
            return {"resultado": "no_vigente"}
        if respuesta == -1:
            return {"resultado": "rol_no_autorizado"}
        usuario_id, rol, ttl = respuesta
        return {"resultado": "ok", "usuario_id": usuario_id, "rol": rol, "ttl": int(ttl)}

    def cerrar_sesion(self, sesion_id: str) -> None:
        """DEL idempotente: cerrar una sesión ausente deja el mismo estado final."""
        with self._traducir("cerrar_sesion"):
            self._cliente.delete(self._clave_sesion(sesion_id))

    # Ficha de equipo cacheada (CU-01, CU-14)

    def leer_ficha_cacheada(self, equipo_id: str) -> dict | None:
        with self._traducir("leer_ficha_cacheada"):
            copia = self._cliente.get(self._clave_ficha(equipo_id))
        if copia is None:
            return None
        try:
            return json.loads(copia)
        except ValueError:
            # Una copia ilegible se trata como miss: la próxima escritura la reemplaza.
            logger.warning("dependencia=%s operacion=leer_ficha_cacheada resultado=copia_invalida",
                           DEPENDENCIA)
            return None

    def guardar_ficha_cacheada(self, equipo_id: str, ficha: dict) -> None:
        with self._traducir("guardar_ficha_cacheada"):
            self._cliente.set(
                self._clave_ficha(equipo_id), json.dumps(ficha, ensure_ascii=False), ex=TTL_FICHA_S
            )

    def invalidar_ficha_cacheada(self, equipo_id: str) -> None:
        with self._traducir("invalidar_ficha_cacheada"):
            self._cliente.delete(self._clave_ficha(equipo_id))

    def ping(self) -> bool:
        """Chequeo de salud: True si Redis responde. Nunca lanza."""
        try:
            with self._traducir("ping"):
                self._cliente.ping()
            return True
        except ErrorDominio:
            return False
