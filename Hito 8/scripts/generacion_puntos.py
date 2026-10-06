"""Genera line protocol secuencialmente y conserva el origen temporal de la muestra."""

import argparse
import json
from datetime import datetime, timezone
from time import perf_counter

from comun import DATOS, TABLA, ahora, dimensiones, imprimir, instante, medidas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partidos", type=int, default=2, choices=range(1, 33))
    parser.add_argument("--minutos", type=int, default=90, choices=range(10, 121))
    parser.add_argument("--paso", type=int, default=1, choices=[1, 5, 10, 30, 60])
    argumentos = parser.parse_args()
    parametros = vars(argumentos)
    DATOS.mkdir(exist_ok=True)
    ruta_meta = DATOS / "muestra.json"
    if ruta_meta.exists():
        meta = json.loads(ruta_meta.read_text(encoding="utf-8"))
        if any(meta[k] != v for k, v in parametros.items()):
            raise SystemExit("La muestra existente tiene otros parámetros. Conservar datos/ con "
                             "otro nombre antes de generar una muestra distinta.")
    else:
        inicio = int(datetime.now(timezone.utc).timestamp()) // 60 * 60 - argumentos.minutos * 60
        meta = {**parametros, "inicio": inicio, "fin": inicio + argumentos.minutos * 60,
                "puntos": argumentos.partidos * 2 * argumentos.minutos * 60 // argumentos.paso}
        ruta_meta.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    inicio_medicion = perf_counter()
    cantidad = 0
    with (DATOS / "puntos.lp").open("w", encoding="ascii", newline="\n") as archivo:
        for segundo in range(0, meta["minutos"] * 60, meta["paso"]):
            for partido in range(1, meta["partidos"] + 1):
                for lado in (0, 1):
                    pid, equipo, estadio = dimensiones(partido, lado)
                    posesion, pases, tiros = medidas(partido, lado, segundo, meta["paso"])
                    archivo.write(
                        f"{TABLA},partido_id={pid},equipo_id={equipo},estadio_id={estadio} "
                        f"posesion_pct={posesion:.1f},pases_acumulados={pases}i,"
                        f"tiros_intervalo={tiros}i {meta['inicio'] + segundo}\n"
                    )
                    cantidad += 1
    imprimir({"fecha_utc": ahora(), "parametros": parametros,
              "inicio_utc": instante(meta["inicio"]), "fin_exclusivo_utc": instante(meta["fin"]),
              "puntos_generados": cantidad, "bytes_lp": (DATOS / "puntos.lp").stat().st_size,
              "generacion_segundos": round(perf_counter() - inicio_medicion, 6)})


if __name__ == "__main__":
    main()
