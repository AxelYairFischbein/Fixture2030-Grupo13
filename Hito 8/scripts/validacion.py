"""Contrasta cantidad, distribución y una muestra con el generador."""

from datetime import datetime, timezone

from comun import (TABLA, ahora, consultar, dimensiones, filtro, imprimir,
                   instante, medidas, muestra)


def main():
    meta = muestra()
    sql = f"""SELECT partido_id, equipo_id, estadio_id, COUNT(*) AS puntos,
      MIN(time) AS primero, MAX(time) AS ultimo,
      MIN(posesion_pct) AS posesion_min, MAX(posesion_pct) AS posesion_max,
      MAX(pases_acumulados) AS pases_finales, SUM(tiros_intervalo) AS tiros_totales
      FROM {TABLA} WHERE {filtro(meta['inicio'], meta['fin'])}
      GROUP BY partido_id, equipo_id, estadio_id ORDER BY partido_id, equipo_id"""
    filas = consultar(sql)
    esperado_serie = meta["minutos"] * 60 // meta["paso"]
    assert len(filas) == meta["partidos"] * 2, "Cantidad inesperada de series"
    for partido in range(1, meta["partidos"] + 1):
        for lado in (0, 1):
            fila = filas[(partido - 1) * 2 + lado]
            assert tuple(fila[k] for k in ("partido_id", "equipo_id", "estadio_id")) == dimensiones(partido, lado)
            assert fila["puntos"] == esperado_serie, "Cantidad inesperada por serie"
            assert datetime.fromisoformat(fila["primero"]).replace(tzinfo=timezone.utc).timestamp() == meta["inicio"]
            assert datetime.fromisoformat(fila["ultimo"]).replace(tzinfo=timezone.utc).timestamp() == meta["fin"] - meta["paso"]
            assert 0 <= fila["posesion_min"] <= fila["posesion_max"] <= 100
            segundo = meta["minutos"] * 60 - meta["paso"]
            assert fila["pases_finales"] == medidas(partido, lado, segundo, meta["paso"])[1]
            assert fila["tiros_totales"] == segundo // (300 + 10 * partido + 20 * lado)
    ejemplo = consultar(f"SELECT * FROM {TABLA} WHERE {filtro(meta['inicio'], meta['inicio'] + meta['paso'])} "
                        "AND partido_id = 'PAR-001' AND equipo_id = 'EQ-001'")
    posesion, pases, tiros = medidas(1, 0, 0, meta["paso"])
    assert len(ejemplo) == 1
    assert (ejemplo[0]["posesion_pct"], ejemplo[0]["pases_acumulados"],
            ejemplo[0]["tiros_intervalo"]) == (posesion, pases, tiros)
    tipos = consultar(f"SELECT column_name, data_type FROM information_schema.columns "
                      f"WHERE table_name = '{TABLA}' ORDER BY ordinal_position")
    por_columna = {f["column_name"]: f["data_type"] for f in tipos}
    assert por_columna["posesion_pct"] == "Float64"
    assert por_columna["pases_acumulados"] == por_columna["tiros_intervalo"] == "Int64"
    imprimir({"fecha_utc": ahora(), "validacion": "OK", "puntos_esperados": meta["puntos"],
              "puntos_almacenados": sum(f["puntos"] for f in filas),
              "inicio_utc": instante(meta["inicio"]), "distribucion": filas,
              "muestra": ejemplo, "tipos": tipos})


if __name__ == "__main__":
    main()
