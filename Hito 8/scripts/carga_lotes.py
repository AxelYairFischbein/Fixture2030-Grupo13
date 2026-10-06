"""Carga con un cliente y lotes acotados. Reintenta solo fallos transitorios."""

import argparse
from itertools import islice
from time import perf_counter, sleep
from urllib.error import HTTPError, URLError

from comun import BASE, DATOS, TABLA, ahora, consultar, filtro, imprimir, muestra, pedir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lote", type=int, default=1000)
    argumentos = parser.parse_args()
    if not 1 <= argumentos.lote <= 10000:
        parser.error("El lote debe tener entre 1 y 10000 puntos.")
    meta = muestra()
    ruta = f"/api/v3/write_lp?db={BASE}&precision=second&accept_partial=false&no_sync=false"
    enviados = aceptados = peticiones = lotes = 0
    inicio = perf_counter()
    try:
        with (DATOS / "puntos.lp").open("rb") as archivo:
            while lineas := list(islice(archivo, argumentos.lote)):
                contenido = b"".join(lineas)
                for intento in range(3):
                    enviados += len(lineas)
                    peticiones += 1
                    try:
                        pedir(ruta, contenido, "text/plain")
                        break
                    except HTTPError as error:
                        if error.code not in (429, 500, 502, 503, 504) or intento == 2:
                            raise
                    except (URLError, TimeoutError, ConnectionError):
                        if intento == 2:
                            raise
                    sleep(intento + 1)
                aceptados += len(lineas)
                lotes += 1
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        imprimir({"fecha_utc": ahora(), "estado": "carga interrumpida",
                  "puntos_enviados_incluyendo_reintentos": enviados,
                  "puntos_con_respuesta_exitosa": aceptados, "peticiones": peticiones})
        raise SystemExit(f"Error de carga: {error}. Una respuesta perdida puede haber escrito "
                         "datos. Corregir la causa y repetir el mismo archivo, sin cambiar tiempos.")
    duracion = perf_counter() - inicio
    almacenados = consultar(f"SELECT COUNT(*) AS puntos FROM {TABLA} "
                           f"WHERE {filtro(meta['inicio'], meta['fin'])}")[0]["puntos"]
    imprimir({"fecha_utc": ahora(), "metodo": "HTTP local con WAL sincronizado",
              "clientes_concurrentes": 1, "tamano_lote": argumentos.lote,
              "puntos_generados_segun_metadatos": meta["puntos"],
              "puntos_enviados_incluyendo_reintentos": enviados,
              "puntos_con_respuesta_exitosa": aceptados, "lotes_aceptados": lotes,
              "peticiones": peticiones, "puntos_almacenados_en_ventana": almacenados,
              "carga_segundos": round(duracion, 6),
              "puntos_confirmados_por_segundo": round(aceptados / duracion, 2)})
    if aceptados != meta["puntos"] or almacenados != meta["puntos"]:
        raise SystemExit("La cantidad difiere de la muestra. Ejecutar validacion.py.")


if __name__ == "__main__":
    main()
