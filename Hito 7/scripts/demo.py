"""Demostracion pequena. Todas las operaciones Redis usan redis-cli en Docker."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shlex
import subprocess
import threading
import time

BASE = Path(__file__).resolve().parent.parent
PREFIJO = "fixture2030:h7:demo:"
CLI = ["docker", "compose", "exec", "-T", "redis", "redis-cli", "--json", "-e"]


def ejecutar(args, entrada=None):
    resultado = subprocess.run(args, input=entrada, cwd=BASE, text=True,
                               encoding="utf-8", capture_output=True, timeout=60)
    if resultado.returncode:
        raise RuntimeError(resultado.stderr.strip() or resultado.stdout.strip())
    return resultado.stdout.strip()


def redis(*args):
    salida = ejecutar(CLI + [str(a) for a in args])
    # redis-cli imprime INFO como texto incluso con --json.
    return salida if args[0] == "INFO" else json.loads(salida)


def comandos(nombre):
    # Solo comentarios de linea completa y lineas vacias. No enviar '#' a Redis.
    return [linea.strip() for linea in (BASE / "scripts" / nombre).read_text(
        encoding="utf-8-sig").splitlines()
        if linea.strip() and not linea.lstrip().startswith("#")]


def archivo(nombre):
    lineas = comandos(nombre)
    salida = ejecutar(CLI, "\n".join(lineas) + "\n")
    if any(linea.startswith("INFO ") for linea in lineas):
        print(nombre, "(comandos en orden, comentarios filtrados):\n" + salida)
        return
    respuestas = [json.loads(linea) for linea in salida.splitlines()]
    comprobar(len(respuestas) == len(lineas), "Una respuesta por comando, sin comentarios enviados")
    for orden, respuesta in zip(lineas, respuestas):
        print(f"> {orden}\n{json.dumps(respuesta, ensure_ascii=False)}")
    return respuestas


def comprobar(condicion, mensaje):
    if not condicion:
        raise RuntimeError("FALLO: " + mensaje)
    print("OK: " + mensaje)


def cabecera():
    print("Fecha UTC:", datetime.now(timezone.utc).isoformat())
    servidor = redis("INFO", "server")
    print(next(linea for linea in servidor.splitlines() if linea.startswith("redis_version:")))


def sesiones():
    archivo("carga_muestra.redis")
    clave = PREFIJO + "sesion:SES-DEMO-01"
    anterior = redis("HGET", clave, "ultima_actividad")
    time.sleep(2)
    ttl_antes = redis("TTL", clave)
    archivo("sesiones.redis")
    ttl_despues = redis("TTL", clave)
    print("TTL antes y despues de actividad:", ttl_antes, ttl_despues)
    comprobar(ttl_despues > ttl_antes, "La actividad renueva los 1800 segundos")
    comprobar(int(redis("HGET", clave, "ultima_actividad")) > int(anterior),
              "Se actualiza la ultima actividad")
    renovar = next(linea for linea in comandos("sesiones.redis") if linea.startswith("EVAL")
                   and clave in linea)
    print("Espera de 4 segundos para la sesion de prueba con TTL 3")
    time.sleep(4)
    for identificador in ("SES-CORTA", "SES-DEMO-02"):
        ausente = PREFIJO + "sesion:" + identificador
        print(identificador, "HGETALL:", redis("HGETALL", ausente), "TTL:", redis("TTL", ausente))
        resultado = json.loads(ejecutar(CLI, renovar.replace(clave, ausente) + "\n"))
        comprobar(resultado == 0 and redis("EXISTS", ausente) == 0,
                  identificador + ": actividad rechazada, no se recrea la sesion")
    print(redis("INFO", "stats"))


def cache():
    # Fuente simulada FUERA de Redis, en memoria del proceso Python.
    # Representa una ficha documental. No consulta ni modifica MongoDB.
    origen = {"equipoId": "EQ-001", "codigo": "F01", "nombre": "Seleccion Sintetica 01",
              "confederacion": "AFC"}
    clave = PREFIJO + "cache:equipo:EQ-001"
    hits, misses = 0, 0

    def leer():
        nonlocal hits, misses
        try:
            copia = redis("GET", clave)
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            print("Redis no disponible o lectura rechazada. Se consulta el origen:", error)
            copia = None
        if copia is not None:
            hits += 1
            print("HIT:", copia)
            return json.loads(copia)
        misses += 1
        if origen is None:
            raise RuntimeError("Dato no disponible: tampoco se pudo obtener del origen")
        dato = origen.copy()
        print("MISS. Lectura de la fuente simulada externa:", dato)
        try:
            redis("SET", clave, json.dumps(dato), "EX", 300)
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            print("Copia no confirmada. Se devuelve el dato de origen:", error)
        return dato

    redis("DEL", clave)
    archivo("cache.redis")
    comprobar(redis("EXISTS", clave) == 0, "Inicio sin copia en Redis")
    primero = leer()
    comprobar(0 < redis("TTL", clave) <= 300, "Copia guardada con TTL de 5 minutos")
    comprobar(leer() == primero, "Segunda lectura desde cache")
    origen["nombre"] = "Seleccion Sintetica 01 - ficha actualizada"
    print("Cambio confirmado en la fuente simulada:", origen)
    comprobar(redis("DEL", clave) == 1, "Invalidacion despues del cambio de origen")
    comprobar(leer()["nombre"] == origen["nombre"], "La lectura siguiente recupera el dato nuevo")
    print(f"Intervalo: tres llamadas a leer. Hits={hits}, misses={misses}, porcentaje={hits / 3 * 100:.2f}%")
    archivo("cache.redis")


def concurrencia():
    clave = PREFIJO + "ranking:visitas:ventana"
    redis("DEL", clave)
    # Reutiliza el comando del archivo sin implementar un protocolo Redis propio.
    visita = shlex.split(comandos("concurrencia.redis")[0])
    for partido in ("PAR-002", "PAR-002", "PAR-003"):
        json.loads(ejecutar(CLI + visita[:-1] + [partido]))
    ttl_antes = redis("TTL", clave)
    clientes, por_cliente = 4, 100
    barrera = threading.Barrier(clientes)

    def cliente(_):
        barrera.wait(timeout=10)
        salida = ejecutar(CLI + ["-r", str(por_cliente), "-i", "0.01"] + visita)
        return [json.loads(linea) for linea in salida.splitlines()]

    print("Sistema cliente:", platform.platform(), "Python:", platform.python_version())
    print("Recursos del motor Docker:", ejecutar([
        "docker", "info", "--format", "CPU={{.NCPU}} RAM_bytes={{.MemTotal}} SO={{.OperatingSystem}}"]))
    print("Limites del contenedor: 1 CPU, 256 MiB. Redis maxmemory: 64 MiB, noeviction, AOF everysec")
    print("Metodo: 4 redis-cli, 100 visitas cada uno, pausa de 10 ms por cliente entre visitas")
    print("Tiempo incluye creacion de clientes, llamadas Docker, pausas y lectura de respuestas")
    inicio = time.perf_counter()
    with ThreadPoolExecutor(max_workers=clientes) as ejecutor:
        respuestas = list(ejecutor.map(cliente, range(clientes)))
    duracion = time.perf_counter() - inicio
    esperado = clientes * por_cliente
    total = float(redis("ZSCORE", clave, "PAR-001"))
    comprobar(all(len(r) == por_cliente for r in respuestas), "100 respuestas por cliente")
    comprobar(sorted(float(n) for r in respuestas for n in r) == list(range(1, esperado + 1)),
              "Puntajes devueltos 1 a 400, sin duplicados ni saltos")
    # Rangos superpuestos prueban que hubo intercalacion entre los clientes.
    rangos = [(min(map(float, r)), max(map(float, r))) for r in respuestas]
    print("Rangos de puntajes por cliente:", rangos)
    comprobar(max(a for a, b in rangos) < min(b for a, b in rangos), "Clientes intercalados")
    comprobar(total == esperado, f"Resultado final {total:g}, esperado {esperado}")
    comprobar(0 < redis("TTL", clave) <= ttl_antes, "La ventana no se renueva por cada visita")
    print(f"Operaciones medidas={esperado}, concurrencia={clientes}, segundos={duracion:.6f}, visitas/s={esperado / duracion:.2f}")
    print("Tres visitas de preparacion y consultas de verificacion fuera del intervalo")
    print("Top 3:", redis("ZRANGE", clave, 0, 2, "REV", "WITHSCORES"))
    print("TTL:", redis("TTL", clave))
    print(ejecutar(["docker", "stats", "--no-stream", "--format",
                   "CPU={{.CPUPerc}} RAM={{.MemUsage}}", ejecutar(["docker", "compose", "ps", "-q", "redis"])]))
    archivo("metricas.redis")
    cursor = "0"
    while True:
        cursor, claves = redis("SCAN", cursor, "MATCH", PREFIJO + "*", "COUNT", 10)
        print("SCAN cursor:", cursor, "claves:", claves)
        if str(cursor) == "0":
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accion", choices=["archivo", "sesiones", "cache", "concurrencia"])
    parser.add_argument("nombre", nargs="?", choices=[p.name for p in (BASE / "scripts").glob("*.redis")])
    args = parser.parse_args()
    if args.accion == "archivo" and not args.nombre:
        parser.error("archivo requiere el nombre de un .redis")
    cabecera()
    if args.accion == "archivo":
        archivo(args.nombre)
    else:
        {"sesiones": sesiones, "cache": cache, "concurrencia": concurrencia}[args.accion]()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as error:
        print("ERROR:", error)
        raise SystemExit(1)
