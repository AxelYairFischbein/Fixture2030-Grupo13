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