"""Adaptador clave/valor (Hito 7): sesiones, caché de fichas y claves de idempotencia en Redis."""

import json
import secrets

import redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from app.contexto import operacion

ERRORES = (RedisError, OSError)

# Igual que en el Hito 7: el hash y su vencimiento se crean como una unidad, con la hora del servidor.
LUA_CREAR_SESION = """
local t = redis.call('TIME')[1]
redis.call('HSET', KEYS[1], 'sesion_id', ARGV[1], 'usuario_id', ARGV[2], 'ultima_actividad', t,
            'estado', 'activa', 'rol', ARGV[3])
redis.call('EXPIRE', KEYS[1], ARGV[4])
return t
"""


class RedisKV:
    nombre = "redis"

    def __init__(self, cfg, *, sesion_ttl: int | None = None):
        # Sin reintentos internos: el cliente HTTP decide si reintenta; la espera queda acotada al timeout.
        self._r = redis.Redis(host=cfg.redis_host, port=cfg.redis_port, password=cfg.redis_password or None,
                              socket_timeout=cfg.timeout, socket_connect_timeout=cfg.timeout,
                              retry=Retry(NoBackoff(), 0), decode_responses=True)
        self._p = cfg.redis_prefix
        self.sesion_ttl = sesion_ttl or cfg.sesion_ttl
        self._crear = self._r.register_script(LUA_CREAR_SESION)

    def ping(self):
        with operacion(self.nombre, "ping", ERRORES):
            self._r.ping()

    # --- Sesiones -------------------------------------------------------------------
    def crear_sesion(self, usuario_id: str, rol: str) -> dict:
        sesion_id = "SES-" + secrets.token_hex(12)
        with operacion(self.nombre, "crear_sesion", ERRORES):
            instante = self._crear(keys=[f"{self._p}:sesion:{sesion_id}"],
                                   args=[sesion_id, usuario_id, rol, self.sesion_ttl])
        return {"sesionId": sesion_id, "usuarioId": usuario_id, "estado": "activa", "rol": rol,
                "ultimaActividad": int(instante), "expiraEnSegundos": self.sesion_ttl}

    def obtener_sesion(self, sesion_id: str) -> dict | None:
        clave = f"{self._p}:sesion:{sesion_id}"
        with operacion(self.nombre, "obtener_sesion", ERRORES):
            pipe = self._r.pipeline(transaction=True)
            datos, ttl = pipe.hgetall(clave).ttl(clave).execute()
        if not datos:
            return None  # Redis no distingue "nunca existió" de "venció": ambas son ausencia.
        return {"sesionId": datos.get("sesion_id"), "usuarioId": datos.get("usuario_id"),
                "estado": datos.get("estado"), "rol": datos.get("rol"),
                "ultimaActividad": int(datos.get("ultima_actividad", 0)), "expiraEnSegundos": ttl}

    def cerrar_sesion(self, sesion_id: str) -> bool:
        with operacion(self.nombre, "cerrar_sesion", ERRORES):
            return self._r.delete(f"{self._p}:sesion:{sesion_id}") == 1

    # --- Caché cache-aside de la ficha de equipo ------------------------------------------
    def leer_equipo(self, equipo_id: str) -> dict | None:
        with operacion(self.nombre, "leer_cache_equipo", ERRORES):
            valor = self._r.get(f"{self._p}:cache:equipo:{equipo_id}")
        return json.loads(valor) if valor else None

    def guardar_equipo(self, equipo_id: str, equipo: dict, ttl: int):
        with operacion(self.nombre, "guardar_cache_equipo", ERRORES):
            self._r.set(f"{self._p}:cache:equipo:{equipo_id}", json.dumps(equipo), ex=ttl)

    def invalidar_equipo(self, equipo_id: str) -> bool:
        with operacion(self.nombre, "invalidar_cache_equipo", ERRORES):
            return self._r.delete(f"{self._p}:cache:equipo:{equipo_id}") == 1

    # --- Idempotencia de escrituras ------------------------------------------------------
    def reservar_idempotencia(self, clave: str, huella: str, ttl: int) -> dict | None:
        """SET NX: devuelve None si la clave quedó reservada ahora, o el registro previo."""
        k = f"{self._p}:idem:{clave}"
        with operacion(self.nombre, "reservar_idempotencia", ERRORES):
            if self._r.set(k, json.dumps({"estado": "EN_CURSO", "huella": huella}), nx=True, ex=ttl):
                return None
            previo = self._r.get(k)
        return json.loads(previo) if previo else {"estado": "EN_CURSO", "huella": huella}

    def completar_idempotencia(self, clave: str, huella: str, resultado: dict, ttl: int):
        with operacion(self.nombre, "completar_idempotencia", ERRORES):
            self._r.set(f"{self._p}:idem:{clave}",
                        json.dumps({"estado": "COMPLETADO", "huella": huella, "resultado": resultado}), ex=ttl)

    def liberar_idempotencia(self, clave: str):
        with operacion(self.nombre, "liberar_idempotencia", ERRORES):
            self._r.delete(f"{self._p}:idem:{clave}")
