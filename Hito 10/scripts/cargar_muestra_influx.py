"""Escribe una muestra reciente en InfluxDB cuando la del Hito 8 ya venció por retención (7 días).

Reutiliza dimensiones() y medidas() del Hito 8: misma tabla, tags y fields. Solo agrega puntos
de los últimos N minutos para PAR-001 y PAR-002; no borra ni reescribe la muestra original.
Uso: .venv\\Scripts\\python scripts\\cargar_muestra_influx.py [--minutos 30] [--paso 5]
"""

import argparse
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Hito 8" / "scripts"))
from app import config  # noqa: E402
from comun import TABLA, dimensiones, medidas  # noqa: E402  (Hito 8)


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--minutos", type=int, default=30, choices=range(5, 121))
    args.add_argument("--paso", type=int, default=5, choices=(1, 5, 10, 30, 60))
    a = args.parse_args()
    cfg = config.cargar()
    fin = int(time.time()) // a.paso * a.paso
    inicio = fin - a.minutos * 60
    lineas = []
    for partido in (1, 2):
        for lado in (0, 1):
            p, e, s = dimensiones(partido, lado)
            pases = 0
            for t in range(inicio, fin, a.paso):
                posesion, pases, tiros = medidas(partido, lado, t - inicio, a.paso)
                lineas.append(f"{TABLA},partido_id={p},equipo_id={e},estadio_id={s} "
                              f"posesion_pct={posesion},pases_acumulados={pases}i,tiros_intervalo={tiros}i {t}")
    r = httpx.post(f"{cfg.influx_url}/api/v3/write_lp", params={"db": cfg.influx_db, "precision": "second"},
                   content="\n".join(lineas), headers={"Authorization": f"Bearer {cfg.influx_token}"}, timeout=30)
    r.raise_for_status()
    print(f"puntos escritos: {len(lineas)} | ventana UTC {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(inicio))}"
          f" -> {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(fin))} | paso {a.paso}s")


if __name__ == "__main__":
    main()
