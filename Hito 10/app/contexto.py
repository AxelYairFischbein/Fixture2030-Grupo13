"""Estado por request: identificador de correlación y trazas de las fuentes consultadas."""

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar

from app.errors import ApiError, DependenciaNoDisponible, DependenciaTimeout

log = logging.getLogger("fixture2030")

request_id: ContextVar[str] = ContextVar("request_id", default="-")
trazas: ContextVar[list | None] = ContextVar("trazas", default=None)


def es_timeout(error: BaseException) -> bool:
    """Reconoce señales explícitas del driver, sin deducir la causa por su mensaje."""
    if isinstance(error, TimeoutError):
        return True
    modulo = type(error).__module__.split(".")[0]
    if modulo == "pymongo":
        return getattr(error, "timeout", False) is True
    if modulo == "httpx":
        from httpx import TimeoutException
        return isinstance(error, TimeoutException)
    if modulo == "redis":
        from redis.exceptions import TimeoutError as RedisTimeout
        return isinstance(error, RedisTimeout)
    if modulo == "cassandra":
        from cassandra import OperationTimedOut, ReadTimeout, WriteTimeout
        from cassandra.cluster import NoHostAvailable
        if isinstance(error, NoHostAvailable):
            causas = list(error.errors.values())
            return bool(causas) and all(es_timeout(causa) for causa in causas)
        return isinstance(error, (OperationTimedOut, ReadTimeout, WriteTimeout))
    if modulo == "neo4j":
        codigo = getattr(error, "code", "") or ""
        if codigo.rsplit(".", 1)[-1] in {"TransactionTimedOut", "TransactionTimedOutClientConfiguration"}:
            return True
        causa = error.__cause__
        return isinstance(causa, TimeoutError)
    # Un RuntimeError de IRIS no identifica por sí solo un timeout.
    return False


@contextmanager
def operacion(dependencia: str, nombre: str, errores_driver: tuple[type[BaseException], ...]):
    """Mide, registra y traduce una operación de un adaptador.

    Un timeout identificable produce 504. Otras fallas del driver producen 503.
    Solo se registra el tipo de excepción: nunca mensajes que puedan incluir URIs o credenciales.
    """
    inicio = time.perf_counter()
    resultado = "ok"
    try:
        yield
    except ApiError as error:
        resultado = error.codigo.lower()
        raise
    except errores_driver as error:
        if es_timeout(error):
            resultado = "timeout:" + type(error).__name__
            raise DependenciaTimeout(
                f"La fuente {dependencia} excedió el tiempo de espera.", dependencia=dependencia
            ) from None
        resultado = "no_disponible:" + type(error).__name__
        raise DependenciaNoDisponible(f"No se pudo utilizar la fuente {dependencia}.",
                                     dependencia=dependencia) from None
    except Exception as error:
        resultado = "inesperado:" + type(error).__name__
        raise
    finally:
        ms = round((time.perf_counter() - inicio) * 1000, 2)
        log.info("req=%s dep=%s op=%s resultado=%s ms=%s", request_id.get(), dependencia, nombre, resultado, ms)
        lista = trazas.get()
        if lista is not None:
            lista.append({"fuente": dependencia, "operacion": nombre, "resultado": resultado, "ms": ms})
