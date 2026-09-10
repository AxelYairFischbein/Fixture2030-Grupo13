// B01: vista general acotada al primer grupo: 4 equipos, 4 partidos,
// 2 estadios, 8 eventos y 8 jugadores involucrados. No dibujar 1.800 nodos a la vez.
MATCH camino=(p:Partido {grupo:'G01'})<-[:DISPUTA]-(e:Equipo)
RETURN camino
UNION ALL
MATCH camino=(p:Partido {grupo:'G01'})-[:SE_JUEGA_EN]->(:Estadio)
RETURN camino
UNION ALL
MATCH camino=(p:Partido {grupo:'G01'})<-[:OCURRE_EN]-(:EventoDeportivo)-[:INVOLUCRA]->(:Jugador)
RETURN camino;

// B02: tres saltos; los dos partidos de un jugador y sus estadios.
MATCH camino=(:Jugador {jugadorId:'JUG-0001'})-[:PERTENECE_A]->(:Equipo)-[:DISPUTA]->(:Partido)-[:SE_JUEGA_EN]->(:Estadio)
RETURN camino;

// B03: evidencia visual de carga y cardinalidades (vista Table).
MATCH (n)
RETURN labels(n)[0] AS etiqueta,count(n) AS cantidad ORDER BY etiqueta;
