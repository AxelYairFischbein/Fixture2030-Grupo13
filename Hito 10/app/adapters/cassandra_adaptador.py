"""Adaptador de Cassandra (Hito 6): comentarios por partido y por usuario.

Respeta el modelo tabular del Hito 6 (keyspace fixture2030_comentarios):
- comentarios_por_partido: PRIMARY KEY ((partido_id, minuto, segmento), creado_en, comentario_id)
- comentarios_por_usuario: PRIMARY KEY ((usuario_id, dia), creado_en, comentario_id)
Ambas con CLUSTERING ORDER BY (creado_en DESC, comentario_id ASC). minuto es creado_en
truncado al minuto UTC, segmento = CRC32(comentario_id UTF-8) mod 4 y dia el día UTC.

Solo ejecuta sentencias preparadas y fijas, siempre por clave de partición (nunca
ALLOW FILTERING). Las escrituras usan un batch registrado con las dos representaciones.
Devuelve dicts con fechas aware en UTC y traduce las excepciones del driver a las de
app.errors. Nada del driver sale de acá.
"""

import logging
import threading
import time
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

from cassandra import (
    AuthenticationFailed,
    ConsistencyLevel,
    DriverException,
    OperationTimedOut,
    ReadTimeout,
    Unavailable,
    WriteTimeout,
)
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile, NoHostAvailable
from cassandra.connection import ConnectionException
from cassandra.io.asyncioreactor import AsyncioConnection
from cassandra.policies import DCAwareRoundRobinPolicy, FallthroughRetryPolicy, TokenAwarePolicy
from cassandra.query import BatchStatement, BatchType, dict_factory

from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio

DEPENDENCIA = "cassandra"

SEGMENTOS = (0, 1, 2, 3)
UN_MS = timedelta(milliseconds=1)
UN_MINUTO = timedelta(minutes=1)
EPOCA = datetime(1970, 1, 1, tzinfo=UTC)

# CU-08: rondas máximas de la fusión cuando el filtro de estado descarta filas (ver
# leer_por_partido). Con todos los estados alcanza siempre una sola ronda.
MAX_RONDAS = 5

logger = logging.getLogger("app.adapters.cassandra")

COLUMNAS = ("partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, "
            "contenido, estado, likes")

# Q1 y Q2 del Hito 6. IN sobre minutos y segmentos (como máximo 6 × 4 = 24 particiones).
# Sin ORDER BY: Cassandra no permite paginar IN con ORDER BY. Cada partición devuelve sus
# primeras filas en el orden de clustering (PER PARTITION LIMIT) y el adaptador las fusiona
# y aplica el límite global.
SEL_PARTIDO = (
    f"SELECT {COLUMNAS} FROM comentarios_por_partido "
    "WHERE partido_id = ? AND minuto IN ? AND segmento IN ? "
    "AND creado_en >= ? AND creado_en < ? "
    "PER PARTITION LIMIT ?"
)

# Q3 del Hito 6: una sola partición (usuario_id, dia), leída en orden de clustering.
SEL_USUARIO = (
    f"SELECT {COLUMNAS} FROM comentarios_por_usuario "
    "WHERE usuario_id = ? AND dia = ? AND creado_en < ?"
)

# Lectura puntual por clave primaria completa (CU-09 reintento, CU-20).
SEL_CLAVE_PARTIDO = (
    f"SELECT {COLUMNAS} FROM comentarios_por_partido "
    "WHERE partido_id = ? AND minuto = ? AND segmento = ? AND creado_en = ? AND comentario_id = ?"
)

INS_PARTIDO = (
    f"INSERT INTO comentarios_por_partido ({COLUMNAS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
INS_USUARIO = (
    f"INSERT INTO comentarios_por_usuario ({COLUMNAS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

# Edición delimitada por cada clave completa (Hito 6, crud.cql). Solo se llama después de
# leer la fila: en CQL un UPDATE sobre una clave inexistente crearía la fila.
UPD_ESTADO_PARTIDO = (
    "UPDATE comentarios_por_partido SET estado = ? "
    "WHERE partido_id = ? AND minuto = ? AND segmento = ? AND creado_en = ? AND comentario_id = ?"
)
UPD_ESTADO_USUARIO = (
    "UPDATE comentarios_por_usuario SET estado = ? "
    "WHERE usuario_id = ? AND dia = ? AND creado_en = ? AND comentario_id = ?"
)

PING = "SELECT release_version FROM system.local"

SENTENCIAS = {
    "sel_partido": SEL_PARTIDO, "sel_usuario": SEL_USUARIO, "sel_clave": SEL_CLAVE_PARTIDO,
    "ins_partido": INS_PARTIDO, "ins_usuario": INS_USUARIO,
    "upd_partido": UPD_ESTADO_PARTIDO, "upd_usuario": UPD_ESTADO_USUARIO,
}


# Cálculos del modelo (Hito 6)

def segmento(comentario_id: str) -> int:
    """CRC32 del identificador en UTF-8, módulo 4 (Hito 6, carga_o_prueba.py)."""
    return zlib.crc32(comentario_id.encode("utf-8")) % 4


def minuto_de(instante: datetime) -> datetime:
    """Inicio del minuto UTC que contiene al instante."""
    return instante.astimezone(UTC).replace(second=0, microsecond=0)


def minutos_que_intersectan(desde: datetime, hasta: datetime) -> list[datetime]:
    """Minutos UTC que intersectan [desde, hasta). Una ventana de 5 min toca como máximo 6."""
    minutos, actual = [], minuto_de(desde)
    while actual < hasta:
        minutos.append(actual)
        actual += UN_MINUTO
    return minutos


def _ms(instante: datetime) -> int:
    return (instante - EPOCA) // UN_MS


def clave_de_orden(creado_en: datetime, comentario_id: str) -> tuple[int, str]:
    """Orden creado_en DESC, comentario_id ASC como clave ascendente."""
    return (-_ms(creado_en), comentario_id)


def _clave_fila(fila: dict) -> tuple[int, str]:
    return clave_de_orden(fila["creado_en"], fila["comentario_id"])


def _a_utc(valor: datetime) -> datetime:
    """El driver devuelve timestamps naive en UTC."""
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor.astimezone(UTC)


def _a_dict(fila: dict) -> dict:
    convertida = dict(fila)
    convertida["creado_en"] = _a_utc(fila["creado_en"])
    convertida["minuto"] = _a_utc(fila["minuto"])
    dia = fila["dia"]
    # cassandra.util.Date → datetime.date
    convertida["dia"] = dia if isinstance(dia, date) else dia.date()
    return convertida


def _fin_del_dia(dia: date) -> datetime:
    return datetime(dia.year, dia.month, dia.day, tzinfo=UTC) + timedelta(days=1)


class AdaptadorCassandra:
    def __init__(self, settings: Settings, sesion=None) -> None:
        """`sesion` permite inyectar una sesión falsa en las pruebas."""
        self._settings = settings
        self._cluster: Cluster | None = None
        self._sesion = sesion
        self._preparadas: dict | None = None
        self._lock = threading.Lock()

    # Conexión

    def _crear_cluster(self) -> Cluster:
        s = self._settings
        perfil = ExecutionProfile(
            load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy(local_dc=s.cassandra_dc)),
            # Sin reintentos implícitos: el request_timeout de §6.3 es el límite real.
            retry_policy=FallthroughRetryPolicy(),
            consistency_level=ConsistencyLevel.ONE,
            request_timeout=s.cassandra_request_timeout_s,
            row_factory=dict_factory,
        )
        autenticacion = None
        if s.cassandra_user and s.cassandra_password:
            autenticacion = PlainTextAuthProvider(
                username=s.cassandra_user, password=s.cassandra_password.get_secret_value()
            )
        return Cluster(
            [h.strip() for h in s.cassandra_hosts.split(",") if h.strip()],
            port=s.cassandra_port,
            # Python 3.12+ no trae asyncore y en Windows no hay libev.
            connection_class=AsyncioConnection,
            execution_profiles={EXEC_PROFILE_DEFAULT: perfil},
            auth_provider=autenticacion,
            connect_timeout=s.cassandra_connect_timeout_s,
            control_connection_timeout=s.cassandra_connect_timeout_s,
        )

    def _sesion_lista(self):
        """Conecta en el primer uso: la API arranca aunque Cassandra esté caída.

        Si la conexión falla, el driver apaga el Cluster; el próximo uso crea otro.
        """
        if self._preparadas is not None:
            return self._sesion
        with self._lock:
            if self._preparadas is None:
                if self._sesion is None:
                    cluster = self._crear_cluster()
                    try:
                        self._sesion = cluster.connect(self._settings.cassandra_keyspace)
                    except BaseException:
                        cluster.shutdown()
                        raise
                    self._cluster = cluster
                self._preparadas = {
                    nombre: self._sesion.prepare(cql) for nombre, cql in SENTENCIAS.items()
                }
        return self._sesion

    def cerrar(self) -> None:
        if self._cluster is not None:
            self._cluster.shutdown()

    @contextmanager
    def _traducir(self, operacion: str) -> Iterator[None]:
        """Traduce excepciones del driver y registra dependencia, resultado y duración.

        Nunca se registra el CQL ni los parámetros.
        """
        inicio = time.perf_counter()
        resultado = "ok"
        try:
            yield
        except (ReadTimeout, WriteTimeout, OperationTimedOut) as exc:
            # En escrituras el resultado es incierto: el batch registrado puede completarse.
            resultado = f"DEPENDENCIA_TIMEOUT tipo={type(exc).__name__}"
            raise DependenciaTimeout(DEPENDENCIA) from exc
        except NoHostAvailable as exc:
            if any(isinstance(e, AuthenticationFailed) for e in (exc.errors or {}).values()):
                # Credenciales inválidas: configuración, no disponibilidad.
                resultado = "ERROR_INTERNO tipo=AuthenticationFailed"
                raise ErrorDominio() from exc
            resultado = "DEPENDENCIA_NO_DISPONIBLE"
            raise DependenciaNoDisponible(DEPENDENCIA) from exc
        except (Unavailable, ConnectionException) as exc:
            resultado = f"DEPENDENCIA_NO_DISPONIBLE tipo={type(exc).__name__}"
            raise DependenciaNoDisponible(DEPENDENCIA) from exc
        except DriverException as exc:
            # Keyspace inexistente, sintaxis, autenticación u otra falla de configuración.
            resultado = f"ERROR_INTERNO tipo={type(exc).__name__}"
            raise ErrorDominio() from exc
        finally:
            duracion_ms = (time.perf_counter() - inicio) * 1000
            logger.info(
                "dependencia=%s operacion=%s resultado=%s duracion_ms=%.1f",
                DEPENDENCIA, operacion, resultado, duracion_ms,
            )

    def _ejecutar(self, nombre: str, parametros: tuple, fetch_size: int | None = None):
        sesion = self._sesion_lista()
        sentencia = self._preparadas[nombre].bind(parametros)
        if fetch_size is not None:
            sentencia.fetch_size = fetch_size
        return sesion.execute(sentencia)

    # CU-08 (Q1 y Q2)

    def leer_por_partido(
        self, partido_id: str, desde: datetime, hasta: datetime,
        antes_de: tuple[datetime, str] | None, limite: int, solo_visibles: bool,
    ) -> tuple[list[dict], tuple[datetime, str] | None]:
        """Comentarios de [desde, hasta): minutos que lo intersectan × 4 segmentos.

        Devuelve (filas, siguiente): hasta `limite` filas en orden creado_en DESC,
        comentario_id ASC (límite global, no por partición) y el cursor para seguir,
        o None si no hay más. `antes_de` excluye esa clave y todo lo anterior en el orden.

        Cada partición devuelve como máximo k = limite + 1 filas. Si una partición llegó a
        k ("saturada"), puede tener más filas después de su última: el orden fusionado solo
        es exacto hasta la menor de esas últimas filas (la frontera). Si el filtro de estado
        no juntó k filas antes de la frontera, se consulta otra ronda desde ella. Si se
        agotan las rondas, la página puede tener menos filas, pero el cursor sigue desde la
        frontera y no se pierde ninguna.
        """
        k = limite + 1
        minutos = minutos_que_intersectan(desde, hasta)
        cursor = antes_de
        aceptadas: list[dict] = []
        with self._traducir("leer_por_partido"):
            for _ in range(MAX_RONDAS):
                tope = hasta if cursor is None else min(hasta, cursor[0] + UN_MS)
                if tope <= desde:
                    return aceptadas, None
                filas = [_a_dict(f) for f in self._ejecutar(
                    "sel_partido", (partido_id, minutos, list(SEGMENTOS), desde, tope, k))]
                filas.sort(key=_clave_fila)

                por_particion: dict[tuple, list[dict]] = {}
                for fila in filas:
                    por_particion.setdefault((fila["minuto"], fila["segmento"]), []).append(fila)
                ultimas_saturadas = [p[-1] for p in por_particion.values() if len(p) >= k]
                frontera = min(ultimas_saturadas, key=_clave_fila) if ultimas_saturadas else None

                clave_cursor = clave_de_orden(*cursor) if cursor else None
                for fila in filas:
                    clave = _clave_fila(fila)
                    if clave_cursor is not None and clave <= clave_cursor:
                        continue
                    if frontera is not None and clave > _clave_fila(frontera):
                        break
                    if solo_visibles and fila["estado"] != "visible":
                        continue
                    aceptadas.append(fila)
                    if len(aceptadas) == k:
                        ultima = aceptadas[limite - 1]
                        return aceptadas[:limite], (ultima["creado_en"], ultima["comentario_id"])

                if frontera is None:
                    return aceptadas, None
                nuevo = (frontera["creado_en"], frontera["comentario_id"])
                if cursor is not None and clave_de_orden(*nuevo) <= clave_de_orden(*cursor):
                    break  # sin avance (más de k filas en el mismo milisegundo)
                cursor = nuevo
        logger.warning("dependencia=%s operacion=leer_por_partido resultado=rondas_agotadas "
                       "filas=%d", DEPENDENCIA, len(aceptadas))
        return aceptadas, cursor

    # CU-10 (Q3)

    def leer_por_usuario(
        self, usuario_id: str, dia: date, antes_de: tuple[datetime, str] | None, limite: int,
    ) -> tuple[list[dict], tuple[datetime, str] | None]:
        """Comentarios de la partición (usuario_id, dia) en orden de clustering.

        El driver pagina de a limite + 1 filas y solo se lee lo necesario.
        """
        fin = _fin_del_dia(dia)
        tope = fin if antes_de is None else min(fin, antes_de[0] + UN_MS)
        clave_cursor = clave_de_orden(*antes_de) if antes_de else None
        filas: list[dict] = []
        with self._traducir("leer_por_usuario"):
            for fila in self._ejecutar("sel_usuario", (usuario_id, dia, tope), fetch_size=limite + 1):
                fila = _a_dict(fila)
                if clave_cursor is not None and _clave_fila(fila) <= clave_cursor:
                    continue
                filas.append(fila)
                if len(filas) > limite:
                    ultima = filas[limite - 1]
                    return filas[:limite], (ultima["creado_en"], ultima["comentario_id"])
        return filas, None

    # CU-09 y CU-20

    def leer_comentario(self, partido_id: str, creado_en: datetime, comentario_id: str) -> dict | None:
        """Lectura por clave primaria completa en comentarios_por_partido."""
        with self._traducir("leer_comentario"):
            fila = self._ejecutar("sel_clave", (
                partido_id, minuto_de(creado_en), segmento(comentario_id), creado_en, comentario_id,
            )).one()
        return _a_dict(fila) if fila else None

    def insertar_comentario(self, comentario: dict) -> None:
        """Batch registrado con las dos representaciones (upsert por clave completa).

        Deriva de creado_en y comentario_id las columnas del modelo: minuto, segmento y dia.
        """
        creado_en = comentario["creado_en"].astimezone(UTC)
        valores = (
            comentario["partido_id"], minuto_de(creado_en), segmento(comentario["comentario_id"]),
            creado_en, comentario["comentario_id"], comentario["usuario_id"], creado_en.date(),
            comentario["contenido"], comentario["estado"], comentario["likes"],
        )
        with self._traducir("insertar_comentario"):
            self._sesion_lista()
            batch = BatchStatement(batch_type=BatchType.LOGGED)
            batch.add(self._preparadas["ins_partido"], valores)
            batch.add(self._preparadas["ins_usuario"], valores)
            self._sesion.execute(batch)

    def actualizar_estado(self, fila: dict, estado: str) -> None:
        """Batch registrado que cambia estado en las dos tablas.

        `fila` es la leída por clave completa: de ella salen usuario_id y dia.
        """
        with self._traducir("actualizar_estado"):
            self._sesion_lista()
            batch = BatchStatement(batch_type=BatchType.LOGGED)
            batch.add(self._preparadas["upd_partido"], (
                estado, fila["partido_id"], fila["minuto"], fila["segmento"],
                fila["creado_en"], fila["comentario_id"]))
            batch.add(self._preparadas["upd_usuario"], (
                estado, fila["usuario_id"], fila["dia"], fila["creado_en"], fila["comentario_id"]))
            self._sesion.execute(batch)

    def ping(self) -> bool:
        """Chequeo de salud: True si Cassandra responde. Nunca lanza."""
        try:
            with self._traducir("ping"):
                self._sesion_lista().execute(PING)
            return True
        except ErrorDominio:
            return False
