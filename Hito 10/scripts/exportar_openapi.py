"""Exporta el contrato OpenAPI generado por la aplicación a openapi/openapi.yaml.

No abre conexiones: usa servicios vacíos porque solo se necesitan las rutas y los modelos.
La prueba test_openapi_versionado_coincide_con_la_aplicacion falla si el archivo queda desactualizado.
"""

import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from app import config  # noqa: E402
from app.main import crear_app  # noqa: E402
from app.services import Servicios  # noqa: E402

vacio = Servicios(config.cargar(), mongo=None, neo4j=None, cassandra=None, redis=None, influx=None, iris=None)
esquema = crear_app(vacio).openapi()
destino = RAIZ / "openapi" / "openapi.yaml"
destino.parent.mkdir(exist_ok=True)
destino.write_text(yaml.safe_dump(esquema, allow_unicode=True, sort_keys=False), encoding="utf-8")
print(f"OpenAPI {esquema['info']['version']}: {len(esquema['paths'])} rutas -> {destino.relative_to(RAIZ)}")
