"""Carga breve y falla recuperable de Redis. No carga muestras ni modifica datos canónicos."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from verificar_version import verificar

RAIZ = Path(__file__).resolve().parent
API = "http://127.0.0.1:8000/api/v1"
PROM = "http://127.0.0.1:9090/api/v1"
REDIS = "grupo13-hito7-redis-1"


def fecha():
    return datetime.now(timezone(timedelta(hours=-3))).isoformat()


def http(url, metodo="GET", cuerpo=None):
    req = Request(url, method=metodo, data=None if cuerpo is None else json.dumps(cuerpo).encode(),
                  headers={"Content-Type": "application/json"})
    try:
        respuesta = urlopen(req, timeout=15)
    except HTTPError as error:
        respuesta = error
    with respuesta:
        texto = respuesta.read()
        return {"status": respuesta.status, "cache": respuesta.headers.get("X-Cache"),
                "body": json.loads(texto) if texto else None}


def prom(ruta, **params):
    r = http(PROM + ruta + ("?" + urlencode(params) if params else ""))
    if r["status"] != 200 or r["body"]["status"] != "success":
        raise RuntimeError("Consulta Prometheus no válida")
    return r["body"]["data"]


def consultas():
    dashboard = json.loads((RAIZ / "grafana/dashboards/fixture2030.json").read_text(encoding="utf-8"))
    return [{"panel": p["id"], "titulo": p["title"], "expr": t["expr"], "leyenda": t["legendFormat"]}
            for p in dashboard["panels"] for t in p["targets"]]


def estado():
    targets = prom("/targets")["activeTargets"]
    return {"fecha": fecha(), "salud": http(API + "/salud"),
            "targets": [{k: t[k] for k in ("labels", "health", "lastError", "lastScrape", "scrapeUrl")} for t in targets],
            "alertas": prom("/alerts")["alerts"],
            "consultas": [{**q, "resultado": prom("/query", query=q["expr"])} for q in consultas()]}


def carga(segundos, sesion, caida):
    fin = time.monotonic() + segundos
    rutas = [("/equipos?tamanio=5", 200), ("/equipos/EQ-001", 200),
             (f"/sesiones/{sesion}", 503 if caida else 200), ("/equipos/EQ-999", 404)]

    def cliente():
        conteos, cache, inesperados, ejemplos = Counter(), Counter(), [], {}
        n = 0
        while time.monotonic() < fin:
            ruta, esperado = rutas[n % len(rutas)]
            r = http(API + ruta)
            conteos[str(r["status"])] += 1
            if r["cache"]:
                cache[r["cache"]] += 1
            if r["status"] != esperado:
                inesperados.append({"ruta": ruta.replace(sesion, "{sesionId}"), "esperado": esperado, "status": r["status"]})
                break
            ejemplos[str(r["status"])] = {"ruta": ruta.replace(sesion, "{sesionId}"), "status": r["status"], "cache": r["cache"]}
            n += 1
            time.sleep(.5)
        return conteos, cache, inesperados, ejemplos

    inicio = fecha()
    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        resultados = list(ejecutor.map(lambda _: cliente(), range(2)))
    estados, caches, fallos, ejemplos = Counter(), Counter(), [], {}
    for c, h, f, e in resultados:
        estados.update(c)
        caches.update(h)
        fallos.extend(f)
        ejemplos.update(e)
    return {"inicio": inicio, "fin": fecha(), "duracion_programada_s": segundos,
            "estados_http": dict(estados), "cache": dict(caches), "inesperados": fallos,
            "ejemplos": ejemplos, "errores_deliberados": [404, 503] if caida else [404]}


def ejecutar(salida, falla):
    salida.mkdir(parents=True, exist_ok=False)
    resultado = {"inicio": fecha(), "completa": False, "falla_solicitada": falla,
                 "carga": {"clientes": 2, "pausa_por_cliente_s": .5, "timeout_s": 15}, "fases": {}}

    def guardar():
        (salida / "demostracion.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sesion, detenido = None, False
    comienzo = time.time()
    try:
        resultado["version"] = verificar(RAIZ.parent, "grupo13-hito10-api-1")
        if subprocess.check_output(["git", "diff", "HEAD", "--", str(RAIZ)], cwd=RAIZ, encoding="utf-8").strip():
            raise RuntimeError("El Hito 13 tiene cambios sin commit")
        if subprocess.check_output(["docker", "inspect", "--format", "{{.State.Running}}", REDIS], encoding="utf-8").strip() != "true":
            raise RuntimeError("Redis debe estar operativo antes de comenzar")
        resultado["funciones"] = {ruta: http(API + ruta) for ruta in (
            "/salud", "/equipos?tamanio=2", "/equipos/EQ-001", "/partidos/PAR-001",
            "/actas/PAR-001", "/partidos/PAR-001/estadisticas",
            "/partidos/PAR-001/comentarios?desde=2030-06-10T18:00:30Z&hasta=2030-06-10T18:02:10Z&limite=3")}
        if any(r["status"] != 200 for r in resultado["funciones"].values()):
            raise RuntimeError("Una función previa no respondió 200")
        r = http(API + "/sesiones", "POST", {"usuarioId": "USR-00001"})
        if r["status"] != 201:
            raise RuntimeError("No se pudo crear la sesión temporal")
        sesion = r["body"]["data"]["sesionId"]
        for nombre, segundos, caida in [("antes", 120, False), *([("durante", 105, True), ("despues", 135, False)] if falla else [])]:
            if caida:
                detenido = True
                subprocess.run(["docker", "stop", REDIS], check=True, capture_output=True, timeout=60)
            elif detenido:
                subprocess.run(["docker", "start", REDIS], check=True, capture_output=True, timeout=30)
                # Esperar PING de la misma instancia, sin recrearla ni alterar su volumen.
                for _ in range(30):
                    r = subprocess.run(["docker", "exec", REDIS, "redis-cli", "ping"], capture_output=True, text=True)
                    if r.returncode == 0 and r.stdout.strip() == "PONG":
                        break
                    time.sleep(1)
                else:
                    raise RuntimeError("Redis no se recuperó")
                detenido = False
            print(nombre, fecha(), flush=True)
            resultado["fases"][nombre] = carga(segundos, sesion, caida)
            resultado["fases"][nombre]["observacion"] = estado()
            guardar()
            if resultado["fases"][nombre]["inesperados"]:
                raise RuntimeError("Hubo respuestas inesperadas, revisar la evidencia")
        resultado["series"] = [{**q, "resultado": prom("/query_range", query=q["expr"], start=comienzo, end=time.time(), step="15s")} for q in consultas()]
        if any(not q["resultado"]["result"] for q in resultado["series"]):
            raise RuntimeError("Hay una consulta del dashboard sin series")
        resultado["completa"] = True
    except BaseException as error:
        resultado["fallo"] = type(error).__name__
        raise
    finally:
        if detenido:
            subprocess.run(["docker", "start", REDIS], check=True, capture_output=True, timeout=30)
        if sesion:
            resultado["cierre_sesion"] = http(API + f"/sesiones/{sesion}", "DELETE")["status"]
        resultado["fin"] = fecha()
        guardar()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", type=Path, required=True, help="Carpeta nueva para no reemplazar evidencias")
    p.add_argument("--falla-redis", action="store_true", help="Detener Redis 105 s y recuperarlo, conservando datos")
    a = p.parse_args()
    ejecutar(a.salida, a.falla_redis)
