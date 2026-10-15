"""Casos de uso de sesiones (CU-11, CU-12, CU-13) y la dependencia sesion_requerida.

Regla de validez del Hito 7: la clave existe, estado=activa y TTL > 0. Redis no
distingue "vencida" de "nunca existió": ambos casos son 401 SESION_NO_VIGENTE.
Si Redis no responde, la falla se propaga como 503/504 y nunca como 401, porque
una dependencia caída no significa que la sesión sea inválida.
"""

from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import Depends, Header

from app.dependencias import obtener_adaptador_redis
from app.errors import RolNoAutorizado, SesionNoVigente, SesionRequerida
from app.schemas.sesiones import PATRON_SESION, ActividadRegistrada, SesionVigente

ESTADO_ACTIVA = "activa"


class RepositorioSesiones(Protocol):
    def leer_sesion(self, sesion_id: str) -> dict | None: ...
    def renovar_sesion(self, sesion_id: str, rol_requerido: str | None = None) -> dict: ...
    def cerrar_sesion(self, sesion_id: str) -> None: ...


@dataclass(frozen=True)
class Sesion:
    """Sesión validada y renovada por una operación protegida."""

    usuario_id: str
    rol: str
    expira_en_segundos: int


# El encabezado se valida junto con path, query y body (400 sin consultar Redis).
# Su ausencia no es un 400 sino 401 SESION_REQUERIDA, y se informa recién al usarlo.
EncabezadoSesion = Annotated[
    str | None,
    Header(
        alias="X-Session-Id",
        pattern=PATRON_SESION,
        description="Identificador de sesión (Hito 7). Es una credencial: no se registra en logs.",
    ),
]


def _requerir(sesion_id: str | None) -> str:
    if sesion_id is None:
        raise SesionRequerida()
    return sesion_id


class ServicioSesiones:
    def __init__(self, repositorio: RepositorioSesiones) -> None:
        self._repo = repositorio

    def consultar(self, sesion_id: str | None) -> SesionVigente:
        """CU-11. Lectura sin renovar: una inspección no es actividad."""
        sesion = self._repo.leer_sesion(_requerir(sesion_id))
        # TTL -2 (ausente) y -1 (sin vencimiento) no se aceptan como sesión válida.
        if sesion is None or sesion["ttl"] <= 0 or sesion.get("estado") != ESTADO_ACTIVA:
            raise SesionNoVigente()
        return SesionVigente(
            usuarioId=sesion.get("usuario_id", ""), rol=sesion.get("rol", ""),
            estado=sesion["estado"], expiraEnSegundos=sesion["ttl"],
        )

    def autorizar(self, sesion_id: str | None, rol: str | None = None) -> Sesion:
        """Valida, comprueba el rol y renueva en un único script Lua (CU-12)."""
        resultado = self._repo.renovar_sesion(_requerir(sesion_id), rol)
        if resultado["resultado"] == "no_vigente":
            raise SesionNoVigente()
        if resultado["resultado"] == "rol_no_autorizado":
            raise RolNoAutorizado(detalles=[{"campo": "X-Session-Id", "problema": f"requiere rol {rol}"}])
        return Sesion(resultado["usuario_id"], resultado["rol"], resultado["ttl"])

    def registrar_actividad(self, sesion_id: str | None) -> ActividadRegistrada:
        """CU-12. No recrea una sesión ausente; ante timeout no informa un TTL nuevo (504)."""
        return ActividadRegistrada(expiraEnSegundos=self.autorizar(sesion_id).expira_en_segundos)

    def cerrar(self, sesion_id: str | None) -> None:
        """CU-13. Idempotente: cerrar una sesión ausente también termina en 204."""
        self._repo.cerrar_sesion(_requerir(sesion_id))


class Autorizacion:
    """Autorización diferida que devuelve sesion_requerida.

    FastAPI resuelve las dependencias antes de validar path, query y body. Por eso
    la dependencia solo toma el encabezado y Redis se consulta recién en exigir(),
    que la ruta llama en su primera línea: una entrada inválida devuelve 400 sin
    tocar Redis y un intento rechazado no renueva la sesión (Hito 7).
    """

    def __init__(self, servicio: ServicioSesiones, sesion_id: str | None, rol: str | None) -> None:
        self._servicio = servicio
        self._sesion_id = sesion_id
        self._rol = rol

    def exigir(self) -> Sesion:
        """401 SESION_REQUERIDA / SESION_NO_VIGENTE, 403 ROL_NO_AUTORIZADO o 503/504.

        Si la sesión es válida cuenta como actividad: renueva el TTL a 1800 s.
        """
        return self._servicio.autorizar(self._sesion_id, self._rol)


def obtener_servicio_sesiones(
    repositorio: Annotated[RepositorioSesiones, Depends(obtener_adaptador_redis)],
) -> ServicioSesiones:
    return ServicioSesiones(repositorio)


def sesion_requerida(rol: str | None = None):
    """Dependencia reutilizable para operaciones protegidas (CU-09, CU-10, CU-14, CU-19, CU-20).

    Uso: `auth: Annotated[Autorizacion, Depends(sesion_requerida("operador"))]` y,
    como primera línea de la ruta, `sesion = auth.exigir()`. Con rol=None alcanza
    cualquier sesión vigente.
    """

    def dependencia(
        servicio: Annotated[ServicioSesiones, Depends(obtener_servicio_sesiones)],
        sesion_id: EncabezadoSesion = None,
    ) -> Autorizacion:
        return Autorizacion(servicio, sesion_id, rol)

    return dependencia
