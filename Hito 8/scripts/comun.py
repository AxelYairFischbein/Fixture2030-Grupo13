"""Funciones pequeñas compartidas por los scripts del módulo."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "datos"
TOKEN = RAIZ / ".local" / "admin.token"
BASE = "fixture2030_h8"
TABLA = "estadisticas_equipo"
URL = "http://127.0.0.1:8181"


def imprimir(valor):
    print(json.dumps(valor, ensure_ascii=False, indent=2))


def instante(segundos):
    return datetime.fromtimestamp(segundos, timezone.utc).isoformat().replace("+00:00", "Z")


def ahora():
    return datetime.now(timezone.utc).isoformat()


def token():
    return TOKEN.read_text(encoding="utf-8").strip()


def cli(*argumentos):
    # El secreto viaja por stdin, nunca como argumento de proceso ni en el Compose.
    resultado = subprocess.run(
        ["docker", "compose", "exec", "-T", "influxdb", "sh", "-c",
         'read -r INFLUXDB3_AUTH_TOKEN; export INFLUXDB3_AUTH_TOKEN; exec influxdb3 "$@"',
         "sh", *argumentos],
        cwd=RAIZ, input=(token() + "\n").encode("utf-8"),
        capture_output=True, timeout=60,
    )
    if resultado.returncode:
        raise RuntimeError("Falló el CLI autenticado. Revisar disponibilidad y credencial local.")
    return resultado.stdout.decode("utf-8").strip()


def pedir(ruta, datos=None, tipo="application/json"):
    solicitud = Request(URL + ruta, data=datos, headers={
        "Authorization": "Bearer " + token(), "Content-Type": tipo,
    })
    with urlopen(solicitud, timeout=60) as respuesta:
        return respuesta.read()


def consultar(sql):
    cuerpo = json.dumps({"db": BASE, "q": sql, "format": "json"}).encode()
    return json.loads(pedir("/api/v3/query_sql", cuerpo))


def muestra():
    return json.loads((DATOS / "muestra.json").read_text(encoding="utf-8"))


def filtro(inicio, fin):
    return f"time >= TIMESTAMP '{instante(inicio)}' AND time < TIMESTAMP '{instante(fin)}'"


def dimensiones(partido, lado):
    return (f"PAR-{partido:03d}", f"EQ-{2 * partido - 1 + lado:03d}",
            f"EST-{(partido - 1) % 8 + 1:02d}")


def medidas(partido, lado, segundo, paso):
    local = 50 + ((segundo // paso + partido) % 21 - 10) / 2
    periodo_tiro = 300 + 10 * partido + 20 * lado
    return (local if lado == 0 else 100 - local,
            segundo // (10 + 2 * lado),
            segundo // periodo_tiro - max(0, segundo - paso) // periodo_tiro)


def incrementos(inicio, fin, paso):
    # Incluye una muestra anterior para calcular el primer incremento de la ventana.
    return f"""WITH diferencias AS (
      SELECT time, equipo_id, posesion_pct, tiros_intervalo,
        pases_acumulados - LAG(pases_acumulados) OVER (
          PARTITION BY partido_id, equipo_id, estadio_id ORDER BY time
        ) AS pases_nuevos,
        time - LAG(time) OVER (
          PARTITION BY partido_id, equipo_id, estadio_id ORDER BY time
        ) AS separacion
      FROM {TABLA}
      WHERE {filtro(inicio - paso, fin)} AND partido_id = 'PAR-001'
    ), ventana AS (
      SELECT * FROM diferencias WHERE {filtro(inicio, fin)}
    )"""
