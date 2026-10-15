"""Logging de la API: cada línea incluye el request id de la request en curso.

El request id viaja en un ContextVar que fija el middleware; así lo ven el
router, el servicio y el adaptador sin pasarlo como parámetro (RF18).
"""

import logging
from contextvars import ContextVar

request_id_actual: ContextVar[str] = ContextVar("request_id_actual", default="-")

FORMATO = "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"


class FiltroRequestId(logging.Filter):
    """Agrega el atributo request_id a cada registro de log."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_actual.get()
        return True


def configurar_logging(nivel: str = "INFO") -> None:
    """Configura el logger "app" (idempotente: no duplica handlers)."""
    logger = logging.getLogger("app")
    logger.setLevel(nivel.upper())
    logger.propagate = False
    if not any(getattr(h, "_fixture2030", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(FORMATO))
        handler.addFilter(FiltroRequestId())
        handler._fixture2030 = True
        logger.addHandler(handler)
