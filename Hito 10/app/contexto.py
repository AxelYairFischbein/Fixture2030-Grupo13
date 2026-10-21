"""Estado por request: identificador de correlación y trazas de las fuentes consultadas."""

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar

from app.errors import ApiError, DependenciaNoDisponible

log = logging.getLogger("fixture2030")

request_id: ContextVar[str] = ContextVar("request_id", default="-")
trazas: ContextVar[list | None] = ContextVar("trazas", default=None)


@contextmanager
def operacion(dependencia: str, nombre: str, errores_driver: tuple[type[BaseException], ...]):
    """Mide, registra y traduce una operación de un adaptador.

    Las excepciones propias del driver se convierten en DependenciaNoDisponible (503).
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
        resultado = "error:" + type(error).__name__
        raise DependenciaNoDisponible(
            f"La fuente {dependencia} no está disponible o no respondió a tiempo.", dependencia=dependencia
        ) from None
    except Exception as error:
        resultado = "inesperado:" + type(error).__name__
        raise
    finally:
        ms = round((time.perf_counter() - inicio) * 1000, 2)
        log.info("req=%s dep=%s op=%s resultado=%s ms=%s", request_id.get(), dependencia, nombre, resultado, ms)
        lista = trazas.get()
        if lista is not None:
            lista.append({"fuente": dependencia, "operacion": nombre, "resultado": resultado, "ms": ms})
