"""Schemas de sesiones (CU-11, CU-12). Nunca incluyen el ID de sesión ni ultima_actividad."""

from pydantic import BaseModel, Field

PATRON_SESION = r"^[A-Za-z0-9-]{8,64}$"


class SesionVigente(BaseModel):
    """CU-11. Atributos públicos de una sesión válida (existe, estado activa y TTL > 0)."""

    usuarioId: str = Field(examples=["USR-00001"])
    rol: str = Field(examples=["lector"], description="lector, moderador u operador.")
    estado: str = Field(examples=["activa"])
    expiraEnSegundos: int = Field(examples=[1742])


class ActividadRegistrada(BaseModel):
    """CU-12. Nuevo vencimiento después de renovar el TTL."""

    expiraEnSegundos: int = Field(examples=[1800])
