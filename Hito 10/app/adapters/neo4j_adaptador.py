"""Adaptador de Neo4j (Hito 5): agenda, eventos, calendario y catálogo de partidos.

Encapsula el driver: crea la conexión con los timeouts de casos_de_uso.md §6.3,
ejecuta solo las consultas fijas de este módulo (derivadas de Q04, Q06, Q07 y Q09
del Hito 5), siempre parametrizadas y con LIMIT, devuelve dicts con propiedades
(nunca nodos ni element ids) y traduce las excepciones del driver a las de
app.errors. Nada del driver sale de acá.

Ninguna consulta proyecta Partido.estado: el estado del partido pertenece a IRIS
(casos_de_uso.md §3.1).
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from neo4j import READ_ACCESS, Driver, GraphDatabase, NotificationMinimumSeverity, Query
from neo4j.exceptions import (
    DriverError,
    Neo4jError,
    ServiceUnavailable,
    SessionExpired,
)
from neo4j.time import DateTime

from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio

DEPENDENCIA = "neo4j"

# Tope de la carga del catálogo (§3.2): la muestra tiene 64 partidos.
LIMITE_CATALOGO = 1000

logger = logging.getLogger("app.adapters.neo4j")

# CU-05 (Q04 + Q06). Primero el nodo raíz: sin fila → equipo inexistente (404);
# una fila con la lista vacía → equipo sin partidos (200 []). El RETURN agrupa por
# el nodo raíz: un collect() sin clave devolvería una fila aunque no hubiera equipo.
AGENDA_EQUIPO = """
MATCH (e:Equipo {equipoId: $equipoId})
OPTIONAL MATCH (e)-[d:DISPUTA]->(p:Partido)<-[:DISPUTA]-(rival:Equipo),
               (p)-[:SE_JUEGA_EN]->(s:Estadio)
WHERE rival <> e
WITH e, d, p, rival, s
ORDER BY p.inicio, p.partidoId
LIMIT $limite
RETURN e.equipoId AS equipoId, collect(CASE WHEN p IS NULL THEN null ELSE {
  partidoId: p.partidoId, inicio: p.inicio, grupo: p.grupo, fase: p.fase, rol: d.rol,
  rival: {equipoId: rival.equipoId, codigo: rival.codigo, nombre: rival.nombre},
  estadio: {estadioId: s.estadioId, nombre: s.nombre, ciudad: s.ciudad}
} END) AS partidos
"""

# CU-06 (Q07). Hay un único partido, así que el LIMIT sobre filas cuenta eventos.
# El segundo recorrido conserva la validación de Q07: el jugador pertenece a un
# equipo que disputa el partido. Participantes en orden SALE, ENTRA.
EVENTOS_PARTIDO = """
MATCH (p:Partido {partidoId: $partidoId})
OPTIONAL MATCH (p)<-[:OCURRE_EN]-(v:EventoDeportivo)
WITH p, v
ORDER BY v.minuto, v.eventoId
LIMIT $limite
OPTIONAL MATCH (v)-[i:INVOLUCRA]->(j:Jugador)-[:PERTENECE_A]->(eq:Equipo)-[:DISPUTA]->(p)
WITH p, v, i, j, eq
ORDER BY v.minuto, v.eventoId, CASE i.rol WHEN 'SALE' THEN 0 ELSE 1 END, j.jugadorId
WITH p, v, collect(CASE WHEN j IS NULL THEN null ELSE {
  jugadorId: j.jugadorId, nombre: j.nombre, apellido: j.apellido,
  equipoId: eq.equipoId, rol: i.rol
} END) AS participantes
ORDER BY v.minuto, v.eventoId
RETURN p.partidoId AS partidoId, collect(CASE WHEN v IS NULL THEN null ELSE {
  eventoId: v.eventoId, tipo: v.tipo, minuto: v.minuto, participantes: participantes
} END) AS eventos
"""

# CU-07 (Q09). Rango semiabierto [desde, hasta) sobre idx_partido_inicio.
PARTIDOS_POR_FECHA = """
MATCH (p:Partido)-[:SE_JUEGA_EN]->(s:Estadio)
WHERE p.inicio >= $desde AND p.inicio < $hasta
  AND ($estadioId IS NULL OR s.estadioId = $estadioId)
RETURN p.partidoId AS partidoId, p.inicio AS inicio, p.grupo AS grupo, p.fase AS fase,
       {estadioId: s.estadioId, nombre: s.nombre, ciudad: s.ciudad} AS estadio
ORDER BY p.inicio, p.partidoId
LIMIT $limite
"""

# Catálogo de partidos en memoria (casos_de_uso.md §3.2).
CATALOGO_PARTIDOS = """
MATCH (e:Equipo)-[:DISPUTA]->(p:Partido)
WITH p, e
ORDER BY e.equipoId
RETURN p.partidoId AS partidoId, collect(e.equipoId) AS equipos
ORDER BY partidoId
LIMIT $limite
"""


def _a_utc(valor):
    """DateTime de Neo4j → datetime aware en UTC (Pydantic lo serializa con Z)."""
    if isinstance(valor, DateTime):
        return valor.to_native().astimezone(UTC)
    return valor


def _es_timeout_de_transaccion(exc: Neo4jError) -> bool:
    # Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration (5.x y 2025.x)
    # o Neo.TransientError.Transaction.TransactionTimedOut (versiones anteriores).
    return "TransactionTimedOut" in (exc.code or "")


class AdaptadorNeo4j:
    def __init__(self, settings: Settings, driver: Driver | None = None) -> None:
        # El driver conecta en la primera consulta: la API arranca aunque Neo4j esté caído.
        self._driver = driver or GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
            connection_timeout=settings.neo4j_connection_timeout_s,
            connection_acquisition_timeout=settings.neo4j_connection_timeout_s,
            user_agent="fixture2030-h10",
            # Las notificaciones del servidor se registran con el texto del Cypher: se apagan.
            notifications_min_severity=NotificationMinimumSeverity.OFF,
        )
        self._database = settings.neo4j_database
        self._tx_timeout_s = settings.neo4j_tx_timeout_s

    def cerrar(self) -> None:
        self._driver.close()

    @contextmanager
    def _traducir(self, operacion: str) -> Iterator[None]:
        """Traduce excepciones del driver y registra dependencia, resultado y duración.

        Nunca se registra el Cypher ni los parámetros.
        """
        inicio = time.perf_counter()
        resultado = "ok"
        try:
            yield
        except (ServiceUnavailable, SessionExpired) as exc:
            resultado = "DEPENDENCIA_NO_DISPONIBLE"
            raise DependenciaNoDisponible(DEPENDENCIA) from exc
        except Neo4jError as exc:
            if _es_timeout_de_transaccion(exc):
                resultado = "DEPENDENCIA_TIMEOUT"
                raise DependenciaTimeout(DEPENDENCIA) from exc
            # Autenticación, sintaxis u otra falla de configuración: 500, tipo solo en el log.
            resultado = f"ERROR_INTERNO tipo={type(exc).__name__} codigo={exc.code}"
            raise ErrorDominio() from exc
        except DriverError as exc:
            resultado = f"ERROR_INTERNO tipo={type(exc).__name__}"
            raise ErrorDominio() from exc
        finally:
            duracion_ms = (time.perf_counter() - inicio) * 1000
            logger.info(
                "dependencia=%s operacion=%s resultado=%s duracion_ms=%.1f",
                DEPENDENCIA, operacion, resultado, duracion_ms,
            )

    def _leer(self, operacion: str, cypher: str, parametros: dict) -> list[dict]:
        """Transacción de lectura auto-commit, sin reintentos automáticos del driver
        (execute_read reintenta hasta 30 s y excedería el límite de §6.3)."""
        with self._traducir(operacion):
            with self._driver.session(
                database=self._database, default_access_mode=READ_ACCESS
            ) as sesion:
                resultado = sesion.run(Query(cypher, timeout=self._tx_timeout_s), parametros)
                return [registro.data() for registro in resultado]

    # CU-05
    def agenda_equipo(self, equipo_id: str, limite: int) -> list[dict] | None:
        """Partidos del equipo con rival, rol y estadio. None si el equipo no existe."""
        filas = self._leer("agenda_equipo", AGENDA_EQUIPO,
                           {"equipoId": equipo_id, "limite": limite})
        if not filas:
            return None
        partidos = filas[0]["partidos"]
        for partido in partidos:
            partido["inicio"] = _a_utc(partido["inicio"])
        return partidos

    # CU-06
    def eventos_partido(self, partido_id: str, limite: int) -> list[dict] | None:
        """Eventos del partido con sus participantes. None si el partido no existe."""
        filas = self._leer("eventos_partido", EVENTOS_PARTIDO,
                           {"partidoId": partido_id, "limite": limite})
        if not filas:
            return None
        return filas[0]["eventos"]

    # CU-07
    def partidos_por_fecha(self, desde: datetime, hasta: datetime,
                           estadio_id: str | None, limite: int) -> list[dict]:
        filas = self._leer("partidos_por_fecha", PARTIDOS_POR_FECHA, {
            "desde": desde, "hasta": hasta, "estadioId": estadio_id, "limite": limite,
        })
        for fila in filas:
            fila["inicio"] = _a_utc(fila["inicio"])
        return filas

    # Catálogo de partidos (§3.2)
    def cargar_catalogo_partidos(self) -> dict[str, tuple[str, ...]]:
        """partidoId → equipoIds que lo disputan (los dos de DISPUTA)."""
        filas = self._leer("cargar_catalogo_partidos", CATALOGO_PARTIDOS,
                           {"limite": LIMITE_CATALOGO})
        if len(filas) >= LIMITE_CATALOGO:
            logger.warning("dependencia=%s operacion=cargar_catalogo_partidos "
                           "resultado=limite_alcanzado limite=%d", DEPENDENCIA, LIMITE_CATALOGO)
        return {f["partidoId"]: tuple(f["equipos"]) for f in filas}

    def ping(self) -> bool:
        """Chequeo de salud: True si Neo4j responde. Nunca lanza."""
        try:
            self._leer("ping", "RETURN 1 AS ok", {})
            return True
        except ErrorDominio:
            return False
