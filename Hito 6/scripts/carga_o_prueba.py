"""Genera un CSV reproducible y, opcionalmente, mide su carga en dos tablas con cqlsh COPY.

Solo usa la biblioteca estándar de Python. Ejecutar desde PowerShell en Hito 6.
"""

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import time
import zlib


RAIZ = Path(__file__).resolve().parents[1]
COLUMNAS = ["partido_id", "minuto", "segmento", "creado_en", "comentario_id",
            "usuario_id", "dia", "contenido", "estado", "likes"]
TABLAS = ["comentarios_por_partido", "comentarios_por_usuario"]


def ejecutar(argumentos):
    resultado = subprocess.run(argumentos, cwd=RAIZ, text=True,
                               encoding="utf-8", errors="replace",
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if resultado.returncode:
        raise RuntimeError(resultado.stdout)
    return resultado.stdout.strip()


def generar(cantidad, destino):
    principal, secundaria, estados = Counter(), Counter(), Counter()
    inicio = datetime(2030, 6, 10, 18, tzinfo=timezone.utc)
    # El mismo CSV sirve para ambas tablas porque COPY explicita las columnas.
    # Se guarda una sola copia del archivo para evitar duplicar el volumen local.
    with (destino / "comentarios.csv").open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(COLUMNAS)
        for n in range(cantidad):
            partido = n % 64 + 1
            vuelta = n // 64
            creado = inicio + timedelta(days=(partido - 1) // 8,
                                        milliseconds=(vuelta * 997) % 7_200_000)
            # COPY recibe timestamps numéricos en milisegundos UTC.
            # Así no depende del formato de fecha configurado en cqlsh.
            creado_ms = (int(inicio.timestamp()) * 1000 + (partido - 1) // 8 * 86_400_000
                         + (vuelta * 997) % 7_200_000)
            minuto = creado_ms // 60_000 * 60_000
            comentario = f"MASIVO-{n + 1:012d}"
            usuario = f"USR-{n % 10_000 + 1:05d}"
            segmento = zlib.crc32(comentario.encode("utf-8")) % 4
            estado = "visible" if n % 20 < 16 else "pendiente" if n % 20 < 19 else "oculto"
            partido_id = f"PAR-{partido:03d}"
            dia = creado.date().isoformat()
            escritor.writerow([partido_id, minuto, segmento, creado_ms,
                               comentario, usuario, dia,
                               f"Comentario sintetico {n + 1} del Fixture 2030 en {partido_id}",
                               estado, n % 11])
            principal[(partido_id, minuto, segmento)] += 1
            secundaria[(usuario, dia)] += 1
            estados[estado] += 1
    return {
        "comentarios_logicos": cantidad,
        "filas_previstas_dos_tablas": cantidad * 2,
        "estados": dict(estados),
        "particiones_principal": len(principal),
        "max_filas_particion_principal": max(principal.values()),
        "particiones_secundaria": len(secundaria),
        "max_filas_particion_secundaria": max(secundaria.values()),
        "bytes_csv": (destino / "comentarios.csv").stat().st_size,
    }


def cargar(cantidad, procesos, destino, distribucion):
    prefijo = ["docker", "compose", "exec", "-T", "cassandra", "cqlsh", "--no-color"]
    version = ejecutar(prefijo + ["-e", "SHOW VERSION"])
    recursos = json.loads(ejecutar(["docker", "info", "--format", "{{json .}}"]))
    reporte = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "docker_cpus": recursos["NCPU"],
        "docker_memoria_bytes": recursos["MemTotal"],
        "procesos_copy": procesos,
        "consistencia": "ONE",
        "cantidad_solicitada": cantidad,
        "distribucion": distribucion,
        "tablas": {},
    }
    # Incluye ambas invocaciones de cqlsh, lectura CSV, envío y confirmaciones.
    # Excluye generación de datos y consultas de ambiente anteriores.
    inicio = time.perf_counter()
    for tabla in TABLAS:
        cql = (f"CONSISTENCY ONE; COPY fixture2030_comentarios.{tabla} "
               f"({', '.join(COLUMNAS)}) FROM '/data/generados/comentarios.csv' "
               f"WITH HEADER = TRUE AND NUMPROCESSES = {procesos} "
               "AND MINBATCHSIZE = 1 AND MAXBATCHSIZE = 1 AND MAXATTEMPTS = 1 "
               "AND MAXPARSEERRORS = 0 AND MAXINSERTERRORS = 0 "
               f"AND ERRFILE = '/data/generados/{tabla}.err';")
        resultado = subprocess.run(prefijo + ["-e", cql], cwd=RAIZ, text=True,
                                   encoding="utf-8", errors="replace",
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (destino / f"{tabla}.log").write_text(resultado.stdout, encoding="utf-8")
        resumen = re.search(r"(\d+) rows imported from (\d+) files in .+? \((\d+) skipped\)",
                            resultado.stdout)
        exitosas = int(resumen[1]) if resumen else None
        completo = (resultado.returncode == 0 and resumen is not None
                    and exitosas == cantidad and int(resumen[3]) == 0
                    and not re.search(r"Error|Failed|Exception|aborting", resultado.stdout))
        reporte["tablas"][tabla] = {
            "filas_confirmadas": exitosas,
            "completa_sin_errores": bool(completo),
            "codigo_salida": resultado.returncode,
        }
        print(f"{tabla}: {exitosas} filas confirmadas, completa={bool(completo)}", flush=True)
    segundos = time.perf_counter() - inicio
    completa = all(t["completa_sin_errores"] for t in reporte["tablas"].values())
    filas = [t["filas_confirmadas"] for t in reporte["tablas"].values()]
    fisicas = sum(filas) if all(n is not None for n in filas) else None
    # Confirmación puntual fuera del tiempo medido, incluyendo los timestamps.
    # Un COPY exitoso no basta para detectar una conversión temporal incorrecta.
    validacion = []
    with (destino / "comentarios.csv").open(encoding="utf-8", newline="") as archivo:
        lector = csv.DictReader(archivo)
        primera = next(lector)
        ultima = primera
        for fila in lector:
            ultima = fila
    for fila in [primera, ultima]:
        for tabla in TABLAS:
            particion = (f"partido_id = '{fila['partido_id']}' AND minuto = {fila['minuto']} "
                         f"AND segmento = {fila['segmento']}" if tabla == TABLAS[0] else
                         f"usuario_id = '{fila['usuario_id']}' AND dia = '{fila['dia']}'")
            consulta = (f"SELECT comentario_id, toUnixTimestamp(creado_en) AS instante_ms "
                        f"FROM fixture2030_comentarios.{tabla} WHERE {particion} "
                        f"AND creado_en = {fila['creado_en']} AND comentario_id = '{fila['comentario_id']}';")
            salida = ejecutar(prefijo + ["-e", consulta])
            validacion.append(fila['comentario_id'] in salida and fila['creado_en'] in salida)
    completa = completa and all(validacion)
    reporte.update({
        "duracion_segundos": round(segundos, 6),
        "escrituras_fisicas_confirmadas": fisicas,
        "comentarios_logicos_confirmados": cantidad if completa else None,
        "filas_sin_confirmar": cantidad * 2 - fisicas if fisicas is not None else None,
        "errores": 0 if completa else "Carga incompleta, revisar los dos logs",
        "primer_y_ultimo_comentario_verificados": all(validacion),
        "comentarios_logicos_por_segundo": round(cantidad / segundos, 2) if completa else None,
        "escrituras_fisicas_por_segundo": round(fisicas / segundos, 2) if fisicas is not None else None,
    })
    (destino / "medicion.json").write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(reporte, indent=2, ensure_ascii=False))
    if not completa:
        raise SystemExit("No se confirmó la carga completa en ambas tablas. Revisar data/generados.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cantidad", type=int, default=1_000_100)
    parser.add_argument("--cargar", action="store_true", help="Cargar y medir después de generar")
    parser.add_argument("--procesos", type=int, default=4, help="Procesos de COPY por tabla")
    args = parser.parse_args()
    if args.cantidad < 1 or not 1 <= args.procesos <= 16:
        parser.error("cantidad debe ser positiva y procesos debe estar entre 1 y 16")
    destino = RAIZ / "data" / "generados"
    destino.mkdir(parents=True, exist_ok=True)
    distribucion = generar(args.cantidad, destino)
    (destino / "distribucion.json").write_text(json.dumps(distribucion, indent=2), encoding="utf-8")
    print(json.dumps(distribucion, indent=2), flush=True)
    if args.cargar:
        cargar(args.cantidad, args.procesos, destino, distribucion)


if __name__ == "__main__":
    main()
