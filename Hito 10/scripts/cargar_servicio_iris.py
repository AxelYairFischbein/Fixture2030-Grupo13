"""Carga y compila Hito 10/iris/FixtureH10.Servicio.cls en el IRIS del Hito 9 (namespace USER).

Usa el SDK de Python con las credenciales de Hito 10/.env: no copia archivos al
contenedor ni abre el Terminal. Solo crea o reemplaza la clase FixtureH10.Servicio;
no toca ni recompila el paquete FixtureH9. Es repetible.

Ejecutar desde la carpeta "Hito 10":  python scripts/cargar_servicio_iris.py
(o con scripts/cargar_servicio_iris.ps1). Nunca imprime credenciales.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import iris  # noqa: E402
import iris.dbapi  # noqa: E402

from app.adapters.iris_adaptador import CLASE_SERVICIO  # noqa: E402
from app.config.settings import cargar_settings  # noqa: E402

ARCHIVO = RAIZ / "iris" / f"{CLASE_SERVICIO}.cls"
CRLF = chr(13) + chr(10)


def main() -> int:
    s = cargar_settings()
    # SetTextFromString separa las líneas por CRLF: con LF toda la clase sería una sola línea.
    texto = CRLF.join(ARCHIVO.read_text(encoding="utf-8").splitlines())
    try:
        conexion = iris.dbapi.connect(
            hostname=s.iris_host, port=s.iris_port, namespace=s.iris_namespace,
            username=s.iris_user, password=s.iris_password.get_secret_value(), timeout=10,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo conectar a IRIS ({type(exc).__name__}). ¿Está levantado el Hito 9 "
              "y son correctas IRIS_USER / IRIS_PASSWORD en Hito 10/.env?", file=sys.stderr)
        return 1
    try:
        nativo = iris.createIRIS(conexion)
        sc = nativo.classMethodValue("%Compiler.UDL.TextServices", "SetTextFromString",
                                     s.iris_namespace, CLASE_SERVICIO, texto)
        if str(sc) != "1":
            print("IRIS rechazó el texto de la clase: "
                  + nativo.classMethodString("%SYSTEM.Status", "GetErrorText", sc), file=sys.stderr)
            return 1
        sc = nativo.classMethodValue("%SYSTEM.OBJ", "Compile", CLASE_SERVICIO, "ck-d")
        if str(sc) != "1":
            print("La compilación falló: "
                  + nativo.classMethodString("%SYSTEM.Status", "GetErrorText", sc), file=sys.stderr)
            return 1
        version = nativo.classMethodString(CLASE_SERVICIO, "Version")
        print(f"COMPILACION OK: {CLASE_SERVICIO} versión {version} en el namespace {s.iris_namespace}")
        return 0
    finally:
        conexion.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
