"""Casos de uso. Combinan adaptadores y aplican reglas; no conocen HTTP ni drivers."""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from app import contexto
from app.errors import Conflicto, DependenciaNoDisponible, NoEncontrado, SesionNoVigente, ValidacionFallida

log = logging.getLogger("fixture2030")

VENTANA_COMENTARIOS_MAX = timedelta(minutes=5)  # <= 6 minutos x 4 segmentos = 24 particiones (Hito 6)
VENTANA_ESTADISTICAS_DEFECTO = timedelta(minutes=10)
PUNTOS_MAX = 720  # intervalos por equipo en una respuesta
SEGUNDOS_INTERVALO = {"10s": 10, "30s": 30, "1m": 60, "5m": 300}


def _utc(valor: datetime) -> datetime:
    # Un instante sin zona horaria se interpreta como UTC, igual que en los Hitos 6 y 8.
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)


def _iso(valor: datetime) -> str:
    return valor.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def minutos_de_ventana(desde: datetime, hasta: datetime) -> list[datetime]:
    """Buckets de minuto UTC que intersectan [desde, hasta)."""
    actual = desde.replace(second=0, microsecond=0)
    ultimo = (hasta - timedelta(microseconds=1)).replace(second=0, microsecond=0)
    minutos = []
    while actual <= ultimo:
        minutos.append(actual)
        actual += timedelta(minutes=1)
    return minutos


def codificar_cursor(comentario: dict) -> str:
    instante = datetime.fromisoformat(comentario["creadoEn"].replace("Z", "+00:00"))
    return f"{int(instante.timestamp() * 1000)}_{comentario['comentarioId']}"


def decodificar_cursor(cursor: str) -> tuple[datetime, str]:
    ms, comentario_id = cursor.split("_", 1)
    return datetime.fromtimestamp(int(ms) / 1000, timezone.utc), comentario_id


class Servicios:
    def __init__(self, cfg, *, mongo, neo4j, cassandra, redis, influx, iris):
        self.cfg = cfg
        self.mongo, self.neo4j, self.cassandra = mongo, neo4j, cassandra
        self.redis, self.influx, self.iris = redis, influx, iris

    # --- Salud ---------------------------------------------------------------------------
    def salud(self) -> list[dict]:
        estados = []
        for adaptador in (self.mongo, self.neo4j, self.cassandra, self.redis, self.influx, self.iris):
            try:
                adaptador.ping()
                estado = "ok"
            except DependenciaNoDisponible:
                estado = "no_disponible"
            ms = next((t["ms"] for t in reversed(contexto.trazas.get() or []) if t["fuente"] == adaptador.nombre), 0)
            estados.append({"fuente": adaptador.nombre, "estado": estado, "ms": ms})
        return estados

    # --- Equipos y jugadores (MongoDB, caché en Redis) -----------------------------------------
    def listar_equipos(self, confederacion, pagina: int, tamanio: int):
        return self.mongo.listar_equipos(confederacion, (pagina - 1) * tamanio, tamanio)

    def obtener_equipo(self, equipo_id: str) -> tuple[dict, str]:
        """Cache-aside: Redis primero; si Redis falla se degrada a MongoDB sin ocultarlo (BYPASS)."""
        redis_ok = True
        try:
            cache = self.redis.leer_equipo(equipo_id)
            if cache:
                return cache, "HIT"
        except DependenciaNoDisponible:
            redis_ok = False
        equipo = self.mongo.buscar_equipo(equipo_id)
        if equipo is None:
            raise NoEncontrado(f"No existe el equipo {equipo_id}.")
        if redis_ok:
            try:
                self.redis.guardar_equipo(equipo_id, equipo, self.cfg.cache_equipo_ttl)
            except DependenciaNoDisponible:
                redis_ok = False
        return equipo, "MISS" if redis_ok else "BYPASS"

    def invalidar_equipo(self, equipo_id: str) -> bool:
        return self.redis.invalidar_equipo(equipo_id)

    def plantel(self, equipo_id: str, posicion, pagina: int, tamanio: int):
        if not self.mongo.existe_equipo(equipo_id):
            raise NoEncontrado(f"No existe el equipo {equipo_id}.")
        return self.mongo.plantel(equipo_id, posicion, (pagina - 1) * tamanio, tamanio)

    # --- Partidos (Neo4j) --------------------------------------------------------------------
    def agenda(self, equipo_id: str, limite: int) -> list[dict]:
        partidos = self.neo4j.agenda(equipo_id, limite)
        if partidos is None:
            raise NoEncontrado(f"No existe el equipo {equipo_id} en el grafo.")
        return partidos

    def partido(self, partido_id: str, limite_eventos: int) -> dict:
        partido = self.neo4j.partido(partido_id)
        if partido is None:
            raise NoEncontrado(f"No existe el partido {partido_id}.")
        partido["eventos"] = self.neo4j.eventos(partido_id, limite_eventos)  # [] es válido
        return partido

    # --- Comentarios (Cassandra; Redis para idempotencia; Neo4j valida el partido) ---------------
    def comentarios(self, partido_id: str, desde: datetime, hasta: datetime, limite: int, cursor: str | None):
        desde, hasta = _utc(desde), _utc(hasta)
        if hasta <= desde:
            raise ValidacionFallida("'hasta' debe ser posterior a 'desde'.")
        if hasta - desde > VENTANA_COMENTARIOS_MAX:
            raise ValidacionFallida("La ventana de comentarios no puede superar 5 minutos.")
        posicion = None
        if cursor:
            posicion = decodificar_cursor(cursor)
            if not desde <= posicion[0] < hasta:
                raise ValidacionFallida("El cursor no pertenece a la ventana solicitada.")
        minutos = minutos_de_ventana(desde, hasta)
        filas = self.cassandra.listar(partido_id, minutos, desde, hasta, limite + 1, posicion)
        siguiente = codificar_cursor(filas[limite - 1]) if len(filas) > limite else None
        datos = {"partidoId": partido_id, "desde": _iso(desde), "hasta": _iso(hasta),
                 "particiones": len(minutos) * 4, "items": filas[:limite]}
        return datos, siguiente

    def crear_comentario(self, partido_id: str, usuario_id: str, contenido: str, clave_idem: str) -> tuple[dict, bool]:
        """Devuelve (comentario, repetido). Una misma Idempotency-Key nunca genera dos filas."""
        huella = hashlib.sha256(json.dumps([partido_id, usuario_id, contenido]).encode()).hexdigest()
        clave = f"comentario:{partido_id}:{clave_idem}"
        ttl = self.cfg.idempotencia_ttl
        previo = self.redis.reservar_idempotencia(clave, huella, ttl)
        if previo:
            if previo["huella"] != huella:
                raise Conflicto("La Idempotency-Key ya se utilizó con otro contenido.")
            if previo["estado"] != "COMPLETADO":
                raise Conflicto("Hay una solicitud en curso con la misma Idempotency-Key.")
            return previo["resultado"], True
        try:
            if self.neo4j.partido(partido_id) is None:
                raise NoEncontrado(f"No existe el partido {partido_id}.")
            ahora = datetime.now(timezone.utc)
            creado_en = ahora.replace(microsecond=ahora.microsecond // 1000 * 1000)  # precisión de Cassandra
            comentario = self.cassandra.insertar(partido_id, "API-" + uuid.uuid4().hex, usuario_id, contenido, creado_en)
        except Exception:
            try:
                self.redis.liberar_idempotencia(clave)  # permite reintentar con la misma clave
            except DependenciaNoDisponible:
                pass
            raise
        try:
            self.redis.completar_idempotencia(clave, huella, comentario, ttl)
        except DependenciaNoDisponible:
            # La fila ya existe; la clave queda EN_CURSO hasta su TTL y bloquea duplicados (409).
            log.warning("req=%s idempotencia sin completar para %s", contexto.request_id.get(), clave)
        return comentario, False

    # --- Sesiones (Redis) ------------------------------------------------------------------
    def crear_sesion(self, usuario_id: str, rol: str) -> dict:
        return self.redis.crear_sesion(usuario_id, rol)

    def obtener_sesion(self, sesion_id: str) -> dict:
        sesion = self.redis.obtener_sesion(sesion_id)
        if sesion is None:
            raise SesionNoVigente(f"No existe una sesión vigente con ID {sesion_id} (cerrada, vencida o inexistente).")
        return sesion

    def cerrar_sesion(self, sesion_id: str) -> None:
        self.redis.cerrar_sesion(sesion_id)  # idempotente: cerrar dos veces deja el mismo estado

    # --- Estadísticas (InfluxDB) -------------------------------------------------------------
    def estadisticas(self, partido_id: str, equipo_id, desde, hasta, intervalo: str) -> dict:
        if (desde is None) != (hasta is None):
            raise ValidacionFallida("Enviar 'desde' y 'hasta' juntos, u omitir ambos para la ventana más reciente.")
        if desde is None:
            ultimo = self.influx.ultimo_instante(partido_id)
            if ultimo is None:  # sin puntos retenidos: respuesta vacía válida, no un error
                return {"partidoId": partido_id, "equipoId": equipo_id, "desde": None, "hasta": None,
                        "intervalo": intervalo, "puntos": []}
            hasta = ultimo + timedelta(seconds=1)
            desde = hasta - VENTANA_ESTADISTICAS_DEFECTO
        desde, hasta = _utc(desde), _utc(hasta)
        if hasta <= desde:
            raise ValidacionFallida("'hasta' debe ser posterior a 'desde'.")
        intervalos = (hasta - desde).total_seconds() / SEGUNDOS_INTERVALO[intervalo]
        if intervalos > PUNTOS_MAX:
            raise ValidacionFallida(f"La ventana genera {int(intervalos)} intervalos por equipo; el máximo es "
                                    f"{PUNTOS_MAX}. Reducir la ventana o aumentar el intervalo.")
        limite = (int(intervalos) + 1) * (1 if equipo_id else 2)
        puntos = self.influx.resumen(partido_id, equipo_id, desde, hasta, intervalo, limite)
        return {"partidoId": partido_id, "equipoId": equipo_id, "desde": _iso(desde), "hasta": _iso(hasta),
                "intervalo": intervalo, "puntos": puntos}

    # --- Actas (IRIS) -----------------------------------------------------------------------
    def acta(self, codigo: str) -> dict:
        acta = self.iris.acta(codigo)
        if acta is None:
            raise NoEncontrado(f"No existe el acta del partido {codigo}.")
        return acta

    def cambiar_estado_acta(self, codigo: str, nuevo: str) -> tuple[bool, dict]:
        actual = self.acta(codigo)
        if actual["estado"] == nuevo:
            return False, actual  # PUT idempotente: repetir no produce otra transición
        if not self.iris.cambiar_estado(codigo, nuevo):  # la regla vive en Partido.CambiarEstado()
            raise NoEncontrado(f"No existe el acta del partido {codigo}.")
        return True, self.acta(codigo)
