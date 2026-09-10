// L01-L05. Dataset sintetico, no oficial. Ejecutar con cypher-shell.
// Una transaccion: un error aborta toda la carga. MERGE solo por identidad.
// No se elimina ningun dato. Recarga restaura las propiedades declaradas.
:begin
// L01: mismos IDs, nombres, codigos y confederaciones que Hito 4.
UNWIND range(1,64) AS i
MERGE (e:Equipo {equipoId:'EQ-'+right('000'+toString(i),3)})
SET e.codigo='F'+right('00'+toString(i),2),
    e.nombre='Seleccion Sintetica '+right('00'+toString(i),2),
    e.confederacion=['AFC','CAF','CONCACAF','CONMEBOL','OFC','UEFA'][(i-1)%6],
    e.origen='sintetico-grupo13-v1', e.esDatoSintetico=true
RETURN 'L01' AS codigo, count(e) AS equipos;
// L02: la referencia equipoId del documento pasa a ser PERTENECE_A.
UNWIND range(1,64) AS i
MATCH (e:Equipo {equipoId:'EQ-'+right('000'+toString(i),3)})
UNWIND range(1,24) AS camiseta
WITH e,camiseta,(i-1)*24+camiseta AS numero
MERGE (j:Jugador {jugadorId:'JUG-'+right('0000'+toString(numero),4)})
SET j.nombre='Nombre'+right('0000'+toString(numero),4),
    j.apellido='Apellido'+right('0000'+toString(numero),4),
    j.posicion=CASE WHEN camiseta<=3 THEN 'ARQUERO' WHEN camiseta<=11 THEN 'DEFENSOR'
                   WHEN camiseta<=19 THEN 'MEDIOCAMPISTA' ELSE 'DELANTERO' END,
    j.origen='sintetico-grupo13-v1', j.esDatoSintetico=true
MERGE (j)-[r:PERTENECE_A]->(e)
SET r.numeroCamiseta=camiseta
RETURN 'L02' AS codigo, count(j) AS jugadores;
// L03: ocho estadios ficticios; no representan sedes oficiales.
UNWIND range(1,8) AS i
MERGE (s:Estadio {estadioId:'EST-'+right('00'+toString(i),2)})
SET s.nombre='Estadio Sintetico '+right('00'+toString(i),2),
    s.ciudad='Ciudad Sede '+right('00'+toString(i),2),
    s.origen='sintetico-grupo13-v1', s.esDatoSintetico=true
RETURN 'L03' AS codigo, count(s) AS estadios;
// L04: 16 grupos ficticios de cuatro; dos jornadas, dos encuentros por grupo/jornada.
// J1: 1-2,3-4; J2: 1-3,2-4. Cada equipo tiene dos partidos y dos rivales.
UNWIND range(1,64) AS i
WITH i, toInteger((i-1)/32)+1 AS jornada, toInteger(((i-1)%32)/2)+1 AS grupo, (i-1)%2 AS par
WITH *, (grupo-1)*4 AS base,
 CASE WHEN jornada=1 THEN [par*2+1,par*2+2] ELSE [par+1,par+3] END AS pareja
MATCH (local:Equipo {equipoId:'EQ-'+right('000'+toString(base+pareja[0]),3)}),
      (visitante:Equipo {equipoId:'EQ-'+right('000'+toString(base+pareja[1]),3)}),
      (s:Estadio {estadioId:'EST-'+right('00'+toString((i-1)%8+1),2)})
MERGE (p:Partido {partidoId:'PAR-'+right('000'+toString(i),3)})
SET p.grupo='G'+right('00'+toString(grupo),2), p.jornada=jornada,
    p.fase='GRUPOS_MUESTRA', p.estado='FINALIZADO',
    p.inicio=datetime('2030-06-10T18:00:00Z')+duration({days:toInteger((i-1)/8)}),
    p.origen='sintetico-grupo13-v1', p.esDatoSintetico=true
MERGE (local)-[dl:DISPUTA]->(p) SET dl.rol='LOCAL'
MERGE (visitante)-[dv:DISPUTA]->(p) SET dv.rol='VISITANTE'
MERGE (p)-[:SE_JUEGA_EN]->(s)
RETURN 'L04' AS codigo, count(p) AS partidos;
// L05: dos sustituciones por partido, una de cada equipo, con SALE y ENTRA.
// Incidencias discretas: no se guardan goles, contadores ni series de rendimiento.
MATCH (e:Equipo)-[d:DISPUTA]->(p:Partido)
WHERE p.origen='sintetico-grupo13-v1'
MATCH (sale:Jugador)-[:PERTENECE_A {numeroCamiseta:20}]->(e),
      (entra:Jugador)-[:PERTENECE_A {numeroCamiseta:21}]->(e)
MERGE (v:EventoDeportivo {eventoId:'EVT-'+p.partidoId+'-'+d.rol})
SET v.tipo='SUSTITUCION', v.minuto=CASE d.rol WHEN 'LOCAL' THEN 60 ELSE 65 END,
    v.origen='sintetico-grupo13-v1', v.esDatoSintetico=true
MERGE (v)-[:OCURRE_EN]->(p)
MERGE (v)-[rs:INVOLUCRA]->(sale) SET rs.rol='SALE'
MERGE (v)-[re:INVOLUCRA]->(entra) SET re.rol='ENTRA'
RETURN 'L05' AS codigo, count(v) AS eventos;
:commit
