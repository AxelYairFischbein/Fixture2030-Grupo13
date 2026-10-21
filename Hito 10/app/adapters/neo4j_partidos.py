"""Adaptador de grafos (Hito 5): partidos, equipos, estadios y eventos en Neo4j."""

from neo4j import GraphDatabase, Query, RoutingControl
from neo4j.exceptions import Neo4jError, DriverError

from app.contexto import operacion

ERRORES = (Neo4jError, DriverError, OSError)

# Cypher fijo y parametrizado: el consumidor solo aporta identificadores ya validados.
Q_PARTIDO = """
MATCH (p:Partido {partidoId: $partidoId})
OPTIONAL MATCH (p)-[:SE_JUEGA_EN]->(s:Estadio)
OPTIONAL MATCH (e:Equipo)-[d:DISPUTA]->(p)
WITH p, s, e, d ORDER BY d.rol
RETURN p {.partidoId, .grupo, .fase, .estado, .jornada, inicio: toString(p.inicio)} AS partido,
       s {.estadioId, .nombre, .ciudad} AS estadio,
       collect(e {.equipoId, .codigo, .nombre, rol: d.rol}) AS equipos
"""

Q_EVENTOS = """
MATCH (v:EventoDeportivo)-[:OCURRE_EN]->(:Partido {partidoId: $partidoId})
OPTIONAL MATCH (v)-[r:INVOLUCRA]->(j:Jugador)
WITH v, r, j ORDER BY r.rol DESC
WITH v, collect(j {.jugadorId, .nombre, .apellido, rol: r.rol}) AS involucrados
RETURN v.eventoId AS eventoId, v.tipo AS tipo, v.minuto AS minuto, involucrados
ORDER BY minuto, eventoId
LIMIT $limite
"""

Q_AGENDA = """
MATCH (e:Equipo {equipoId: $equipoId})
OPTIONAL MATCH (e)-[r:DISPUTA]->(p:Partido)-[:SE_JUEGA_EN]->(s:Estadio)
OPTIONAL MATCH (rival:Equipo)-[:DISPUTA]->(p) WHERE rival <> e
WITH e, r, p, s, rival ORDER BY p.inicio, p.partidoId
RETURN e.equipoId AS equipoId,
       collect(p {.partidoId, .grupo, .estado, inicio: toString(p.inicio), rol: r.rol,
                  estadioId: s.estadioId, rivalId: rival.equipoId})[..$limite] AS partidos
"""


class Neo4jPartidos:
    nombre = "neo4j"

    def __init__(self, cfg):
        self._db = cfg.neo4j_database
        self._timeout = cfg.timeout
        self._driver = GraphDatabase.driver(
            cfg.neo4j_uri, auth=(cfg.neo4j_user, cfg.neo4j_password),
            connection_timeout=cfg.timeout, connection_acquisition_timeout=cfg.timeout,
            max_transaction_retry_time=cfg.timeout,
        )

    def _leer(self, cypher: str, **parametros):
        registros, _, _ = self._driver.execute_query(
            Query(cypher, timeout=self._timeout), parametros,
            database_=self._db, routing_=RoutingControl.READ,
        )
        return registros

    def ping(self):
        with operacion(self.nombre, "ping", ERRORES):
            self._leer("RETURN 1")

    def partido(self, partido_id: str) -> dict | None:
        with operacion(self.nombre, "partido", ERRORES):
            filas = self._leer(Q_PARTIDO, partidoId=partido_id)
        if not filas:
            return None
        fila = filas[0]
        return {**fila["partido"], "estadio": fila["estadio"], "equipos": fila["equipos"]}

    def eventos(self, partido_id: str, limite: int) -> list[dict]:
        with operacion(self.nombre, "eventos", ERRORES):
            return [dict(r) for r in self._leer(Q_EVENTOS, partidoId=partido_id, limite=limite)]

    def agenda(self, equipo_id: str, limite: int) -> list[dict] | None:
        with operacion(self.nombre, "agenda", ERRORES):
            filas = self._leer(Q_AGENDA, equipoId=equipo_id, limite=limite)
        return filas[0]["partidos"] if filas else None
