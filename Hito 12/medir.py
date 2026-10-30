"""Carga concurrente acotada de GET comentarios y comparación de dos variantes."""

import argparse
import concurrent.futures
import ctypes
import http.client
import json
import math
import os
import platform
import re
import socket
import subprocess
import threading
import time
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from datos import RAIZ, config, instante, ordenados


def comando(args, timeout=20, entrada=None):
    r = subprocess.run(args, input=entrada, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"No se completó {args[0]} {args[1]}. Revisar el entorno sin publicar su configuración")
    return r.stdout


def resumen(valores):
    if not valores:
        return {"n": 0}
    v = sorted(valores)
    return {"n": len(v), "min_ms": round(v[0], 3), "promedio_ms": round(sum(v) / len(v), 3),
            **{f"p{p}_ms": round(v[math.ceil(len(v) * p / 100) - 1], 3) for p in (50, 95, 99)}}


def cursor(fila):
    return str(round(instante(fila["creadoEn"]).timestamp() * 1000)) + "_" + fila["comentarioId"]


def caso(c, partido, pagina):
    filas = ordenados(c, partido)
    inicio = pagina * c["limite"]
    parametros = {"desde": c["desde"], "hasta": c["hasta"], "limite": c["limite"]}
    if inicio:
        parametros["cursor"] = cursor(filas[inicio - 1])
    items = filas[inicio:inicio + c["limite"]]
    siguiente = cursor(items[-1]) if inicio + len(items) < len(filas) else None
    return {"nombre": f"{partido}-pagina{pagina + 1}",
            "ruta": f"/api/v1/partidos/{partido}/comentarios?" + urlencode(parametros),
            "items": items, "siguiente": siguiente, "partido": partido}


def validar_respuesta(c, prueba, cuerpo, rid, cabecera):
    if cabecera != rid or cuerpo["meta"]["requestId"] != rid:
        raise ValueError("Correlación distinta")
    datos = cuerpo["data"]
    if (datos["partidoId"] != prueba["partido"] or datos["items"] != prueba["items"]
            or datos["particiones"] != 20
            or instante(datos["desde"]) != instante(c["desde"])
            or instante(datos["hasta"]) != instante(c["hasta"])
            or cuerpo["meta"]["paginacion"]["siguienteCursor"] != prueba["siguiente"]):
        raise ValueError("Contenido, orden o cursor distinto al esperado")


def conexion(c):
    u = urlsplit(c["api_url"])
    if u.scheme != "http" or u.hostname not in ("127.0.0.1", "localhost"):
        raise ValueError("Solo API HTTP local")
    return http.client.HTTPConnection(u.hostname, u.port, timeout=c["timeout_s"])


def solicitud(c, conn, prueba, rid):
    t = time.perf_counter()
    estado, error, adaptador = 0, None, None
    try:
        conn.request("GET", prueba["ruta"], headers={"X-Request-ID": rid})
        respuesta = conn.getresponse()
        estado = respuesta.status
        cuerpo = json.loads(respuesta.read())
        if estado != 200:
            error = cuerpo.get("error", {}).get("codigo", "HTTP_NO_ESPERADO")
        else:
            validar_respuesta(c, prueba, cuerpo, rid, respuesta.getheader("X-Request-ID"))
            trazas = [t for t in cuerpo["meta"]["fuentes"] if t["fuente"] == "cassandra"]
            if len(trazas) != 1 or trazas[0]["resultado"] != "ok":
                raise ValueError("Falta la traza del adaptador")
            adaptador = trazas[0]["ms"]
    except (TimeoutError, socket.timeout):
        error = "TIMEOUT_CLIENTE"
        conn.close()
    except (OSError, http.client.HTTPException):
        error = "CONEXION_CLIENTE"
        conn.close()
    except (ValueError, KeyError, TypeError):
        error = "INTEGRIDAD_O_CONTRATO"
        conn.close()
    return {"request_id": rid, "caso": prueba["nombre"], "http": estado, "error": error,
            "cliente_ms": (time.perf_counter() - t) * 1000, "adaptador_ms": adaptador}


def integridad(c):
    """Recorre todas las páginas y compara cada atributo con un oráculo independiente."""
    resultados = {}
    with closing(conexion(c)) as conn:
        for partido in c["partidos"]:
            paginas = math.ceil(c["por_partido"] / c["limite"])
            for n in range(paginas):
                r = solicitud(c, conn, caso(c, partido, n), f"h12-integridad-{partido}-{n}")
                if r["error"]:
                    raise ValueError(f"Integridad fallida {partido}, página {n + 1}: {r['error']}")
            resultados[partido] = {"filas": c["por_partido"], "paginas": paginas, "atributos_y_orden": "OK"}
    return resultados


def fuente(c):
    # La configuración efectiva viaja por stdin, incluso si el JSON está fuera del montaje.
    salida = comando(["docker", "exec", "-i", c["contenedor_api"], "python", "/h12/datos.py",
                      "validar", "--config", "-"], 90, entrada=json.dumps(c))
    return json.loads(salida.strip().splitlines()[-1])


def memoria_generador():
    if os.name != "nt":
        return None
    from ctypes import wintypes
    class Contadores(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("fallos", wintypes.DWORD)] + [
            (n, ctypes.c_size_t) for n in ("pico", "actual", "pico_paginado", "paginado",
                                          "pico_no_paginado", "no_paginado", "pagefile", "pico_pagefile")]
    contadores = Contadores()
    contadores.cb = ctypes.sizeof(contadores)
    proceso = ctypes.windll.kernel32.GetCurrentProcess
    proceso.restype = wintypes.HANDLE
    obtener = ctypes.windll.psapi.GetProcessMemoryInfo
    obtener.argtypes = [wintypes.HANDLE, ctypes.POINTER(Contadores), wintypes.DWORD]
    obtener.restype = wintypes.BOOL
    if not obtener(proceso(), ctypes.byref(contadores), contadores.cb):
        return None
    return round(contadores.actual / 1048576, 3)


def medir_recursos(c, fin, muestras):
    while not fin.is_set():
        t = time.perf_counter()
        fecha = datetime.now(timezone.utc).isoformat()
        try:
            texto = comando(["docker", "stats", "--no-stream", "--format", "{{json .}}",
                             c["contenedor_api"], c["contenedor_cassandra"]], 8)
            for linea in texto.splitlines():
                v = json.loads(linea)
                muestras.append({"fecha": fecha, "contenedor": v["Name"], "cpu_pct": float(v["CPUPerc"].rstrip("%")),
                                 "memoria": v["MemUsage"], "memoria_pct": float(v["MemPerc"].rstrip("%")),
                                 "lectura_s": round(time.perf_counter() - t, 3)})
            if any(m.get("memoria_pct", 0) >= 90 for m in muestras[-2:]):
                fin.set()
        except (RuntimeError, subprocess.SubprocessError, ValueError, KeyError):
            muestras.append({"fecha": fecha, "error": "Muestreo de recursos incompleto"})
            fin.set()
        fin.wait(max(0, c["muestreo_s"] - (time.perf_counter() - t)))


def fase(c, casos, nombre, concurrencia, segundos, prefijo):
    inicio, cpu = time.perf_counter(), time.process_time()
    fin, bloqueo = threading.Event(), threading.Lock()
    filas, recursos, asignadas, fallas = [], [], 0, 0
    muestreador = threading.Thread(target=medir_recursos, args=(c, fin, recursos))
    muestreador.start()
    def cliente():
        nonlocal asignadas, fallas
        with closing(conexion(c)) as conn:
            while time.perf_counter() - inicio < segundos and not fin.is_set():
                with bloqueo:
                    if asignadas >= c["max_operaciones"]:
                        fin.set()
                        break
                    n = asignadas
                    asignadas += 1
                r = solicitud(c, conn, casos[n % len(casos)], f"{prefijo}-{nombre}-{n}")
                with bloqueo:
                    filas.append(r)
                    fallas += bool(r["error"])
                    if r["error"] == "INTEGRIDAD_O_CONTRATO" or fallas >= c["max_errores"]:
                        fin.set()
    fallo_proceso = None
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrencia) as pool:
        trabajos = [pool.submit(cliente) for _ in range(concurrencia)]
        try:
            for trabajo in trabajos:
                trabajo.result()
        except (Exception, KeyboardInterrupt) as error:
            fallo_proceso = type(error).__name__
            fin.set()
    duracion = time.perf_counter() - inicio
    cpu_pct = 100 * (time.process_time() - cpu) / duracion
    interrumpida = fin.is_set()
    fin.set()
    muestreador.join(timeout=10)
    errores = Counter(r["error"] for r in filas if r["error"])
    try:
        memoria = memoria_generador()
    except (OSError, ctypes.ArgumentError) as error:
        memoria, fallo_proceso, interrumpida = None, type(error).__name__, True
    return {"fase": nombre, "concurrencia": concurrencia, "programada_s": segundos, "duracion_s": round(duracion, 4),
            "intentadas": len(filas), "exitosas": len(filas) - fallas, "fallidas": fallas,
            "timeouts": sum(r["error"] in ("TIMEOUT_CLIENTE", "DEPENDENCIA_TIMEOUT") for r in filas),
            "errores": dict(errores), "tasa_error_pct": round(100 * fallas / len(filas), 3) if filas else None,
            "throughput_ok_s": round((len(filas) - fallas) / duracion, 3),
            "cliente": resumen([r["cliente_ms"] for r in filas]),
            "adaptador": resumen([r["adaptador_ms"] for r in filas if r["adaptador_ms"] is not None]),
            "distribucion": dict(Counter(r["caso"] for r in filas)),
            "generador_cpu_pct": round(cpu_pct, 3), "generador_memoria_mib": memoria,
            "recursos": recursos, "interrumpida": interrumpida, "fallo_proceso": fallo_proceso,
            "asignadas": asignadas, "sin_resultado": asignadas - len(filas)}, filas


def entorno(c):
    info = json.loads(comando(["docker", "info", "--format", "{{json .}}"] ))
    contenedores = []
    for nombre in (c["contenedor_api"], c["contenedor_cassandra"]):
        d = json.loads(comando(["docker", "inspect", nombre]))[0]
        if not d["State"]["Running"]:
            raise RuntimeError(f"Contenedor detenido: {nombre}")
        contenedores.append({"nombre": nombre, "imagen": d["Config"]["Image"], "image_id": d["Image"],
                             "cpu_limite": d["HostConfig"]["NanoCpus"] / 1e9,
                             "memoria_limite_bytes": d["HostConfig"]["Memory"]})
    versiones = comando(["docker", "exec", c["contenedor_api"], "python", "-c",
                        "import json,sys; from importlib.metadata import version; from app.main import VERSION; print(json.dumps({'api':VERSION,'python':sys.version.split()[0], **{n:version(n) for n in ('fastapi','uvicorn','cassandra-driver')}}))"])
    return {"docker": info["ServerVersion"], "cpu_docker": info["NCPU"], "memoria_docker_bytes": info["MemTotal"],
            "generador": platform.platform(), "python_generador": platform.python_version(),
            "cpu_logicas_host": os.cpu_count(), "versiones_api": json.loads(versiones), "contenedores": contenedores}


def ejecutar(c, variante, humo, archivo=None):
    fecha = datetime.now().astimezone().isoformat()
    prefijo = "h12-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    resultado = {"fecha": fecha, "variante": variante, "humo": humo, "config": c,
                 "fases": [], "fallos": [], "integridad": "no comprobada", "completa": False}

    def guardar():
        if archivo:
            archivo.seek(0)
            json.dump(resultado, archivo, ensure_ascii=False, indent=2)
            archivo.write("\n")
            archivo.truncate()
            archivo.flush()

    def registrar_fallo(etapa, error):
        resultado["fallos"].append({"etapa": etapa, "tipo": type(error).__name__,
                                    "detalle": "Etapa no completada. Conservar el registro y revisar esa comprobación. No se publican mensajes crudos."})
    fases = [("humo", 1, 2)] if humo else [
        ("calentamiento", c["concurrencias"][0], c["calentamiento_s"]),
        *[(f"rampa{n}", n, c["rampa_s"]) for n in c["concurrencias"][:-1]],
        ("sostenimiento", c["concurrencias"][-1], c["sostenimiento_s"])]
    filas, etapa = [], "version"
    guardar()
    try:
        git = ["git", "-C", str(Path(__file__).resolve().parents[1])]
        resultado["commit_base"] = comando([*git, "rev-parse", "HEAD"]).strip()
        resultado["cambios_locales"] = comando([*git, "status", "--porcelain", "--", "Hito 10", "Hito 11", "Hito 12", "readme.md"]).strip().splitlines()
        for etapa, funcion in (("entorno", entorno), ("fuente_antes", fuente), ("api_antes", integridad)):
            resultado[etapa] = funcion(c)
            guardar()
        # Ciclo determinista: 75% PAR-001, 25% PAR-002, cuatro primeras páginas por partido.
        casos = [caso(c, partido, pagina) for partido in (c["partidos"][0],) * 3 + (c["partidos"][1],)
                 for pagina in (0, 1, 2, 3)]
        for nombre, concurrencia, segundos in fases:
            etapa = nombre
            r, nuevas = fase(c, casos, nombre, concurrencia, segundos, prefijo)
            resultado["fases"].append(r)
            filas.extend(nuevas)
            guardar()
            print(f"{nombre}: {r['intentadas']} solicitudes, {r['fallidas']} fallidas, P95={r['cliente'].get('p95_ms')} ms", flush=True)
            if r["interrumpida"] or r["fallidas"]:
                break
    except (Exception, KeyboardInterrupt) as error:
        registrar_fallo(etapa, error)
    if filas:
        try:
            logs = subprocess.run(["docker", "logs", "--since", fecha, c["contenedor_api"]], capture_output=True,
                                  text=True, encoding="utf-8", timeout=20)
            if logs.returncode:
                raise RuntimeError("Logs no disponibles")
            patron = re.compile(r"req=(" + prefijo + r"-[a-z0-9]+-\d+) (metodo=GET ruta=/api/v1/partidos/PAR-00[12]/comentarios estado=\d+|dep=cassandra op=listar_ventana resultado=[\w:]+) ms=([0-9.]+)$")
            seguros = [m.groups() for linea in (logs.stdout + logs.stderr).splitlines() if (m := patron.search(linea))]
            http = {rid: float(ms) for rid, tipo, ms in seguros if tipo.startswith("metodo")}
            dep = {rid for rid, tipo, ms in seguros if tipo.startswith("dep")}
            for r in resultado["fases"]:
                propias = [f for f in filas if f["request_id"].startswith(prefijo + "-" + r["fase"] + "-")]
                r["api_log"] = resumen([http[f["request_id"]] for f in propias if f["request_id"] in http])
                r["correlacion_completa"] = all(f["request_id"] in http and f["request_id"] in dep for f in propias)
            resultado["logs_ejemplo"] = ["req=" + rid + " " + tipo + " ms=" + ms for rid, tipo, ms in seguros[:4]]
        except (Exception, KeyboardInterrupt) as error:
            registrar_fallo("logs", error)
    if "fuente_antes" in resultado:
        for etapa, funcion in (("fuente_despues", fuente), ("api_despues", integridad)):
            try:
                resultado[etapa] = funcion(c)
            except (Exception, KeyboardInterrupt) as error:
                registrar_fallo(etapa, error)
            guardar()
    if all(k in resultado for k in ("fuente_antes", "api_antes", "fuente_despues", "api_despues")):
        resultado["integridad"] = "OK"
    resultado["completa"] = (not resultado["fallos"] and resultado["integridad"] == "OK"
        and len(resultado["fases"]) == len(fases) and all(
        not r["interrumpida"] and not r["fallidas"] and not r["sin_resultado"]
        and r.get("correlacion_completa", False) and r["recursos"]
        and not any("error" in m for m in r["recursos"]) for r in resultado["fases"]))
    guardar()
    return resultado


def comparar(rutas):
    ejecuciones = [json.loads(p.read_text(encoding="utf-8")) for p in rutas]
    if any(e["config"] != ejecuciones[0]["config"] or e["humo"] or not e["completa"] for e in ejecuciones):
        raise ValueError("Comparar ejecuciones completas del mismo escenario, sin incluir humo")
    print("| Variante | Fecha | N | P50 ms | P95 ms | P99 ms | OK/s | Errores |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for e in ejecuciones:
        f = e["fases"][-1]
        print(f"| {e['variante']} | {e['fecha']} | {f['intentadas']} | {f['cliente']['p50_ms']} | {f['cliente']['p95_ms']} | {f['cliente']['p99_ms']} | {f['throughput_ok_s']} | {f['fallidas']} |")


def principal():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=RAIZ / "config.ejemplo.json")
    p.add_argument("--variante", choices=("base", "optimizada"), default="base")
    p.add_argument("--humo", action="store_true")
    p.add_argument("--salida", type=Path)
    p.add_argument("--comparar", type=Path, nargs="+")
    a = p.parse_args()
    if a.comparar:
        comparar(a.comparar)
        return
    if not a.salida or a.salida.exists():
        p.error("Indicar --salida con un archivo nuevo para conservar las evidencias")
    c = config(a.config)
    if (not 0 < c["timeout_s"] <= 5 or not 0 < c["sostenimiento_s"] <= 30
            or not 0 < c["calentamiento_s"] <= 10 or not 0 < c["rampa_s"] <= 5
            or c["concurrencias"] != sorted(set(c["concurrencias"]))
            or len(c["concurrencias"]) > 3 or min(c["concurrencias"]) < 1 or max(c["concurrencias"]) > 8
            or not 1 <= c["max_operaciones"] <= 10000 or not 1 <= c["max_errores"] <= 10
            or not 2 <= c["muestreo_s"] <= 5 or c["por_partido"] < 4 * c["limite"]):
        p.error("Escenario fuera de los límites acotados del módulo")
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    with a.salida.open("x", encoding="utf-8") as f:
        resultado = ejecutar(c, a.variante, a.humo, f)
    print("Integridad:", resultado["integridad"], "Evaluación completa:", resultado["completa"])
    raise SystemExit(0 if resultado["completa"] else 2)


if __name__ == "__main__":
    principal()
