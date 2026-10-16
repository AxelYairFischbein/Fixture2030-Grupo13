"""Contrato OpenAPI de la API (RNF2).

FastAPI declara un 422 en cada ruta con parámetros, pero la API nunca lo devuelve: el
manejador de validación lo convierte en 400 VALIDACION (casos_de_uso.md §6.2). Este
módulo quita esa respuesta del contrato para que el OpenAPI describa solo lo que la API
hace. El archivo versionado openapi/openapi.yaml se genera con contrato_yaml()
(scripts/exportar_openapi.py) y tests/test_openapi.py comprueba que siga igual a app.openapi().
"""

import json
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

ETIQUETAS = [
    {"name": "salud", "description": "Estado de las dependencias y del catálogo de partidos."},
    {"name": "equipos", "description": "Fichas, listados y planteles (MongoDB, Hito 4; caché "
                                       "Redis, Hito 7) y agenda de un equipo (Neo4j, Hito 5)."},
    {"name": "jugadores", "description": "Ficha de un jugador (MongoDB, Hito 4)."},
    {"name": "partidos", "description": "Calendario y eventos de un partido (Neo4j, Hito 5). "
                                        "No informan el estado del partido (fuente: IRIS)."},
    {"name": "comentarios", "description": "Lectura, publicación idempotente y moderación de "
                                           "comentarios (Cassandra, Hito 6; sesión Redis)."},
    {"name": "sesiones", "description": "Consulta, renovación y cierre de la sesión vigente "
                                        "(Redis, Hito 7). La sesión viaja en X-Session-Id."},
    {"name": "cache", "description": "Invalidación de la ficha cacheada de un equipo (Redis, "
                                     "Hito 7; rol operador)."},
    {"name": "estadisticas", "description": "Estadísticas temporales por partido y equipo "
                                            "(InfluxDB 3, Hito 8)."},
    {"name": "actas", "description": "Acta y transiciones de estado del partido (InterSystems "
                                     "IRIS, Hito 9; fuente autoritativa del estado)."},
]

SCHEMAS_DE_422 = ("HTTPValidationError", "ValidationError")


def _ajustar(esquema: dict[str, Any]) -> None:
    """Quita el 422 que la API no devuelve y traduce la descripción por defecto de FastAPI."""
    for operaciones in esquema.get("paths", {}).values():
        for operacion in operaciones.values():
            respuestas = operacion.get("responses", {})
            respuestas.pop("422", None)
            for respuesta in respuestas.values():
                if respuesta.get("description") == "Successful Response":
                    respuesta["description"] = "Respuesta exitosa."
    schemas = esquema.get("components", {}).get("schemas", {})
    for nombre in SCHEMAS_DE_422:
        schemas.pop(nombre, None)
    # Ningún otro schema debería referenciarlos; si alguno lo hiciera, el contrato quedaría roto.
    texto = json.dumps(esquema)
    for nombre in SCHEMAS_DE_422:
        if f"#/components/schemas/{nombre}" in texto:
            raise RuntimeError(f"El OpenAPI todavía referencia {nombre}")


def instalar_openapi(app: FastAPI) -> None:
    """Reemplaza app.openapi por la versión sin 422 y con las etiquetas descritas."""

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            esquema = get_openapi(
                title=app.title, version=app.version, description=app.description,
                routes=app.routes, tags=ETIQUETAS,
            )
            _ajustar(esquema)
            app.openapi_schema = esquema
        return app.openapi_schema

    app.openapi = openapi


def normalizar(esquema: dict[str, Any]) -> dict[str, Any]:
    """Mismo contenido como tipos JSON puros (claves str, listas), para comparar con el YAML."""
    return json.loads(json.dumps(esquema))


def contrato_yaml(esquema: dict[str, Any]) -> str:
    """Serialización determinista del contrato: mismo esquema → mismo texto."""
    return yaml.safe_dump(normalizar(esquema), sort_keys=False, allow_unicode=True, width=100)
