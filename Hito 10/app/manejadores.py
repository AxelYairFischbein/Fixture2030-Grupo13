"""Manejadores globales: toda falla sale con el formato de casos_de_uso.md §6.1."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config.logging import request_id_actual
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio
from app.middleware import ENCABEZADO, normalizar_request_id
from app.schemas.errores import ErrorCuerpo, ErrorDetalle, RespuestaError

logger = logging.getLogger("app.errores")

# Problema en español según el tipo de error de Pydantic. No se repite el valor recibido.
PROBLEMAS_VALIDACION = {
    "missing": "es obligatorio",
    "string_pattern_mismatch": "no cumple el formato {pattern}",
    "string_too_short": "debe tener al menos {min_length} caracteres",
    "string_too_long": "debe tener como máximo {max_length} caracteres",
    "enum": "debe ser uno de: {expected}",
    "literal_error": "debe ser uno de: {expected}",
    "int_parsing": "debe ser un número entero",
    "int_type": "debe ser un número entero",
    "float_parsing": "debe ser un número",
    "bool_parsing": "debe ser true o false",
    "greater_than": "debe ser mayor que {gt}",
    "greater_than_equal": "debe ser mayor o igual que {ge}",
    "less_than": "debe ser menor que {lt}",
    "less_than_equal": "debe ser menor o igual que {le}",
    "datetime_parsing": "debe ser una fecha ISO-8601",
    "datetime_from_date_parsing": "debe ser una fecha ISO-8601",
    "timezone_aware": "debe incluir zona horaria (UTC)",
    "extra_forbidden": "campo no permitido",
    "json_invalid": "el cuerpo no es un JSON válido",
    "model_attributes_type": "debe ser un objeto JSON",
    "dict_type": "debe ser un objeto JSON",
}

CODIGOS_HTTP = {
    404: ("RUTA_NO_ENCONTRADA", "La ruta solicitada no existe."),
    405: ("METODO_NO_PERMITIDO", "La ruta no admite el método HTTP utilizado."),
}


def _request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    return request_id or normalizar_request_id(None)


def respuesta_error(
    request: Request,
    http_status: int,
    codigo: str,
    mensaje: str,
    detalles: list[dict[str, str]] | None = None,
    encabezados: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    cuerpo = RespuestaError(
        error=ErrorCuerpo(
            codigo=codigo,
            mensaje=mensaje,
            requestId=request_id,
            detalles=[ErrorDetalle(**d) for d in detalles or []],
        )
    )
    return JSONResponse(
        status_code=http_status,
        content=cuerpo.model_dump(),
        headers={**(encabezados or {}), ENCABEZADO: request_id},
    )


def _detalle_validacion(error: dict) -> dict[str, str]:
    loc = [str(parte) for parte in error.get("loc", ()) if parte not in ("path", "query", "header", "body", "cookie")]
    campo = loc[-1] if loc else "body"
    plantilla = PROBLEMAS_VALIDACION.get(error.get("type", ""))
    if plantilla is None:
        return {"campo": campo, "problema": "valor inválido"}
    try:
        problema = plantilla.format(**(error.get("ctx") or {}))
    except (KeyError, IndexError):
        problema = "valor inválido"
    return {"campo": campo, "problema": problema}


async def _manejar_dominio(request: Request, exc: ErrorDominio) -> JSONResponse:
    if isinstance(exc, (DependenciaNoDisponible, DependenciaTimeout)):
        logger.warning("dependencia=%s resultado=%s", exc.dependencia, exc.codigo)
    return respuesta_error(request, exc.http_status, exc.codigo, exc.mensaje, exc.detalles)


async def _manejar_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    detalles = [_detalle_validacion(e) for e in exc.errors()]
    return respuesta_error(
        request, 400, "VALIDACION", "La solicitud tiene datos inválidos.", detalles
    )


async def _manejar_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Fuera de 404/405 solo se usan códigos ya definidos en §6.2.
    codigo, mensaje = CODIGOS_HTTP.get(
        exc.status_code, ("ERROR_INTERNO" if exc.status_code >= 500 else "VALIDACION",
                          "No se pudo procesar la solicitud.")
    )
    return respuesta_error(request, exc.status_code, codigo, mensaje, encabezados=exc.headers)


async def _manejar_inesperado(request: Request, exc: Exception) -> JSONResponse:
    # Starlette invoca este manejador fuera del middleware: se restablece el request id
    # para que el stack trace del log quede asociado a la request.
    token = request_id_actual.set(_request_id(request))
    try:
        logger.exception("error no previsto en %s %s", request.method, request.url.path)
    finally:
        request_id_actual.reset(token)
    return respuesta_error(request, 500, "ERROR_INTERNO", "Ocurrió un error inesperado.")


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(ErrorDominio, _manejar_dominio)
    app.add_exception_handler(RequestValidationError, _manejar_validacion)
    app.add_exception_handler(StarletteHTTPException, _manejar_http)
    app.add_exception_handler(Exception, _manejar_inesperado)
