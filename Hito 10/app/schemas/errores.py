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
    400: "Parámetro ausente, con formato inválido o fuera de rango; intervalo invertido o "
         "excedido; body con campos extra. Se responde antes de consultar.",
    401: "Falta X-Session-Id o la sesión no es vigente (ausente, vencida, sin TTL o inactiva).",
    403: "La sesión vigente no tiene el rol necesario.",
    404: "El recurso principal de la ruta no existe.",
    409: "Regla de negocio violada por el estado actual o por una clave ya usada.",
    500: "Error inesperado o de configuración; el detalle queda solo en logs.",
    503: "Una fuente de datos necesaria no está disponible.",
    504: "Una fuente de datos no respondió a tiempo; en escrituras, el resultado es incierto.",
}

REQUEST_ID_EJEMPLO = "8f0c2a1e-6b3d-4f7a-9d55-2a1b7c9e4d10"

# Ejemplos de error por nombre: (código §6.2, mensaje, detalles). El nombre coincide con el
# código salvo en las variantes de un mismo código (catálogo no cargado, resultado incierto).
EJEMPLOS_ERROR: dict[str, tuple[str, str, list[dict[str, str]]]] = {
    "VALIDACION": ("VALIDACION", "La solicitud tiene datos inválidos.",
                   [{"campo": "partidoId", "problema": "no cumple el formato ^PAR-\\d{3}$"}]),
    "SESION_REQUERIDA": ("SESION_REQUERIDA", "La operación requiere el encabezado X-Session-Id.", []),
    "SESION_NO_VIGENTE": ("SESION_NO_VIGENTE", "La sesión no existe, venció o no está activa.", []),
    "ROL_NO_AUTORIZADO": ("ROL_NO_AUTORIZADO",
                          "La sesión no tiene el rol necesario para esta operación.", []),
    "EQUIPO_NO_ENCONTRADO": ("EQUIPO_NO_ENCONTRADO",
                             "No existe un equipo con el identificador indicado.",
                             [{"campo": "equipoId", "problema": "EQ-999 no existe"}]),
    "JUGADOR_NO_ENCONTRADO": ("JUGADOR_NO_ENCONTRADO",
                              "No existe un jugador con el identificador indicado.",
                              [{"campo": "jugadorId", "problema": "JUG-9999 no existe"}]),
    "PARTIDO_NO_ENCONTRADO": ("PARTIDO_NO_ENCONTRADO",
                              "No existe un partido con el identificador indicado.",
                              [{"campo": "partidoId", "problema": "PAR-999 no existe"}]),
    "EQUIPO_NO_PARTICIPA": ("EQUIPO_NO_PARTICIPA", "El equipo indicado no disputa ese partido.",
                            [{"campo": "equipoId", "problema": "EQ-003 no disputa PAR-001"}]),
    "COMENTARIO_NO_ENCONTRADO": ("COMENTARIO_NO_ENCONTRADO",
                                 "No existe un comentario con esa clave en el partido indicado.",
                                 [{"campo": "comentarioId",
                                   "problema": "MUESTRA-004 no existe con ese creadoEn"}]),
    "ACTA_NO_ENCONTRADA": ("ACTA_NO_ENCONTRADA", "No existe un acta para el partido indicado.",
                           [{"campo": "partidoId", "problema": "PAR-002 no tiene acta"}]),
    "TRANSICION_NO_PERMITIDA": ("TRANSICION_NO_PERMITIDA",
                                "El estado actual del partido no admite la transición pedida.",
                                [{"campo": "nuevoEstado",
                                  "problema": "no se permite FINALIZADO -> EN_JUEGO; "
                                              "estado actual FINALIZADO"}]),
    "IDEMPOTENCY_KEY_REUTILIZADA": ("IDEMPOTENCY_KEY_REUTILIZADA",
                                    "La Idempotency-Key ya se usó con otro contenido.",
                                    [{"campo": "Idempotency-Key",
                                      "problema": "ya se usó con otro body, partido o autor"}]),
    "ERROR_INTERNO": ("ERROR_INTERNO", "Ocurrió un error inesperado.", []),
    "DEPENDENCIA_NO_DISPONIBLE": ("DEPENDENCIA_NO_DISPONIBLE",
                                  "Una fuente de datos necesaria no está disponible.", []),
    "CATALOGO_NO_CARGADO": ("DEPENDENCIA_NO_DISPONIBLE",
                            "El catálogo de partidos todavía no pudo cargarse.", []),
    "DEPENDENCIA_TIMEOUT": ("DEPENDENCIA_TIMEOUT", "Una fuente de datos no respondió a tiempo.", []),
}

EJEMPLOS_POR_DEFECTO = {
    400: ["VALIDACION"],
    401: ["SESION_REQUERIDA", "SESION_NO_VIGENTE"],
    403: ["ROL_NO_AUTORIZADO"],
    500: ["ERROR_INTERNO"],
    503: ["DEPENDENCIA_NO_DISPONIBLE"],
    504: ["DEPENDENCIA_TIMEOUT"],
}

# 503 de las rutas que validan el partido contra el catálogo en memoria (casos_de_uso.md §3.2).
CAIDA_O_CATALOGO = ["DEPENDENCIA_NO_DISPONIBLE", "CATALOGO_NO_CARGADO"]


def _ejemplo(nombre: str) -> dict:
    codigo, mensaje, detalles = EJEMPLOS_ERROR[nombre]
    cuerpo = {"error": {"codigo": codigo, "mensaje": mensaje, "requestId": REQUEST_ID_EJEMPLO,
                        "detalles": detalles}}
    return {"summary": codigo if nombre == codigo else f"{codigo} ({nombre.lower()})",
            "value": cuerpo}


def respuestas_error(*codigos: int, ejemplos: dict[int, list[str]] | None = None) -> dict[int, dict]:
    """Bloque responses= de una ruta con los errores que puede devolver (formato §6.1).

    `ejemplos` indica, por status, qué códigos de §6.2 devuelve la ruta (claves de
    EJEMPLOS_ERROR). Es obligatorio para 404 y 409, que dependen del recurso; el resto
    usa EJEMPLOS_POR_DEFECTO.
    """
    ejemplos = ejemplos or {}
    respuestas = {}
    for status in codigos:
        nombres = ejemplos.get(status) or EJEMPLOS_POR_DEFECTO.get(status)
        if not nombres:
            raise ValueError(f"El status {status} necesita los códigos de error de la ruta")
        codigos_error = list(dict.fromkeys(EJEMPLOS_ERROR[n][0] for n in nombres))
        respuestas[status] = {
            "model": RespuestaError,
            "description": f"{', '.join(codigos_error)}. {DESCRIPCIONES_ERROR[status]}",
            "content": {"application/json": {"examples": {n: _ejemplo(n) for n in nombres}}},
        }
    return respuestas
