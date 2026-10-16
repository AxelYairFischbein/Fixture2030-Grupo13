"""Exporta el contrato OpenAPI de la API a openapi/openapi.yaml (RNF2).

Uso, desde la carpeta "Hito 10":
  python scripts/exportar_openapi.py              → escribe openapi/openapi.yaml
  python scripts/exportar_openapi.py --verificar  → sale con 1 si el archivo versionado difiere

El contrato no depende de la configuración local: antes de importar la app se fijan
valores ficticios para las variables obligatorias (no se lee .env ni ningún secreto), y
create_app no se conecta a ninguna base fuera del lifespan, que acá no se ejecuta.
"""

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "openapi" / "openapi.yaml"

VARIABLES_FICTICIAS = {
    "MONGO_USER": "no-usado",
    "MONGO_PASSWORD": "no-usado",
    "NEO4J_USER": "no-usado",
    "NEO4J_PASSWORD": "no-usado",
    "INFLUX_TOKEN_FILE": "no-usado.token",
    "IRIS_USER": "no-usado",
    "IRIS_PASSWORD": "no-usado",
}


def generar() -> str:
    os.environ.update(VARIABLES_FICTICIAS)
    sys.path.insert(0, str(RAIZ))
    from app.config.settings import Settings
    from app.main import create_app
    from app.openapi import contrato_yaml

    app = create_app(Settings(_env_file=None), iniciar_catalogo=False)
    return contrato_yaml(app.openapi())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verificar", action="store_true",
                        help="no escribe: compara con el archivo versionado")
    argumentos = parser.parse_args()
    contrato = generar()
    if argumentos.verificar:
        actual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if actual != contrato:
            print(f"{DESTINO.relative_to(RAIZ)} difiere de app.openapi(): "
                  "ejecutar scripts/exportar_openapi.ps1", file=sys.stderr)
            return 1
        print(f"{DESTINO.relative_to(RAIZ)} coincide con app.openapi().")
        return 0
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": el mismo archivo en Windows y en Linux.
    with DESTINO.open("w", encoding="utf-8", newline="\n") as archivo:
        archivo.write(contrato)
    print(f"Contrato escrito en {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
