"""Crea una credencial local y una base con retención, sin borrar datos."""

import json
import subprocess
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from comun import BASE, RAIZ, TOKEN, URL, ahora, cli, imprimir


def main():
    # Espera acotada al arranque. Un 401 confirma disponibilidad sin desactivar autenticación.
    for intento in range(15):
        try:
            with urlopen(URL + "/health", timeout=2):
                break
        except HTTPError as error:
            if error.code == 401:
                break
            raise
        except (URLError, TimeoutError, ConnectionError):
            if intento == 14:
                raise RuntimeError("El servidor no respondió. Revisar docker compose ps y logs.")
            sleep(1)
    if not TOKEN.exists():
        TOKEN.parent.mkdir(exist_ok=True)
        resultado = subprocess.run(
            ["docker", "compose", "exec", "-T", "influxdb", "influxdb3",
             "create", "token", "--admin", "--format", "json"],
            cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        if resultado.returncode:
            raise RuntimeError("No se pudo crear el token. Si el nodo ya tiene uno, recuperar "
                               "esa credencial en .local/admin.token. No reinicializar los datos.")
        credencial = json.loads(resultado.stdout)["token"]
        with TOKEN.open("x", encoding="utf-8") as archivo:
            archivo.write(credencial + "\n")
        print("Credencial guardada en .local/admin.token. Su valor no se muestra.")

    bases = json.loads(cli("show", "databases", "--format", "json"))
    if not any(BASE in fila.values() for fila in bases):
        cli("create", "database", "--retention-period", "7d", BASE)
    imprimir({"fecha_utc": ahora(), "bases_desde_cli_contenedor":
              json.loads(cli("show", "databases", "--format", "json"))})
    retencion = json.loads(cli("show", "retention", "--database", BASE, "--format", "json"))
    imprimir({"retencion": retencion})
    if not any(f.get("database_name") == BASE and f.get("retention_period") == "7.0000d"
               for f in retencion):
        raise RuntimeError("La base existente no tiene la retención esperada de siete días. "
                           "Revisar su configuración sin borrar datos.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit(f"Inicialización interrumpida: {error}")
