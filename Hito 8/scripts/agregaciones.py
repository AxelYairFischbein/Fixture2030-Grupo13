"""Resume cinco minutos en intervalos de un minuto, sin guardar otra tabla."""

from time import perf_counter

from comun import ahora, consultar, imprimir, incrementos, muestra


def main():
    meta = muestra()
    sql = incrementos(meta["fin"] - 300, meta["fin"], meta["paso"]) + f"""
      SELECT DATE_BIN(INTERVAL '1 minute', time) AS minuto, equipo_id,
        COUNT(*) AS muestras, ROUND(AVG(posesion_pct), 3) AS posesion_media,
        SUM(pases_nuevos) AS pases_minuto, SUM(tiros_intervalo) AS tiros_minuto,
        SUM(CASE WHEN separacion = INTERVAL '{meta['paso']} seconds'
          AND pases_nuevos >= 0 THEN 0 ELSE 1 END) AS intervalos_invalidos
      FROM ventana GROUP BY minuto, equipo_id ORDER BY minuto, equipo_id"""
    inicio = perf_counter()
    filas = consultar(sql)
    imprimir({"fecha_utc": ahora(), "sql": sql,
              "segundos_http_y_json": round(perf_counter() - inicio, 6), "filas": filas})
    if len(filas) != 10 or any(f["muestras"] != 60 // meta["paso"] or
                             f["intervalos_invalidos"] != 0 for f in filas):
        raise SystemExit("Resumen incompleto. No interpretar los intervalos como completos.")


if __name__ == "__main__":
    main()
