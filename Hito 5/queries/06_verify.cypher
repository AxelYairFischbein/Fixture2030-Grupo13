// V01: 44 controles, todos deben devolver ok=true. No modifica el grafo.
// cantidad_Equipo
MATCH (n:Equipo)
WITH count(n) AS actual
RETURN 'cantidad_Equipo' AS control,actual,64 AS esperado,actual=64 AS ok

UNION ALL

// cantidad_Jugador
MATCH (n:Jugador)
WITH count(n) AS actual
RETURN 'cantidad_Jugador' AS control,actual,1536 AS esperado,actual=1536 AS ok

UNION ALL

// cantidad_Partido
MATCH (n:Partido)
WITH count(n) AS actual
RETURN 'cantidad_Partido' AS control,actual,64 AS esperado,actual=64 AS ok

UNION ALL

// cantidad_Estadio
MATCH (n:Estadio)
WITH count(n) AS actual
RETURN 'cantidad_Estadio' AS control,actual,8 AS esperado,actual=8 AS ok

UNION ALL

// cantidad_EventoDeportivo
MATCH (n:EventoDeportivo)
WITH count(n) AS actual
RETURN 'cantidad_EventoDeportivo' AS control,actual,128 AS esperado,actual=128 AS ok

UNION ALL

// relaciones_PERTENECE_A
MATCH ()-[r:PERTENECE_A]->()
WITH count(r) AS actual
RETURN 'relaciones_PERTENECE_A' AS control,actual,1536 AS esperado,actual=1536 AS ok

UNION ALL

// relaciones_DISPUTA
MATCH ()-[r:DISPUTA]->()
WITH count(r) AS actual
RETURN 'relaciones_DISPUTA' AS control,actual,128 AS esperado,actual=128 AS ok

UNION ALL

// relaciones_SE_JUEGA_EN
MATCH ()-[r:SE_JUEGA_EN]->()
WITH count(r) AS actual
RETURN 'relaciones_SE_JUEGA_EN' AS control,actual,64 AS esperado,actual=64 AS ok

UNION ALL

// relaciones_OCURRE_EN
MATCH ()-[r:OCURRE_EN]->()
WITH count(r) AS actual
RETURN 'relaciones_OCURRE_EN' AS control,actual,128 AS esperado,actual=128 AS ok

UNION ALL

// relaciones_INVOLUCRA
MATCH ()-[r:INVOLUCRA]->()
WITH count(r) AS actual
RETURN 'relaciones_INVOLUCRA' AS control,actual,256 AS esperado,actual=256 AS ok

UNION ALL

// total_nodos
MATCH (n)
WITH count(n) AS actual
RETURN 'total_nodos' AS control,actual,1800 AS esperado,actual=1800 AS ok

UNION ALL

// total_relaciones
MATCH ()-[r]->()
WITH count(r) AS actual
RETURN 'total_relaciones' AS control,actual,2112 AS esperado,actual=2112 AS ok

UNION ALL

// duplicados_equipoId
MATCH (n:Equipo)
WITH n.equipoId AS id,count(n) AS cantidad
WHERE id IS NULL OR cantidad<>1
WITH count(*) AS actual
RETURN 'duplicados_equipoId' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// duplicados_codigo
MATCH (n:Equipo)
WITH n.codigo AS id,count(n) AS cantidad
WHERE id IS NULL OR cantidad<>1
WITH count(*) AS actual
RETURN 'duplicados_codigo' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// duplicados_jugadorId
MATCH (n:Jugador)
WITH n.jugadorId AS id,count(n) AS cantidad
WHERE id IS NULL OR cantidad<>1
WITH count(*) AS actual
RETURN 'duplicados_jugadorId' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// duplicados_partidoId
MATCH (n:Partido)
WITH n.partidoId AS id,count(n) AS cantidad
WHERE id IS NULL OR cantidad<>1
WITH count(*) AS actual
RETURN 'duplicados_partidoId' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// duplicados_estadioId
MATCH (n:Estadio)
WITH n.estadioId AS id,count(n) AS cantidad
WHERE id IS NULL OR cantidad<>1
WITH count(*) AS actual
RETURN 'duplicados_estadioId' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// duplicados_eventoId
MATCH (n:EventoDeportivo)
WITH n.eventoId AS id,count(n) AS cantidad
WHERE id IS NULL OR cantidad<>1
WITH count(*) AS actual
RETURN 'duplicados_eventoId' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// jugadores_sin_equipo
MATCH (j:Jugador)
WHERE NOT (j)-[:PERTENECE_A]->(:Equipo)
WITH count(j) AS actual
RETURN 'jugadores_sin_equipo' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// jugadores_pertenencia_invalida
MATCH (j:Jugador)
OPTIONAL MATCH (j)-[r:PERTENECE_A]->(:Equipo)
WITH j,count(r) AS cantidad
WHERE cantidad<>1
WITH count(j) AS actual
RETURN 'jugadores_pertenencia_invalida' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// planteles_distintos_de_24
MATCH (e:Equipo)
OPTIONAL MATCH (:Jugador)-[r:PERTENECE_A]->(e)
WITH e,count(r) AS cantidad
WHERE cantidad<>24
WITH count(e) AS actual
RETURN 'planteles_distintos_de_24' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// camisetas_duplicadas
MATCH (:Jugador)-[r:PERTENECE_A]->(e:Equipo)
WITH e,r.numeroCamiseta AS camiseta,count(r) AS cantidad
WHERE camiseta IS NULL OR cantidad<>1 OR camiseta<1 OR camiseta>24
WITH count(*) AS actual
RETURN 'camisetas_duplicadas' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// relaciones_duplicadas
MATCH (a)-[r]->(b)
WITH a,b,type(r) AS tipo,count(r) AS cantidad
WHERE cantidad<>1
WITH count(*) AS actual
RETURN 'relaciones_duplicadas' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// partidos_equipos_invalidos
MATCH (p:Partido)
OPTIONAL MATCH (e:Equipo)-[r:DISPUTA]->(p)
WITH p,count(r) AS cantidad,count(DISTINCT e) AS equipos,collect(r.rol) AS roles
WHERE cantidad<>2 OR equipos<>2 OR NOT 'LOCAL' IN roles OR NOT 'VISITANTE' IN roles
WITH count(p) AS actual
RETURN 'partidos_equipos_invalidos' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// partidos_sede_invalida
MATCH (p:Partido)
OPTIONAL MATCH (p)-[r:SE_JUEGA_EN]->(:Estadio)
WITH p,count(r) AS cantidad
WHERE cantidad<>1
WITH count(p) AS actual
RETURN 'partidos_sede_invalida' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// eventos_partido_invalido
MATCH (v:EventoDeportivo)
OPTIONAL MATCH (v)-[r:OCURRE_EN]->(:Partido)
WITH v,count(r) AS cantidad
WHERE cantidad<>1
WITH count(v) AS actual
RETURN 'eventos_partido_invalido' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// partidos_eventos_invalidos
MATCH (p:Partido)
OPTIONAL MATCH (:EventoDeportivo)-[r:OCURRE_EN]->(p)
WITH p,count(r) AS cantidad
WHERE cantidad<>2
WITH count(p) AS actual
RETURN 'partidos_eventos_invalidos' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// eventos_participantes_invalidos
MATCH (v:EventoDeportivo)
OPTIONAL MATCH (v)-[r:INVOLUCRA]->(j:Jugador)
WITH v,count(r) AS cantidad,count(DISTINCT j) AS jugadores,collect(r.rol) AS roles
WHERE cantidad<>2 OR jugadores<>2 OR NOT 'SALE' IN roles OR NOT 'ENTRA' IN roles
WITH count(v) AS actual
RETURN 'eventos_participantes_invalidos' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// participantes_ajenos_al_partido
MATCH (v:EventoDeportivo)-[:OCURRE_EN]->(p:Partido),(v)-[:INVOLUCRA]->(j:Jugador)
WHERE NOT EXISTS { MATCH (j)-[:PERTENECE_A]->(:Equipo)-[:DISPUTA]->(p) }
WITH count(*) AS actual
RETURN 'participantes_ajenos_al_partido' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// sustituciones_equipos_distintos
MATCH (v:EventoDeportivo)-[:INVOLUCRA]->(:Jugador)-[:PERTENECE_A]->(e:Equipo)
WITH v,count(DISTINCT e) AS equipos
WHERE equipos<>1
WITH count(v) AS actual
RETURN 'sustituciones_equipos_distintos' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// equipos_partidos_invalidos
MATCH (e:Equipo)
OPTIONAL MATCH (e)-[r:DISPUTA]->(:Partido)
WITH e,count(r) AS cantidad
WHERE cantidad<>2
WITH count(e) AS actual
RETURN 'equipos_partidos_invalidos' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// conflictos_estadio_hora
MATCH (p:Partido)-[:SE_JUEGA_EN]->(s:Estadio)
WITH s,p.inicio AS inicio,count(p) AS cantidad
WHERE cantidad>1
WITH count(*) AS actual
RETURN 'conflictos_estadio_hora' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// conflictos_equipo_hora
MATCH (e:Equipo)-[:DISPUTA]->(p:Partido)
WITH e,p.inicio AS inicio,count(p) AS cantidad
WHERE cantidad>1
WITH count(*) AS actual
RETURN 'conflictos_equipo_hora' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// etiquetas_ajenas
MATCH (n)
WHERE size(labels(n))<>1 OR NOT labels(n)[0] IN ['Equipo','Jugador','Partido','Estadio','EventoDeportivo']
WITH count(n) AS actual
RETURN 'etiquetas_ajenas' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// extremos_y_direcciones_invalidos
MATCH (a)-[r]->(b)
WHERE NOT ((a:Jugador AND type(r)='PERTENECE_A' AND b:Equipo) OR (a:Equipo AND type(r)='DISPUTA' AND b:Partido) OR (a:Partido AND type(r)='SE_JUEGA_EN' AND b:Estadio) OR (a:EventoDeportivo AND type(r)='OCURRE_EN' AND b:Partido) OR (a:EventoDeportivo AND type(r)='INVOLUCRA' AND b:Jugador))
WITH count(r) AS actual
RETURN 'extremos_y_direcciones_invalidos' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// procedencia_invalida
MATCH (n)
WHERE coalesce(n.origen,'')<>'sintetico-grupo13-v1' OR coalesce(n.esDatoSintetico,false)<>true
WITH count(n) AS actual
RETURN 'procedencia_invalida' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// estadisticas_fuera_de_alcance
MATCH (n)
WHERE any(k IN keys(n)
WHERE k IN ['goles','ranking','rankingReferencia','partidosInternacionales','golesInternacionales','participacionesMundiales','titulosMundiales'])
WITH count(n) AS actual
RETURN 'estadisticas_fuera_de_alcance' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// identidad_y_pertenencia_hito4
MATCH (j:Jugador)-[r:PERTENECE_A]->(e:Equipo)
WITH j,r,e,toInteger(substring(j.jugadorId,4)) AS numero
WHERE numero<1 OR numero>1536 OR j.jugadorId<>'JUG-'+right('0000'+toString(numero),4) OR e.equipoId<>'EQ-'+right('000'+toString(toInteger((numero-1)/24)+1),3) OR r.numeroCamiseta<>(numero-1)%24+1 OR j.nombre<>'Nombre'+right('0000'+toString(numero),4) OR j.apellido<>'Apellido'+right('0000'+toString(numero),4)
WITH count(j) AS actual
RETURN 'identidad_y_pertenencia_hito4' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// identidad_equipo_hito4
MATCH (e:Equipo)
WITH e,toInteger(substring(e.equipoId,3)) AS numero
WHERE numero<1 OR numero>64 OR e.equipoId<>'EQ-'+right('000'+toString(numero),3) OR e.codigo<>'F'+right('00'+toString(numero),2) OR e.nombre<>'Seleccion Sintetica '+right('00'+toString(numero),2) OR e.confederacion<>['AFC','CAF','CONCACAF','CONMEBOL','OFC','UEFA'][(numero-1)%6]
WITH count(e) AS actual
RETURN 'identidad_equipo_hito4' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// campos_ausentes_Equipo
MATCH (n:Equipo)
WHERE any(k IN ['equipoId', 'codigo', 'nombre', 'confederacion']
WHERE n[k] IS NULL)
WITH count(n) AS actual
RETURN 'campos_ausentes_Equipo' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// campos_ausentes_Jugador
MATCH (n:Jugador)
WHERE any(k IN ['jugadorId', 'nombre', 'apellido', 'posicion']
WHERE n[k] IS NULL)
WITH count(n) AS actual
RETURN 'campos_ausentes_Jugador' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// campos_ausentes_Partido
MATCH (n:Partido)
WHERE any(k IN ['partidoId', 'grupo', 'jornada', 'fase', 'estado', 'inicio']
WHERE n[k] IS NULL)
WITH count(n) AS actual
RETURN 'campos_ausentes_Partido' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// campos_ausentes_Estadio
MATCH (n:Estadio)
WHERE any(k IN ['estadioId', 'nombre', 'ciudad']
WHERE n[k] IS NULL)
WITH count(n) AS actual
RETURN 'campos_ausentes_Estadio' AS control,actual,0 AS esperado,actual=0 AS ok

UNION ALL

// campos_ausentes_EventoDeportivo
MATCH (n:EventoDeportivo)
WHERE any(k IN ['eventoId', 'tipo', 'minuto']
WHERE n[k] IS NULL)
WITH count(n) AS actual
RETURN 'campos_ausentes_EventoDeportivo' AS control,actual,0 AS esperado,actual=0 AS ok
ORDER BY control;
