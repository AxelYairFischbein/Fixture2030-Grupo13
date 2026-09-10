// Consultas autonomas: modificar los valores WITH para cambiar filtros.
// @query Q01
// Plantel de un equipo: pertenencia inmediata y orden de camiseta.
WITH 'EQ-001' AS equipoId
MATCH (j:Jugador)-[r:PERTENECE_A]->(e:Equipo {equipoId:equipoId})
RETURN j.jugadorId AS jugador,j.nombre AS nombre,j.apellido AS apellido,j.posicion AS posicion,r.numeroCamiseta AS camiseta
ORDER BY camiseta,jugador;

// @query Q02
// Equipos con partidos en el estadio, sin repetirlos por jornada.
WITH 'EST-01' AS estadioId
MATCH (e:Equipo)-[:DISPUTA]->(:Partido)-[:SE_JUEGA_EN]->(:Estadio {estadioId:estadioId})
RETURN DISTINCT e.equipoId AS equipo,e.nombre AS nombre ORDER BY equipo;

// @query Q03
// Planteles cuyos equipos disputan PAR-001. No implica presencia en cancha.
WITH ['PAR-001'] AS partidos
MATCH (j:Jugador)-[:PERTENECE_A]->(e:Equipo)-[:DISPUTA]->(p:Partido)
WHERE p.partidoId IN partidos
RETURN p.partidoId AS partido,e.equipoId AS equipo,j.jugadorId AS jugador ORDER BY partido,equipo,jugador;

// @query Q04
// Dos saltos: rivales reales del dataset a traves de partidos compartidos.
WITH 'EQ-001' AS equipoId
MATCH (e:Equipo {equipoId:equipoId})-[:DISPUTA]->(p:Partido)<-[:DISPUTA]-(rival:Equipo)
WHERE rival<>e
RETURN rival.equipoId AS rival,p.partidoId AS partido ORDER BY partido,rival;

// @query Q05
// Partido relacionado con una incidencia puntual identificada.
WITH 'EVT-PAR-001-LOCAL' AS eventoId
MATCH (v:EventoDeportivo {eventoId:eventoId})-[:OCURRE_EN]->(p:Partido)
RETURN v.eventoId AS evento,v.tipo AS tipo,v.minuto AS minuto,p.partidoId AS partido;

// @query Q06
// Agenda del equipo: partido, rol, hora UTC y estadio.
WITH 'EQ-001' AS equipoId
MATCH (:Equipo {equipoId:equipoId})-[r:DISPUTA]->(p:Partido)-[:SE_JUEGA_EN]->(s:Estadio)
RETURN p.partidoId AS partido,toString(p.inicio) AS inicio,r.rol AS rol,s.estadioId AS estadio
ORDER BY inicio,partido;

// @query Q07
// Evento, partido y participantes: valida tambien su pertenencia al equipo que disputa.
WITH 'PAR-001' AS partidoId
MATCH (p:Partido {partidoId:partidoId})<-[:OCURRE_EN]-(v:EventoDeportivo)-[r:INVOLUCRA]->(j:Jugador)
MATCH (j)-[:PERTENECE_A]->(e:Equipo)-[:DISPUTA]->(p)
RETURN v.eventoId AS evento,v.minuto AS minuto,r.rol AS rol,j.jugadorId AS jugador,e.equipoId AS equipo
ORDER BY minuto,evento,rol;

// @query Q08
// Tres saltos: jugador -> equipo -> partido -> estadio.
WITH 'JUG-0001' AS jugadorId
MATCH (j:Jugador {jugadorId:jugadorId})-[:PERTENECE_A]->(e:Equipo)-[:DISPUTA]->(p:Partido)-[:SE_JUEGA_EN]->(s:Estadio)
RETURN j.jugadorId AS jugador,e.equipoId AS equipo,p.partidoId AS partido,s.estadioId AS estadio
ORDER BY partido;

// @query Q09
// Filtro temporal con indice idx_partido_inicio; rango semiabierto.
WITH datetime('2030-06-10T00:00:00Z') AS desde,datetime('2030-06-11T00:00:00Z') AS hasta
MATCH (p:Partido)-[:SE_JUEGA_EN]->(s:Estadio)
WHERE p.inicio>=desde AND p.inicio<hasta
RETURN p.partidoId AS partido,toString(p.inicio) AS inicio,s.estadioId AS estadio ORDER BY inicio,partido;

// @query Q10
// Segunda pagina del plantel. Orden estable por ID antes de SKIP/LIMIT.
WITH 'EQ-001' AS equipoId
MATCH (j:Jugador)-[:PERTENECE_A]->(:Equipo {equipoId:equipoId})
RETURN j.jugadorId AS jugador ORDER BY jugador SKIP 5 LIMIT 5;

// @query Q11
// Cantidad de partidos programados por estadio; cuenta relaciones.
MATCH (p:Partido)-[:SE_JUEGA_EN]->(s:Estadio)
RETURN s.estadioId AS estadio,count(p) AS partidos ORDER BY estadio;

// @query Q12
// Filtro de atributo propio y top acotado, sin estadisticas deportivas.
WITH 'UEFA' AS confederacion
MATCH (e:Equipo) WHERE e.confederacion=confederacion
RETURN e.equipoId AS equipo,e.codigo AS codigo,e.confederacion AS confederacion ORDER BY equipo LIMIT 5;

// @query Q13
// Caso vacio interpretable: ningun plantel para un identificador inexistente.
MATCH (j:Jugador)-[:PERTENECE_A]->(:Equipo {equipoId:'EQ-999'})
RETURN count(j) AS jugadores;
