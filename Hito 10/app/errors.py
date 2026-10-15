"""Excepciones de dominio de la API.

Los servicios y adaptadores lanzan estas excepciones; el manejador global
(app.manejadores) las convierte al formato de error único de
casos_de_uso.md §6.1 con el código HTTP de §6.2. El mensaje es público: no
lleva URIs, credenciales, consultas ni texto crudo del driver (eso va al log).
"""


class ErrorDominio(Exception):
    codigo: str = "ERROR_INTERNO"
    http_status: int = 500
    mensaje_por_defecto: str = "Ocurrió un error inesperado."

    def __init__(
        self,
        mensaje: str | None = None,
        detalles: list[dict[str, str]] | None = None,
        codigo: str | None = None,
    ) -> None:
        self.mensaje = mensaje or self.mensaje_por_defecto
        self.detalles = detalles or []
        if codigo is not None:
            self.codigo = codigo
        super().__init__(self.mensaje)


class ValidacionInvalida(ErrorDominio):
    """Entrada inválida detectada por una regla que Pydantic no cubre (p. ej. desde >= hasta)."""

    codigo = "VALIDACION"
    http_status = 400
    mensaje_por_defecto = "La solicitud tiene datos inválidos."


class SesionRequerida(ErrorDominio):
    codigo = "SESION_REQUERIDA"
    http_status = 401
    mensaje_por_defecto = "La operación requiere el encabezado X-Session-Id."


class SesionNoVigente(ErrorDominio):
    codigo = "SESION_NO_VIGENTE"
    http_status = 401
    mensaje_por_defecto = "La sesión no existe, venció o no está activa."


class RolNoAutorizado(ErrorDominio):
    codigo = "ROL_NO_AUTORIZADO"
    http_status = 403
    mensaje_por_defecto = "La sesión no tiene el rol necesario para esta operación."


class NoEncontrado(ErrorDominio):
    """Recurso principal inexistente. El código es específico: EQUIPO_NO_ENCONTRADO, etc."""

    codigo = "NO_ENCONTRADO"
    http_status = 404
    mensaje_por_defecto = "No existe el recurso indicado."

    def __init__(self, codigo: str, mensaje: str | None = None,
                 detalles: list[dict[str, str]] | None = None) -> None:
        super().__init__(mensaje, detalles, codigo)


class Conflicto(ErrorDominio):
    """Regla de negocio violada: TRANSICION_NO_PERMITIDA, IDEMPOTENCY_KEY_REUTILIZADA."""

    codigo = "CONFLICTO"
    http_status = 409
    mensaje_por_defecto = "La operación entra en conflicto con el estado actual."

    def __init__(self, codigo: str, mensaje: str | None = None,
                 detalles: list[dict[str, str]] | None = None) -> None:
        super().__init__(mensaje, detalles, codigo)


class DependenciaNoDisponible(ErrorDominio):
    codigo = "DEPENDENCIA_NO_DISPONIBLE"
    http_status = 503
    mensaje_por_defecto = "Una fuente de datos necesaria no está disponible."

    def __init__(self, dependencia: str, mensaje: str | None = None) -> None:
        self.dependencia = dependencia
        super().__init__(mensaje)


class DependenciaTimeout(ErrorDominio):
    codigo = "DEPENDENCIA_TIMEOUT"
    http_status = 504
    mensaje_por_defecto = "Una fuente de datos no respondió a tiempo."

    def __init__(self, dependencia: str, mensaje: str | None = None) -> None:
        self.dependencia = dependencia
        super().__init__(mensaje)