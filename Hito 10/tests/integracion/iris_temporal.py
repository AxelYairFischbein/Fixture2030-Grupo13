"""Partido temporal en IRIS para probar CU-19 sin tocar PAR-001.

Crea un FixtureH9.Partido con un código libre al azar en PAR-900…PAR-989, estadio
EST-01, estado PENDIENTE (InitialExpression), el árbitro ARB-001 de la muestra y sin
eventos, igual que el árbol temporal de FixtureH9.Demo. El borrado usa %DeleteId,
que elimina también los hijos y conserva las personas. El ID interno solo se usa
acá para borrar y nunca se imprime.

Uso desde PowerShell (scripts/evidencia_iris.ps1):
  python -m tests.integracion.iris_temporal crear    → imprime el código creado
  python -m tests.integracion.iris_temporal borrar PAR-9xx
"""

import random
import sys

import iris
import iris.dbapi

from app.config.settings import Settings

CLASE_PARTIDO = "FixtureH9.Partido"
CLASE_ARBITRO = "FixtureH9.Arbitro"


def conectar(settings: Settings):
    conexion = iris.dbapi.connect(
        hostname=settings.iris_host, port=settings.iris_port, namespace=settings.iris_namespace,
        username=settings.iris_user, password=settings.iris_password.get_secret_value(),
        timeout=5,
    )
    return conexion, iris.createIRIS(conexion)


def _id_de(nativo, codigo: str) -> str | None:
    referencia = iris.IRISReference(None)
    if nativo.classMethodBoolean(CLASE_PARTIDO, "PorCodigoExists", codigo, referencia):
        return str(referencia.getValue())
    return None


def crear(nativo) -> str:
    libres = [f"PAR-{n}" for n in range(900, 990)]
    random.shuffle(libres)
    codigo = next(c for c in libres if _id_de(nativo, c) is None)
    arbitro = nativo.classMethodObject(CLASE_ARBITRO, "PorCodigoOpen", "ARB-001")
    if arbitro is None:
        raise RuntimeError("Falta el árbitro ARB-001: ejecutar FixtureH9.Demo.Ejecutar() en el Hito 9")
    partido = nativo.classMethodObject(CLASE_PARTIDO, "%New")
    partido.set("Codigo", codigo)
    partido.set("EstadioCodigo", "EST-01")
    partido.set("Arbitro", arbitro)
    sc = partido.invoke("%Save")
    if str(sc) != "1":
        raise RuntimeError("No se pudo guardar el partido temporal")
    return codigo


def borrar(nativo, codigo: str) -> None:
    if not codigo.startswith("PAR-9"):
        raise ValueError("Solo se borran partidos temporales PAR-900…PAR-989")
    identificador = _id_de(nativo, codigo)
    if identificador is not None:
        nativo.classMethodValue(CLASE_PARTIDO, "%DeleteId", identificador)
    if _id_de(nativo, codigo) is not None:
        raise RuntimeError(f"No se pudo borrar el partido temporal {codigo}")


def main(argumentos: list[str]) -> int:
    from app.config.settings import cargar_settings

    conexion, nativo = conectar(cargar_settings())
    try:
        if argumentos[:1] == ["crear"]:
            print(crear(nativo))
        elif argumentos[:1] == ["borrar"] and len(argumentos) == 2:
            borrar(nativo, argumentos[1])
            print(f"borrado {argumentos[1]}")
        else:
            print(__doc__, file=sys.stderr)
            return 2
        return 0
    finally:
        conexion.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
