"""Recupera una ventana y compara los dos equipos de PAR-001."""

from time import perf_counter

from comun import TABLA, ahora, consultar, filtro, imprimir, incrementos, muestra


def main():
    meta = muestra()
    fin = meta["fin"]
    consultas = {
        "ultimas_muestras_equipo": f"""SELECT time, equipo_id, estadio_id,
          posesion_pct, pases_acumulados, tiros_intervalo FROM {TABLA}
          WHERE {filtro(fin - 60, fin)}
            AND partido_id = 'PAR-001' AND equipo_id = 'EQ-001'
          ORDER BY time DESC LIMIT 5""",
        "comparacion_cinco_minutos": incrementos(fin - 300, fin, meta["paso"]) + f"""
          SELECT equipo_id, COUNT(*) AS muestras,
            ROUND(AVG(posesion_pct), 3) AS posesion_media,
            SUM(pases_nuevos) AS pases_ventana, SUM(tiros_intervalo) AS tiros_ventana,
            SUM(CASE WHEN separacion = INTERVAL '{meta['paso']} seconds'
              AND pases_nuevos >= 0 THEN 0 ELSE 1 END) AS intervalos_invalidos
          FROM ventana GROUP BY equipo_id ORDER BY equipo_id""",
    }
    for nombre, sql in consultas.items():
        inicio = perf_counter()
        filas = consultar(sql)
        imprimir({"fecha_utc": ahora(), "consulta": nombre, "sql": sql,
                  "segundos_http_y_json": round(perf_counter() - inicio, 6), "filas": filas})
        if nombre == "comparacion_cinco_minutos" and (
            len(filas) != 2 or any(f["muestras"] != 300 // meta["paso"] or
                                  f["intervalos_invalidos"] != 0 for f in filas)
        ):
            raise SystemExit("Comparación incompleta. Revisar puntos ausentes o discontinuidades.")


if __name__ == "__main__":
    main()
