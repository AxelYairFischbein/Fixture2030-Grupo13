"""Diagnóstico de lectura. PowerShell lo inicia, los drivers corren dentro de la API."""

import argparse
import json
import logging
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

PRODUCTOS = ("mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris")


class ContextoAusente(Exception):
    """La colección esperada no está presente en la database seleccionada."""


PASOS = {
    "host_no_resuelto": "Revisar el nombre y la red desde la API.",
    "conexion_rechazada": "Revisar listener, estado y puerto publicado del contenedor identificado.",
    "timeout": "Comparar TCP y driver, revisar ruta y carga del servicio. No aumentar el tiempo sin diagnosticar.",
    "autenticacion": "Revisar la credencial local y su mecanismo sin imprimirla.",
    "autorizacion": "Revisar los permisos mínimos de lectura de esa identidad.",
    "contexto": "Revisar database, colección, keyspace, tabla o namespace. No cargar datos automáticamente.",
    "consulta": "Contrastar la consulta fija y el esquema existente.",
    "no_disponible": "Contrastar la prueba de driver con TCP y configuración.",
    "desconocido": "Revisar el tipo de error y el contexto antes de atribuir una causa.",
    "configuracion": "Completar la configuración local o instalar las dependencias del Hito 10.",
}


def diagnostico(error):
    """Solo clasifica señales conocidas. Nunca publica mensajes crudos del driver."""
    from app.contexto import es_timeout
    from app.errors import ApiError
    if isinstance(error, ApiError) and error.__context__ is not None:
        error = error.__context__
    tipo = type(error).__name__
    codigo = getattr(error, "code", None)
    if isinstance(error, ContextoAusente):
        causa = "contexto"
    elif isinstance(error, socket.gaierror):
        causa = "host_no_resuelto"
    elif isinstance(error, ConnectionRefusedError):
        causa = "conexion_rechazada"
    elif es_timeout(error):
        causa = "timeout"
    elif tipo in {"AuthenticationError", "AuthenticationFailed", "AuthError"} or codigo == 18:
        causa = "autenticacion"
    elif tipo in {"AuthorizationError", "NoPermissionError", "Unauthorized", "Forbidden"} or codigo == 13:
        causa = "autorizacion"
    elif isinstance(codigo, str) and codigo.endswith(("DatabaseNotFound", "EntityNotFound")):
        causa = "contexto"
    elif isinstance(codigo, str) and codigo.endswith(("SyntaxError", "TypeError", "SemanticError")):
        causa = "consulta"
    elif tipo == "HTTPStatusError":
        causa = {401: "autenticacion", 403: "autorizacion", 404: "contexto", 400: "consulta"}.get(
            error.response.status_code, "no_disponible")
    elif tipo == "InvalidRequest":
        # El texto se usa para reconocer el error, no se incluye en la evidencia.
        causa = "contexto" if re.search(r"(keyspace.*does not exist|unconfigured table)", str(error), re.I) else "consulta"
    elif tipo in {"ConfigurationError", "ModuleNotFoundError", "FileNotFoundError"}:
        causa = "configuracion"
    elif tipo in {"NoHostAvailable", "ConnectionError", "ServiceUnavailable", "AutoReconnect", "ConnectError"}:
        causa = "no_disponible"
    else:
        causa = "desconocido"
    return causa, tipo


def fila(etapa, estado, detalle, ms=0, **extra):
    registro = {"etapa": etapa, "resultado": estado, "detalle": detalle,
                "ms": round(ms, 2), **extra}
    print(json.dumps(registro, ensure_ascii=False), flush=True)


def probar(etapa, funcion):
    inicio = time.perf_counter()
    try:
        detalle = funcion()
        fila(etapa, "OK", detalle, (time.perf_counter() - inicio) * 1000)
        return True
    except Exception as error:
        causa, tipo = diagnostico(error)
        fila(etapa, "SKIP" if causa == "configuracion" else "FAIL",
             f"{causa}, tipo={tipo}. {PASOS[causa]}", (time.perf_counter() - inicio) * 1000,
             diagnostico=causa)
        return False


def destino(producto, c):
    if producto == "mongodb":
        return c.mongo_host, c.mongo_port, c.mongo_db + ".equipos", bool(c.mongo_user)
    if producto == "neo4j":
        u = urlsplit(c.neo4j_uri)
        return u.hostname, u.port or 7687, c.neo4j_database, bool(c.neo4j_user and c.neo4j_password)
    if producto == "cassandra":
        return c.cassandra_hosts[0], c.cassandra_port, c.cassandra_keyspace + ".comentarios_por_partido", False
    if producto == "redis":
        return c.redis_host, c.redis_port, "db=0, prefijo=" + c.redis_prefix, bool(c.redis_password)
    if producto == "influxdb":
        u = urlsplit(c.influx_url)
        return u.hostname, u.port or (443 if u.scheme == "https" else 80), c.influx_db, bool(c.influx_token)
    return c.iris_host, c.iris_port, c.iris_namespace + ".FixtureH9.Partido", bool(c.iris_user and c.iris_password)


def adaptador(producto, c):
    # Importar solo el producto elegido permite probarlo aunque falte otro driver.
    from importlib import import_module
    modulo, clase = {
        "mongodb": ("mongo_equipos", "MongoEquipos"), "neo4j": ("neo4j_partidos", "Neo4jPartidos"),
        "cassandra": ("cassandra_comentarios", "CassandraComentarios"), "redis": ("redis_kv", "RedisKV"),
        "influxdb": ("influx_estadisticas", "InfluxEstadisticas"), "iris": ("iris_actas", "IrisActas"),
    }[producto]
    return getattr(import_module("app.adapters." + modulo), clase)(c)


def lectura(producto, a, c, p):
    if producto == "mongodb":
        if "equipos" not in a._db.list_collection_names(filter={"name": "equipos"}):
            raise ContextoAusente()
        fila("contexto", "OK", "Colección equipos existente y accesible en " + c.mongo_db)
        doc = a.buscar_equipo(p["equipo_id"])
        return "find_one equipo=" + p["equipo_id"] + (", documento encontrado" if doc else ", ausencia válida")
    if producto == "neo4j":
        doc = a.partido(p["partido_id"])
        eventos = a.eventos(p["partido_id"], p["limite"]) if doc else []
        return f"Cypher parametrizado, partido={p['partido_id']}, encontrado={bool(doc)}, eventos={len(eventos)}, limite={p['limite']}"
    if producto == "cassandra":
        from app.services import minutos_de_ventana
        desde, hasta = (instante(p[k]) for k in ("comentarios_desde", "comentarios_hasta"))
        filas = a.listar(p["partido_id"], minutos_de_ventana(desde, hasta), desde, hasta, p["limite"], None)
        return f"partido={p['partido_id']}, [{p['comentarios_desde']}, {p['comentarios_hasta']}), 4 segmentos, filas={len(filas)}, limite={p['limite']}"
    if producto == "redis":
        # Clave conocida de demostración. No hace falta enumerar la base.
        clave = p["redis_clave"]
        tipo = a._r.type(clave)
        if tipo == "hash":
            a._r.hget(clave, "estado")
        elif tipo == "string":
            a._r.getrange(clave, 0, 255)
        elif tipo == "zset":
            a._r.zrange(clave, 0, 2)
        ttl = a._r.ttl(clave)
        fila("memoria", "OK", "Política=" + str(a._r.config_get("maxmemory-policy").get("maxmemory-policy")))
        if tipo == "none":
            fila("muestra", "WARN", "No existe la clave de demostración configurada. No se creó una. Ausencia no demuestra expiración.")
        return f"clave={clave}, tipo={tipo}, TTL={ttl}. Sin renovar TTL ni mostrar valores."
    if producto == "influxdb":
        desde, hasta = instante(p["influx_desde"]), instante(p["influx_hasta"])
        filas = a.resumen(p["partido_id"], p["equipo_id"], desde, hasta, "1m", 6)
        return f"DATE_BIN 1m, partido={p['partido_id']}, equipo={p['equipo_id']}, [{p['influx_desde']}, {p['influx_hasta']}), intervalos={len(filas)}. Cero puntos es válido."
    doc = a.acta(p["acta_codigo"])
    return f"FixtureH9.Partido codigo={p['acta_codigo']}, encontrado={bool(doc)}, eventos={len(doc['eventos']) if doc else 0}"


def seguridad(producto, a, c, p):
    """Inspección de identidad y permisos sin alterar usuarios ni ejecutar escrituras."""
    def comprobar(etapa, consulta):
        inicio = time.perf_counter()
        try:
            verificada, detalle = consulta()
        except Exception as error:
            # Un permiso de inspección ausente no implica que la lectura esté prohibida.
            causa, tipo = diagnostico(error)
            verificada, detalle = False, f"Inspección no completada: {causa}, tipo={tipo}. {PASOS[causa]}"
        fila(etapa, "OK" if verificada else "WARN", detalle,
             (time.perf_counter() - inicio) * 1000, verificada_independientemente=verificada)

    def identidad():
        if producto == "mongodb":
            info = a._db.command("connectionStatus")["authInfo"]
            coincide = any(u["user"] == c.mongo_user and u["db"] == "admin"
                           for u in info["authenticatedUsers"])
            return coincide, "connectionStatus: identidad autenticada coincide con la configurada." if coincide else (
                "Autenticación no verificada independientemente. connectionStatus no confirmó la identidad configurada.")
        if producto == "neo4j":
            filas = a._leer("SHOW CURRENT USER YIELD user RETURN user")
            coincide = len(filas) == 1 and filas[0]["user"] == c.neo4j_user
            return coincide, "SHOW CURRENT USER: identidad coincide con la configurada." if coincide else (
                "Autenticación no verificada independientemente. No se confirmó la identidad configurada.")
        if producto == "redis":
            usuario = a._r.acl_whoami()
            coincide = bool(c.redis_password) and usuario == "default"
            return coincide, (
                "ACL WHOAMI: identidad default confirmada en la conexión con credencial del adaptador." if coincide else
                "ACL WHOAMI: identidad efectiva consultada. Autenticación por credencial no verificada independientemente. No se deduce que esté deshabilitada.")
        return False, "Autenticación no verificada independientemente. El cliente del módulo no inspecciona la identidad autenticada. Una operación aceptada solo acredita acceso funcional."

    def permiso():
        if producto == "mongodb":
            info = a._db.command("connectionStatus", showPrivileges=True)["authInfo"]
            for privilegio in info["authenticatedUserPrivileges"]:
                recurso = privilegio["resource"]
                aplica = recurso.get("anyResource") or (
                    "db" in recurso and recurso["db"] in ("", c.mongo_db)
                    and recurso.get("collection") in ("", "equipos"))
                if aplica and "find" in privilegio["actions"]:
                    return True, f"connectionStatus: privilegio find sobre {c.mongo_db}.equipos. No evalúa escrituras ni otras colecciones."
            return False, "Autorización no verificada independientemente. La inspección no confirmó find sobre equipos. Contrastar con la lectura, sin inferir una denegación."
        if producto == "redis":
            usuario = a._r.acl_whoami()
            permitido = a._r.execute_command("ACL", "DRYRUN", usuario, "GET", p["redis_clave"]) == "OK"
            return permitido, "ACL DRYRUN: permiso GET para la clave configurada, sin ejecutar GET. No verifica otros comandos ni la existencia de la clave."
        return False, "Autorización no verificada independientemente. No se inspeccionan permisos efectivos por recurso. La lectura se registra por separado y no acredita otras operaciones."

    comprobar("autenticacion", identidad)
    comprobar("autorizacion", permiso)


def clientes(producto, c, p):
    import httpx
    host, _, _, autenticado = destino(producto, c)
    portal = {"neo4j": f"http://{host}:7474/", "iris": f"http://{host}:52773/csp/sys/UtilHome.csp",
              "influxdb": c.influx_url.rstrip("/") + "/health"}.get(producto)
    if portal:
        def http():
            r = httpx.get(portal, timeout=p["timeout_http"], follow_redirects=False)
            return f"HTTP {r.status_code}. Solo accesibilidad HTTP, no acredita acceso a datos."
        probar("http_auxiliar", http)
        if producto == "influxdb" and c.influx_token:
            def salud_autorizada():
                r = httpx.get(portal, headers={"Authorization": "Bearer " + c.influx_token}, timeout=p["timeout_http"])
                r.raise_for_status()
                return f"Health HTTP {r.status_code} con token. La consulta posterior verifica database y tabla."
            probar("health_autorizado", salud_autorizada)
    if producto in {"neo4j", "influxdb", "iris"} and not autenticado:
        fila("autenticacion", "SKIP", "Falta la credencial local requerida. No se intenta adivinarla.")
        return
    a = adaptador(producto, c)
    if not probar("protocolo", lambda: (a.ping(), "Driver completó ping/lectura constante en el contexto configurado.")[1]):
        return
    seguridad(producto, a, c, p)
    if producto != "mongodb":
        fila("contexto", "OK", destino(producto, c)[2] + ". Contexto utilizado por el driver, no por el portal.")
    probar("lectura", lambda: lectura(producto, a, c, p))


def instante(texto):
    valor = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    if valor.tzinfo is None:
        raise ValueError("La ventana debe indicar zona horaria")
    return valor.astimezone(timezone.utc)


def rutas(producto, p):
    base = "/api/v1"
    if producto == "mongodb":
        return [(base + "/equipos", {"tamanio": p["limite"]}),
                (base + "/equipos/EQ-999/jugadores", {"tamanio": 1}),
                (base + "/equipos", {"tamanio": 0})]
    if producto == "neo4j":
        return [(base + "/partidos/" + p["partido_id"], {"limiteEventos": p["limite"]})]
    if producto == "cassandra":
        return [(base + "/partidos/" + p["partido_id"] + "/comentarios",
                 {"desde": p["comentarios_desde"], "hasta": p["comentarios_hasta"], "limite": p["limite"]})]
    if producto == "redis":
        return [(base + "/sesiones/" + p["sesion_id"], {})]
    if producto == "influxdb":
        return [(base + "/partidos/" + p["partido_id"] + "/estadisticas",
                 {"equipoId": p["equipo_id"], "desde": p["influx_desde"], "hasta": p["influx_hasta"], "intervalo": "1m"})]
    return [(base + "/actas/" + p["acta_codigo"], {})]


def api(producto, p):
    import httpx
    for n, (ruta, params) in enumerate(rutas(producto, p)):
        rid = f"{p['request_prefix']}-{producto}-{n}"
        inicio = time.perf_counter()
        try:
            r = httpx.get(p["api_url"] + ruta, params=params, headers={"X-Request-ID": rid}, timeout=p["timeout_http"])
            cuerpo = r.json()
            datos = cuerpo.get("data")
            codigo = cuerpo.get("error", {}).get("codigo")
            resumen = codigo or (f"items={len(datos)}" if isinstance(datos, list) else
                                 f"items={len(datos.get('items', datos.get('puntos', datos.get('eventos', []))))}" if isinstance(datos, dict) else "sin datos")
            validacion = producto == "mongodb" and n == 2
            valido = (r.status_code == 400 and codigo == "VALIDACION_FALLIDA") if validacion else (
                r.status_code == 200 or (r.status_code == 404 and codigo in {"RECURSO_NO_ENCONTRADO", "SESION_NO_VIGENTE"}))
            if r.headers.get("X-Request-ID") != rid:
                valido = False
                resumen += ", correlación ausente o distinta"
            fila("api_validacion" if validacion else "api", "OK" if valido else "FAIL",
                 f"GET {ruta} params={json.dumps(params)} HTTP={r.status_code} {resumen}",
                 (time.perf_counter() - inicio) * 1000, request_id=rid, http=r.status_code)
        except Exception as error:
            causa, tipo = diagnostico(error)
            fila("api", "FAIL", f"GET {ruta}: {causa}, tipo={tipo}. No se obtuvo una respuesta interpretable. {PASOS[causa]}",
                 (time.perf_counter() - inicio) * 1000, request_id=rid)


def trabajador(producto, etapa, p):
    sys.path.insert(0, "/app")
    logging.disable(logging.CRITICAL)
    from app.config import cargar
    c = cargar()
    host, puerto, contexto, credencial = destino(producto, c)
    if etapa == "configuracion":
        from importlib.metadata import version
        paquete = dict(zip(PRODUCTOS, ("pymongo", "neo4j", "cassandra-driver", "redis", "httpx", "intersystems-irispython")))[producto]
        protocolo = dict(zip(PRODUCTOS, ("MongoDB wire", "Bolt", "CQL", "RESP", "HTTP", "Superserver")))[producto]
        fila(etapa, "OK", f"host={host} puerto={puerto} protocolo={protocolo} contexto={contexto} credencial_configurada={credencial} timeout_driver={c.timeout}s driver={paquete}/{version(paquete)} Python={sys.version.split()[0]}")
    elif etapa == "tcp":
        if probar("dns", lambda: f"{host}: {len(socket.getaddrinfo(host, puerto, type=socket.SOCK_STREAM))} direcciones resueltas"):
            def tcp():
                with socket.create_connection((host, puerto), timeout=p["timeout_tcp"]):
                    return f"{host}:{puerto} acepta TCP. No acredita protocolo ni identidad."
            probar("tcp", tcp)
    elif etapa == "clientes":
        clientes(producto, c, p)
    elif etapa == "api":
        api(producto, p)


# El supervisor corre dentro de la API y termina su proceso hijo al vencer el plazo.
# No basta con cerrar docker exec en Windows, porque dejaría la consulta ejecutándose.
SUPERVISOR = '''import subprocess,sys,json
fuente=sys.stdin.read()
p=subprocess.Popen([sys.executable,"-c",fuente,*sys.argv[2:]],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
try:
    salida,_=p.communicate(timeout=float(sys.argv[1]))
    print(salida,end="")
    if p.returncode:
        print(json.dumps({"etapa":"ejecucion","resultado":"FAIL","detalle":"Proceso de prueba fallido. Revisar configuración o código, sin atribuirlo al servidor.","ms":0}))
except subprocess.TimeoutExpired:
    p.kill()
    salida,_=p.communicate()
    print(salida,end="")
    print(json.dumps({"etapa":"plazo_total","resultado":"FAIL","detalle":"Tiempo total de etapa agotado. Proceso de diagnóstico terminado, causa no determinada.","ms":float(sys.argv[1])*1000}))
'''


def estado_producto(registros):
    """Estado observado de acceso al producto, separado de las pruebas que faltan."""
    accesos = [r for r in registros if r["etapa"] in {"lectura", "api"} and r["resultado"] == "OK"]
    fallas = [r for r in registros if r["resultado"] == "FAIL" and (
        (r["etapa"] in {"dns", "tcp", "protocolo", "contexto", "lectura", "autenticacion", "autorizacion"}
         and r.get("diagnostico") not in {"desconocido", "configuracion"})
        or (r["etapa"] == "api" and r.get("http") in {503, 504}))]
    if fallas:
        return "degradado" if accesos else "no disponible"
    if accesos:
        return "disponible"
    if registros and all(r["resultado"] == "SKIP" or r["etapa"] == "configuracion" for r in registros):
        return "no probado"
    return "desconocido"


def evaluacion_completa(registros, modo):
    requeridas = {"configuracion"}
    if modo in {"completo", "tcp"}:
        requeridas |= {"dns", "tcp"}
    if modo in {"completo", "clientes"}:
        requeridas |= {"protocolo", "lectura", "autenticacion", "autorizacion"}
    if modo in {"completo", "api"}:
        requeridas |= {"api", "logs"}
    return requeridas <= {r["etapa"] for r in registros} and not any(
        r["resultado"] == "SKIP" or r["etapa"] in {"ejecucion", "plazo_total"}
        or (r["etapa"] in {"autenticacion", "autorizacion"}
            and r.get("verificada_independientemente") is not True) for r in registros)


def verificar_logs(texto, prefijo, registros, producto):
    """Exige log HTTP y de dependencia por request, salvo validación previa al driver."""
    patron = re.compile(r"req=" + re.escape(prefijo) + r"-[a-z0-9-]+ (?:dep=[a-z0-9]+ op=[a-z_]+ resultado=[a-zA-Z0-9_:]+ ms=[0-9.]+|metodo=GET ruta=/[A-Za-z0-9/_-]+ estado=[0-9]+ ms=[0-9.]+|error_interno tipo=[A-Za-z0-9_]+)$")
    logs = [m.group() for line in texto.splitlines() if (m := patron.search(line))]
    controles = []
    for r in registros:
        if not r.get("request_id"):
            continue
        propios = [line for line in logs if line.startswith("req=" + r["request_id"] + " ")]
        encontrado = any(" metodo=GET " in line for line in propios)
        if r["etapa"] != "api_validacion":
            encontrado = encontrado and any(" dep=" + producto + " " in line for line in propios)
        controles.append({"etapa": "logs", "resultado": "OK" if encontrado else "SKIP", "ms": 0,
                          "detalle": "Correlación HTTP/dependencia comprobada." if encontrado else
                          "Correlación incompleta. Revisar acceso a docker logs y configuración de logging. No prueba caída de la base.",
                          "request_id": r["request_id"]})
    if not controles:
        controles.append({"etapa": "logs", "resultado": "SKIP", "ms": 0,
                          "detalle": "No hubo request verificable. Repetir la etapa API antes de evaluar sus logs."})
    return logs, controles


def codigo_salida(por_producto, modo):
    if not all(evaluacion_completa(registros, modo) for registros in por_producto.values()):
        return 2
    return 1 if any(r["resultado"] == "FAIL" for registros in por_producto.values() for r in registros) else 0


def principal():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modo", choices=("completo", "tcp", "clientes", "api"), default="completo")
    parser.add_argument("--producto", choices=PRODUCTOS)
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "config/ejemplo.json")
    parser.add_argument("--salida", type=Path, help="Archivo UTF-8 nuevo. Nunca sobrescribe una evidencia.")
    args = parser.parse_args()
    p = json.loads(args.config.read_text(encoding="utf-8-sig"))
    ahora = datetime.now(timezone.utc)
    if p["influx_desde"] is None and p["influx_hasta"] is None:
        hasta = ahora.replace(second=0, microsecond=0)
        p["influx_desde"], p["influx_hasta"] = (d.isoformat() for d in (hasta - timedelta(minutes=5), hasta))
    for d, h in (("comentarios_desde", "comentarios_hasta"), ("influx_desde", "influx_hasta")):
        assert timedelta(0) < instante(p[h]) - instante(p[d]) <= timedelta(minutes=5), "Usar ventanas de hasta cinco minutos"
    assert 1 <= p["limite"] <= 5
    assert all(0 < p[k] <= 30 for k in ("timeout_tcp", "timeout_http", "timeout_etapa"))
    assert p["redis_clave"].startswith("fixture2030:"), "Usar una clave de demostración del Fixture"
    assert urlsplit(p["api_url"]).hostname in {"127.0.0.1", "localhost"}, "API evaluada dentro de su propio contenedor"
    p["request_prefix"] = "h11-" + ahora.strftime("%Y%m%dT%H%M%S")
    if args.salida and args.salida.exists():
        parser.error("La evidencia existe. Elegir otro nombre para conservarla.")
    raiz = Path(__file__).resolve().parents[1]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=raiz, text=True).strip()
    pendientes = subprocess.check_output(["git", "status", "--porcelain", "--", "Hito 10", "Hito 11"], cwd=raiz, text=True)
    lineas = ["# Hito 11 - Ejecución de conectividad", "", f"Fecha UTC: {ahora.isoformat()}",
              f"Fecha local del lanzador: {ahora.astimezone().isoformat()}",
              f"Commit base: {commit}. Cambios locales del módulo: {bool(pendientes)}.",
              f"Origen de conexiones: contenedor {p['contenedor_api']}. Lanzador: PowerShell/Python en Windows.",
              f"Modo: {args.modo}. Sin cargas ni escrituras del dominio.", ""]
    productos = [args.producto] if args.producto else PRODUCTOS
    por_producto = {producto: [] for producto in productos}
    logs = []
    try:
        info = json.loads(subprocess.check_output(["docker", "inspect", p["contenedor_api"]], stderr=subprocess.DEVNULL, timeout=10))[0]
        assert info["State"]["Running"], "API detenida"
        assert info["Config"]["Labels"].get("com.docker.compose.service") == "api", "No es el servicio API"
        lineas.append(f"Imagen API: {info['Config']['Image']}. Docker Engine: " + subprocess.check_output(
            ["docker", "version", "--format", "{{.Server.Version}}"], text=True, timeout=10).strip())
        fuente = Path(__file__).read_text(encoding="utf-8")
        for producto in productos:
            etapas = ["configuracion"] + (["tcp", "clientes", "api"] if args.modo == "completo" else [args.modo])
            registros = por_producto[producto]
            for etapa in etapas:
                try:
                    r = subprocess.run(["docker", "exec", "-i", p["contenedor_api"], "python", "-c", SUPERVISOR,
                                        str(p["timeout_etapa"]), "--worker", producto, etapa, json.dumps(p)],
                                       input=fuente, capture_output=True, text=True, encoding="utf-8", timeout=p["timeout_etapa"] + 10)
                    filas = [json.loads(line) for line in r.stdout.splitlines() if line.startswith("{")]
                    if r.returncode or not filas:
                        raise RuntimeError("docker exec incompleto")
                except (subprocess.SubprocessError, OSError, ValueError, RuntimeError) as error:
                    filas = [{"etapa": etapa, "resultado": "SKIP", "detalle":
                              f"Herramienta no completó la prueba, tipo={type(error).__name__}. Revisar acceso a Docker. No demuestra una caída de la base.", "ms": 0}]
                registros.extend(filas)
        if args.modo in {"completo", "api"}:
            try:
                r = subprocess.run(["docker", "logs", "--since", ahora.isoformat(), p["contenedor_api"]],
                                   capture_output=True, text=True, encoding="utf-8", timeout=10)
                texto = r.stdout + r.stderr if r.returncode == 0 else ""
            except (subprocess.SubprocessError, OSError):
                texto = ""
            for producto, registros in por_producto.items():
                logs, controles = verificar_logs(texto, p["request_prefix"], registros, producto)
                registros.extend(controles)
    except (subprocess.SubprocessError, OSError, AssertionError) as error:
        lineas += ["", f"Entorno no evaluable: {type(error).__name__}. Revisar Docker y el contenedor API. Productos no probados."]
        for registros in por_producto.values():
            registros.append({"etapa": "ejecucion", "resultado": "SKIP", "detalle":
                              "Revisar Docker, permisos y estado de la API. No se atribuye la falla a las bases.", "ms": 0})
    lineas += ["", "## Matriz", "", "| Producto | Estado observado | Evaluación del modo solicitado |", "| --- | --- | --- |"]
    for producto, registros in por_producto.items():
        completa = "completa" if evaluacion_completa(registros, args.modo) else "incompleta"
        lineas.append(f"| {producto} | {estado_producto(registros)} | {completa} |")
    for producto, registros in por_producto.items():
        lineas += ["", f"## {producto}", "", "| Prueba | Resultado | ms | Diagnóstico y contexto |", "| --- | --- | ---: | --- |"]
        for r in registros:
            detalle = r["detalle"].replace("|", "/").replace("\n", " ")
            if r.get("request_id"):
                detalle += " X-Request-ID=" + r["request_id"]
            lineas.append(f"| {r['etapa']} | {r['resultado']} | {r['ms']} | {detalle} |")
    if args.modo in {"completo", "api"}:
        lineas += ["", "## Logs correlacionados de la API", "", "```text", *(logs or ["Correlación pendiente, ver registros SKIP."]), "```"]
    todos = [r for registros in por_producto.values() for r in registros]
    codigo = codigo_salida(por_producto, args.modo)
    lineas += ["", "Resumen: " + ", ".join(f"{s}={sum(r['resultado']==s for r in todos)}" for s in ("OK", "WARN", "FAIL", "SKIP")),
               f"Código de salida: {codigo}. 0=completa sin fallas, 1=completa con fallas, 2=incompleta.",
               "Los tiempos por prueba excluyen docker exec. Los de API incluyen HTTP y trabajo de sus adaptadores.",
               "Las filas con 0 ms describen configuración o conclusiones de otras operaciones, sin medición independiente.",
               "OK acredita solo la operación indicada. No mide rendimiento ni disponibilidad permanente."]
    salida = "\n".join(lineas) + "\n"
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        with args.salida.open("x", encoding="utf-8") as archivo:
            archivo.write(salida)
    print(salida)
    return codigo


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        try:
            trabajador(sys.argv[2], sys.argv[3], json.loads(sys.argv[4]))
        except Exception as error:
            # Una falla de configuración o del script no se disfraza de servidor caído.
            fila("ejecucion", "SKIP" if isinstance(error, (ImportError, ValueError)) else "FAIL",
                 "No se completó la etapa, tipo=" + type(error).__name__ + ". Revisar configuración y código.")
    else:
        sys.exit(principal())
