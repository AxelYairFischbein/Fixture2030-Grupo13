"""Errores de la aplicación y su traducción a un formato HTTP único."""


class ApiError(Exception):
    estado = 500
    codigo = "ERROR_INTERNO"

    def __init__(self, mensaje: str, *, detalles: list | None = None, dependencia: str | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles
        self.dependencia = dependencia


class ValidacionFallida(ApiError):
    estado = 400
    codigo = "VALIDACION_FALLIDA"


class NoEncontrado(ApiError):
    estado = 404
    codigo = "RECURSO_NO_ENCONTRADO"


class SesionNoVigente(ApiError):
    estado = 404
    codigo = "SESION_NO_VIGENTE"


class Conflicto(ApiError):
    estado = 409
    codigo = "CONFLICTO"


class TransicionInvalida(Conflicto):
    codigo = "TRANSICION_INVALIDA"


class DependenciaNoDisponible(ApiError):
    estado = 503
    codigo = "DEPENDENCIA_NO_DISPONIBLE"


class DependenciaTimeout(DependenciaNoDisponible):
    estado = 504
    codigo = "DEPENDENCIA_TIMEOUT"


def cuerpo_error(codigo: str, mensaje: str, request_id: str, *, detalles=None, dependencia=None) -> dict:
    error = {"codigo": codigo, "mensaje": mensaje, "requestId": request_id}
    if dependencia:
        error["dependencia"] = dependencia
    if detalles:
        error["detalles"] = detalles
    return {"error": error}
