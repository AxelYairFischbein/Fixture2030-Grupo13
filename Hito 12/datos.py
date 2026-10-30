"""Muestra fija del Hito 12, aislada en su keyspace. Preparación separada de la carga HTTP."""

import argparse
import json
import sys
import zlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
KEYSPACE = "fixture2030_h12"


def config(ruta=RAIZ / "config.ejemplo.json"):
    c = json.loads(sys.stdin.read() if str(ruta) == "-" else Path(ruta).read_text(encoding="utf-8-sig"))
    if c["keyspace"] != KEYSPACE or c["partidos"] != ["PAR-001", "PAR-002"]:
        raise ValueError("Conservar el keyspace aislado y los dos partidos de prueba")
    if not 150 <= c["por_partido"] <= 6000 or c["por_partido"] % 150:
        raise ValueError("Usar entre 150 y 6000 filas por partido, múltiplo de 150")
    if (instante(c["hasta"]) - instante(c["desde"]) != timedelta(minutes=5)
            or instante(c["desde"]).second or instante(c["desde"]).microsecond):
        raise ValueError("La muestra abarca cinco minutos completos")
    if not 1 <= c["limite"] <= 50:
        raise ValueError("Límite fuera del contrato")
    return c


def instante(texto):
    d = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("Se requiere zona horaria")
    return d.astimezone(timezone.utc)


def iso(d):
    return d.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def muestra(c, partido):
    """Tres IDs distintos por instante, incluyendo empates que cruzan páginas."""
    inicio = instante(c["desde"])
    for i in range(c["por_partido"]):
        d = inicio + timedelta(milliseconds=(i // 3) * 300000 // (c["por_partido"] // 3))
        yield {"comentarioId": f"H12-{partido}-{i:05d}", "usuarioId": f"USR-{i % 100 + 1:05d}",
               "contenido": f"Comentario sintetico H12 {partido} {i:05d}", "estado": "visible",
               "likes": i % 7, "creadoEn": iso(d)}


def ordenados(c, partido):
    return sorted(muestra(c, partido), key=lambda r: (-instante(r["creadoEn"]).timestamp(), r["comentarioId"]))


def validar_fuente(sesion, c):
    """Cuarenta particiones conocidas, sin escanear los datos de otros hitos."""
    consulta = sesion.prepare(f"SELECT creado_en, comentario_id, usuario_id, contenido, estado, likes FROM {KEYSPACE}.comentarios_por_partido WHERE partido_id=? AND minuto=? AND segmento=?")
    distribucion = {}
    for partido in c["partidos"]:
        filas = []
        particiones = Counter()
        for m in range(5):
            minuto = instante(c["desde"]) + timedelta(minutes=m)
            for segmento in range(4):
                actuales = list(sesion.execute(consulta, (partido, minuto, segmento)))
                if any(f.creado_en.replace(second=0, microsecond=0, tzinfo=timezone.utc) != minuto
                       or zlib.crc32(f.comentario_id.encode("utf-8")) % 4 != segmento for f in actuales):
                    raise ValueError("Hay comentarios ubicados en un minuto o segmento incorrecto")
                particiones[f"minuto{m}-segmento{segmento}"] = len(actuales)
                filas.extend({"comentarioId": f.comentario_id, "usuarioId": f.usuario_id,
                              "contenido": f.contenido, "estado": f.estado, "likes": f.likes,
                              "creadoEn": iso(f.creado_en.replace(tzinfo=timezone.utc))} for f in actuales)
        filas.sort(key=lambda r: (-instante(r["creadoEn"]).timestamp(), r["comentarioId"]))
        if filas != ordenados(c, partido):
            raise ValueError(f"La muestra existente de {partido} difiere. Se conserva sin sobrescribirla")
        distribucion[partido] = {"filas": len(filas), "particiones": dict(particiones)}
    return {"integridad": "OK", "puntos_logicos": sum(d["filas"] for d in distribucion.values()),
            "distribucion": distribucion, "comparacion": "Todas las claves y atributos coinciden con el generador fijo"}


def principal():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("accion", choices=("preparar", "validar"))
    p.add_argument("--config", type=Path, default=RAIZ / "config.ejemplo.json")
    args = p.parse_args()
    c = config(args.config)
    sys.path.insert(0, "/app")
    from app.config import cargar
    from app.adapters.cassandra_comentarios import segmento, Q_INSERT
    from cassandra.cluster import Cluster
    from cassandra.policies import DCAwareRoundRobinPolicy
    cfg = cargar()
    if cfg.cassandra_keyspace != KEYSPACE:
        raise ValueError("La API no está configurada con el keyspace del Hito 12")
    cluster = Cluster(cfg.cassandra_hosts, port=cfg.cassandra_port, protocol_version=5,
                      load_balancing_policy=DCAwareRoundRobinPolicy(local_dc="datacenter1"),
                      connect_timeout=cfg.timeout, control_connection_timeout=cfg.timeout)
    try:
        sesion = cluster.connect()
        sesion.default_timeout = cfg.timeout
        version = sesion.execute("SELECT release_version FROM system.local").one().release_version
        existe = sesion.execute("SELECT keyspace_name FROM system_schema.keyspaces WHERE keyspace_name=%s", (KEYSPACE,)).one()
        enviados = 0
        if args.accion == "preparar" and not existe:
            esquema = Path("/h6-esquema.cql").read_text(encoding="utf-8").replace("fixture2030_comentarios", KEYSPACE)
            for sentencia in esquema.split(";"):
                if sentencia.strip():
                    sesion.execute(sentencia)
            insertar = sesion.prepare(Q_INSERT.format(ks=KEYSPACE, tabla="comentarios_por_partido"))
            for partido in c["partidos"]:
                for fila in muestra(c, partido):
                    d = instante(fila["creadoEn"])
                    sesion.execute(insertar, (partido, d.replace(second=0, microsecond=0), segmento(fila["comentarioId"]),
                                             d, fila["comentarioId"], fila["usuarioId"], d.date(), fila["contenido"],
                                             fila["estado"], fila["likes"]))
                    enviados += 1
        resultado = validar_fuente(sesion, c)
        print(json.dumps({"fecha": datetime.now().astimezone().isoformat(), "cassandra": version,
                          "keyspace": KEYSPACE, "escrituras_en_esta_ejecucion": enviados, **resultado}, ensure_ascii=False))
    finally:
        cluster.shutdown()


if __name__ == "__main__":
    principal()
