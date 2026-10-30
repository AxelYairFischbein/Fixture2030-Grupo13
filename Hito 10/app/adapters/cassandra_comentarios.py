"""Adaptador tabular (Hito 6): comentarios particionados por (partido_id, minuto, segmento)."""

import threading
import zlib
from datetime import datetime, timezone

from cassandra import ConsistencyLevel, DriverException, RequestExecutionException
from cassandra.cluster import Cluster, NoHostAvailable
from cassandra.policies import DCAwareRoundRobinPolicy
from cassandra.query import BatchStatement, BatchType

from app.contexto import operacion

ERRORES = (NoHostAvailable, DriverException, RequestExecutionException, OSError)
SEGMENTOS = (0, 1, 2, 3)
COLUMNAS = "creado_en, comentario_id, usuario_id, contenido, estado, likes"

# IN sobre minutos y segmentos + ORDER BY exige desactivar la paginación del driver (fetch_size=None).
Q_VENTANA = """SELECT {c} FROM {ks}.comentarios_por_partido
WHERE partido_id = ? AND minuto IN ? AND segmento IN ? AND creado_en >= ? AND creado_en < ?
ORDER BY creado_en DESC, comentario_id ASC LIMIT ?"""
# Continuación del cursor: filas con el mismo instante y un ID posterior al último devuelto.
Q_EMPATE = """SELECT {c} FROM {ks}.comentarios_por_partido
WHERE partido_id = ? AND minuto IN ? AND segmento IN ? AND creado_en = ? AND comentario_id > ?
ORDER BY creado_en DESC, comentario_id ASC LIMIT ?"""
INSERT_COLS = "(partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)"
Q_INSERT = "INSERT INTO {ks}.{tabla} " + INSERT_COLS + " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"


def segmento(comentario_id: str) -> int:
    # Misma regla del Hito 6: CRC32 del ID en UTF-8 módulo 4.
    return zlib.crc32(comentario_id.encode("utf-8")) % 4


def _iso(valor: datetime) -> str:
    return valor.replace(tzinfo=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class CassandraComentarios:
    nombre = "cassandra"

    def __init__(self, cfg):
        self._cfg = cfg
        self._sesion = None
        self._lock = threading.Lock()

    def _conectar(self):
        # Conexión perezosa y reintentable: si Cassandra no estaba disponible al iniciar, se reintenta.
        with self._lock:
            if self._sesion is None:
                cluster = Cluster(self._cfg.cassandra_hosts, port=self._cfg.cassandra_port, protocol_version=5,
                                  load_balancing_policy=DCAwareRoundRobinPolicy(local_dc="datacenter1"),
                                  connect_timeout=self._cfg.timeout, control_connection_timeout=self._cfg.timeout)
                try:
                    sesion = cluster.connect()
                except Exception:
                    cluster.shutdown()
                    raise
                sesion.default_timeout = self._cfg.timeout
                sesion.default_consistency_level = ConsistencyLevel.ONE  # nodo único del entorno local
                ks = self._cfg.cassandra_keyspace  # valor de configuración, nunca del consumidor
                self._ventana = sesion.prepare(Q_VENTANA.format(c=COLUMNAS, ks=ks))
                self._empate = sesion.prepare(Q_EMPATE.format(c=COLUMNAS, ks=ks))
                self._ins_partido = sesion.prepare(Q_INSERT.format(ks=ks, tabla="comentarios_por_partido"))
                self._ins_usuario = sesion.prepare(Q_INSERT.format(ks=ks, tabla="comentarios_por_usuario"))
                for sentencia in (self._ventana, self._empate):
                    sentencia.fetch_size = None
                self._sesion = sesion
        return self._sesion

    def ping(self):
        with operacion(self.nombre, "ping", ERRORES):
            self._conectar().execute("SELECT release_version FROM system.local")

    def listar(self, partido_id: str, minutos: list[datetime], desde: datetime, hasta: datetime,
               limite: int, cursor: tuple[datetime, str] | None) -> list[dict]:
        """Devuelve hasta `limite` filas en orden (creado_en DESC, comentario_id ASC)."""
        with operacion(self.nombre, "listar_ventana", ERRORES):
            sesion = self._conectar()
            filas = []
            if cursor:
                instante, ultimo_id = cursor
                # Un timestamp solo puede pertenecer a su bucket de minuto UTC.
                # Se conservan los cuatro segmentos y el orden por ID de los empates.
                minuto_cursor = [instante.replace(second=0, microsecond=0)]
                filas = list(sesion.execute(self._empate, (partido_id, minuto_cursor, SEGMENTOS, instante, ultimo_id, limite)))
                hasta = instante
            if len(filas) < limite:
                filas += list(sesion.execute(self._ventana, (partido_id, minutos, SEGMENTOS, desde, hasta, limite - len(filas))))
        return [{"comentarioId": f.comentario_id, "usuarioId": f.usuario_id, "contenido": f.contenido,
                 "estado": f.estado, "likes": f.likes, "creadoEn": _iso(f.creado_en)} for f in filas]

    def insertar(self, partido_id: str, comentario_id: str, usuario_id: str, contenido: str, creado_en: datetime) -> dict:
        minuto = creado_en.replace(second=0, microsecond=0)
        valores = (partido_id, minuto, segmento(comentario_id), creado_en, comentario_id, usuario_id,
                   creado_en.date(), contenido, "visible", 0)
        # Batch LOGGED solo con las dos representaciones del mismo comentario, como en el Hito 6.
        lote = BatchStatement(batch_type=BatchType.LOGGED)
        with operacion(self.nombre, "insertar_comentario", ERRORES):
            sesion = self._conectar()
            lote.add(self._ins_partido, valores)
            lote.add(self._ins_usuario, valores)
            sesion.execute(lote)
        return {"comentarioId": comentario_id, "partidoId": partido_id, "usuarioId": usuario_id,
                "contenido": contenido, "estado": "visible", "likes": 0, "creadoEn": _iso(creado_en),
                "minuto": _iso(minuto), "segmento": valores[2]}
