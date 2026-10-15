"""Schema del formato de error único (casos_de_uso.md §6.1)."""

from pydantic import BaseModel, Field


class ErrorDetalle(BaseModel):
    campo: str = Field(examples=["partidoId"])
    problema: str = Field(examples=["PAR-999 no existe"])


class ErrorCuerpo(BaseModel):
    codigo: str = Field(examples=["PARTIDO_NO_ENCONTRADO"])
    mensaje: str = Field(examples=["No existe un partido con el identificador indicado."])
    requestId: str = Field(examples=["8f0c2a1e-6b3d-4f7a-9d55-2a1b7c9e4d10"])
    detalles: list[ErrorDetalle] = Field(default_factory=list)


class RespuestaError(BaseModel):
    error: ErrorCuerpo


DESCRIPCIONES_ERROR = {
    400: "VALIDACION: parámetro ausente, con formato inválido o fuera de rango.",
    401: "SESION_REQUERIDA (falta X-Session-Id) o SESION_NO_VIGENTE (ausente, vencida o inactiva).",
    403: "ROL_NO_AUTORIZADO: la sesión vigente no tiene el rol necesario.",
    404: "El recurso principal no existe.",
    503: "DEPENDENCIA_NO_DISPONIBLE: la fuente de datos no está disponible.",
    504: "DEPENDENCIA_TIMEOUT: la fuente de datos no respondió a tiempo.",
}


def respuestas_error(*codigos: int) -> dict[int, dict]:
    """Bloque responses= de una ruta con los errores que puede devolver (formato §6.1)."""
    return {c: {"model": RespuestaError, "description": DESCRIPCIONES_ERROR[c]} for c in codigos}