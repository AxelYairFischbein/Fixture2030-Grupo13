"""Escribe una muestra reciente en InfluxDB cuando la del Hito 8 ya venció por retención (7 días).

Reutiliza las medidas y dimensiones de la primera jornada del Hito 8. La carga omite los
partidos que ya tienen puntos en la ventana para no sobrescribir datos recientes.
Uso: python scripts/cargar_muestra_influx.py [--partido 3] [--minutos 30] [--paso 5]
"""

import argparse
import calendar
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Hito 8" / "scripts"))
from app import config  # noqa: E402
from comun import TABLA, dimensiones, medidas  # noqa: E402  (Hito 8)


def enviar(cfg, ruta, cuerpo, tipo):
    solicitud = Request(
        f"{cfg.influx_url.rstrip('/')}{ruta}",
        data=cuerpo.encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg.influx_token}", "Content-Type": tipo},
    )
    with urlopen(solicitud, timeout=30) as respuesta:
        return respuesta.read()


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--minutos", type=int, default=30, choices=range(5, 121))
    args.add_argument("--paso", type=int, default=5, choices=(1, 5, 10, 30, 60))
    args.add_argument("--partido", type=int, action="append", choices=range(1, 33), metavar="N",
                      help="partido de la primera jornada (1 a 32). Se puede repetir. Por defecto: 1 y 2")
    args.add_argument("--inicio", metavar="AAAA-MM-DDThh:mm:ssZ",
                      help="comienzo fijo de la ventana UTC, p. ej. el inicio del partido. Por defecto: termina ahora")
    a = args.parse_args()
    cfg = config.cargar()
    if not cfg.influx_token:
        args.error("No se encontró el token local de InfluxDB configurado para la API.")
    if a.inicio:
        inicio = calendar.timegm(time.strptime(a.inicio, "%Y-%m-%dT%H:%M:%SZ")) // a.paso * a.paso
        fin = inicio + a.minutos * 60
    else:
        fin = int(time.time()) // a.paso * a.paso
        inicio = fin - a.minutos * 60
    formato = "%Y-%m-%dT%H:%M:%SZ"
    desde, hasta = (time.strftime(formato, time.gmtime(t)) for t in (inicio, fin))
    lineas = []
    for partido in dict.fromkeys(a.partido or (1, 2)):
        partido_id, _ = dimensiones(partido, 0)
        q = (f"SELECT COUNT(*) AS puntos FROM {TABLA} WHERE partido_id = '{partido_id}' "
             f"AND time >= TIMESTAMP '{desde}' AND time < TIMESTAMP '{hasta}'")
        puntos = enviar(cfg, "/api/v3/query_sql",
                        json.dumps({"db": cfg.influx_db, "q": q, "format": "json"}), "application/json")
        if json.loads(puntos)[0]["puntos"] > 0:
            print(f"{partido_id}: ya tiene puntos en esta ventana. Se conserva la muestra existente.")
            continue
        for lado in (0, 1):
            p, e = dimensiones(partido, lado)
            pases = 0
            for t in range(inicio, fin, a.paso):
                posesion, pases, tiros = medidas(partido, lado, t - inicio, a.paso)
                lineas.append(f"{TABLA},partido_id={p},equipo_id={e} "
                              f"posesion_pct={posesion},pases_acumulados={pases}i,tiros_intervalo={tiros}i {t}")
    if lineas:
        parametros = urlencode({"db": cfg.influx_db, "precision": "second"})
        enviar(cfg, f"/api/v3/write_lp?{parametros}", "\n".join(lineas), "text/plain")
    print(f"Puntos escritos: {len(lineas)}. Ventana UTC {desde} a {hasta}, paso de {a.paso} s.")


if __name__ == "__main__":
    main()
