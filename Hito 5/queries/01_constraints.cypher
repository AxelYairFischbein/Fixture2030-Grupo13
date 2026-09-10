// S01: unicidad de identificadores de negocio; repetible.
CREATE CONSTRAINT uq_equipo_id IF NOT EXISTS FOR (n:Equipo) REQUIRE n.equipoId IS UNIQUE;
CREATE CONSTRAINT uq_equipo_codigo IF NOT EXISTS FOR (n:Equipo) REQUIRE n.codigo IS UNIQUE;
CREATE CONSTRAINT uq_jugador_id IF NOT EXISTS FOR (n:Jugador) REQUIRE n.jugadorId IS UNIQUE;
CREATE CONSTRAINT uq_partido_id IF NOT EXISTS FOR (n:Partido) REQUIRE n.partidoId IS UNIQUE;
CREATE CONSTRAINT uq_estadio_id IF NOT EXISTS FOR (n:Estadio) REQUIRE n.estadioId IS UNIQUE;
CREATE CONSTRAINT uq_evento_id IF NOT EXISTS FOR (n:EventoDeportivo) REQUIRE n.eventoId IS UNIQUE;
// S02: rango temporal de la agenda, utilizado en Q09/P01.
CREATE RANGE INDEX idx_partido_inicio IF NOT EXISTS FOR (n:Partido) ON (n.inicio);
CALL db.awaitIndexes(120);
SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties RETURN * ORDER BY name;
SHOW INDEXES YIELD name, type, state, labelsOrTypes, properties, owningConstraint RETURN * ORDER BY name;
