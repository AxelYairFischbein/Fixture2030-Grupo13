"""Mide latencia de lectura de la API ya iniciada. Secuencial, un cliente, con calentamiento.

Uso: .venv\\Scripts\\python scripts\\medir_latencia.py [--n 200] [--url http://127.0.0.1:8000]
Las cifras valen solo para el entorno indicado en la salida; no representan capacidad en producción.
"""

import argparse
import platform
import statistics
import time
from datetime import datetime, timezone

import httpx

RUTAS = {
    "mongodb  GET /equipos?tamanio=16": "/api/v1/equipos?tamanio=16",
    "redis    GET /equipos/EQ-001 (HIT)": "/api/v1/equipos/EQ-001",
    "neo4j    GET /partidos/PAR-001": "/api/v1/partidos/PAR-001",
    "cassandra GET comentarios 3 min": "/api/v1/partidos/PAR-001/comentarios?desde=2030-06-10T18:00:00Z&hasta=2030-06-10T18:03:00Z",
    "influxdb GET estadisticas 1m": "/api/v1/partidos/PAR-001/estadisticas?intervalo=1m",
    "iris     GET /actas/PAR-001": "/api/v1/actas/PAR-001",
}


def percentil(valores, p):
    orden = sorted(valores)
    return orden[min(len(orden) - 1, int(round(p / 100 * (len(orden) - 1))))]


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--n", type=int, default=200)
    a.add_argument("--url", default="http://127.0.0.1:8000")
    args = a.parse_args()
    cliente = httpx.Client(base_url=args.url, timeout=10)
    print(f"Fecha UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    print(f"Entorno: {platform.system()} {platform.release()}, Python {platform.python_version()}, "
          f"API uvicorn 1 worker en la notebook, fuentes en Docker Desktop (contenedores de los Hitos 4-9)")
    print(f"Método: {args.n} requests secuenciales por ruta tras 10 de calentamiento; tiempo de ida y vuelta HTTP medido en el cliente")
    print(f"{'ruta':<40}{'n':>5}{'p50 ms':>9}{'p95 ms':>9}{'máx ms':>9}{'errores':>9}")
    for nombre, ruta in RUTAS.items():
        for _ in range(10):
            cliente.get(ruta)
        tiempos, errores = [], 0
        for _ in range(args.n):
            inicio = time.perf_counter()
            r = cliente.get(ruta)
            tiempos.append((time.perf_counter() - inicio) * 1000)
            errores += r.status_code != 200
        print(f"{nombre:<40}{args.n:>5}{statistics.median(tiempos):>9.2f}{percentil(tiempos, 95):>9.2f}"
              f"{max(tiempos):>9.2f}{errores:>9}")


if __name__ == "__main__":
    main()
