// P01: plan real para el mismo rango de Q09; no se compara latencia.
PROFILE
MATCH (p:Partido)-[:SE_JUEGA_EN]->(s:Estadio)
WHERE p.inicio>=datetime('2030-06-10T00:00:00Z') AND p.inicio<datetime('2030-06-11T00:00:00Z')
RETURN p.partidoId AS partido,p.inicio AS inicio,s.estadioId AS estadio ORDER BY inicio,partido;
