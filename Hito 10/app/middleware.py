"""Middleware de X-Request-Id y log de acceso.

Es un middleware ASGI puro (no BaseHTTPMiddleware) para que el request id
quede en el ContextVar y en request.state también cuando la ruta falla.
El log de acceso registra método, ruta, estado y duración; nunca registra
encabezados (X-Session-Id es una credencial) ni la query string.
"""

import logging
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config.logging import request_id_actual

ENCABEZADO = "X-Request-Id"

logger = logging.getLogger("app.acceso")


def normalizar_request_id(valor: str | None) -> str:
    """Devuelve el request id del cliente si es un UUID válido; si no, uno nuevo."""
    if valor:
        try:
            return str(uuid.UUID(valor))
        except ValueError:
            pass
    return str(uuid.uuid4())


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = normalizar_request_id(Headers(scope=scope).get(ENCABEZADO))
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_actual.set(request_id)
        inicio = time.perf_counter()
        estado = 500

        async def enviar(mensaje: Message) -> None:
            nonlocal estado
            if mensaje["type"] == "http.response.start":
                estado = mensaje["status"]
                MutableHeaders(scope=mensaje)[ENCABEZADO] = request_id
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        finally:
            duracion_ms = (time.perf_counter() - inicio) * 1000
            logger.info(
                "metodo=%s ruta=%s estado=%s duracion_ms=%.1f",
                scope["method"], scope["path"], estado, duracion_ms,
            )
            request_id_actual.reset(token)
