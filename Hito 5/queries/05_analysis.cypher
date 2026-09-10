// @query A01
// Camino minimo de encuentros entre EQ-001 y EQ-004, hasta 6 relaciones.
// Solo DISPUTA: compartir estadio no equivale a competir entre si.
MATCH (a:Equipo {equipoId:'EQ-001'}),(b:Equipo {equipoId:'EQ-004'})
MATCH camino=allShortestPaths((a)-[:DISPUTA*1..6]-(b))
WITH camino,[n IN nodes(camino)|coalesce(n.equipoId,n.partidoId)] AS entidades
WITH camino,entidades ORDER BY entidades LIMIT 1
RETURN length(camino) AS saltos,
       reduce(texto='',id IN entidades|texto+CASE WHEN texto='' THEN '' ELSE ' -> ' END+id) AS entidades;

// @query A02
// Control de conectividad entre grupos distintos, en la misma proyeccion y cota.
MATCH (a:Equipo {equipoId:'EQ-001'}),(b:Equipo {equipoId:'EQ-005'})
OPTIONAL MATCH camino=shortestPath((a)-[:DISPUTA*1..6]-(b))
RETURN a.equipoId AS origen,b.equipoId AS destino,camino IS NOT NULL AS conectado;
