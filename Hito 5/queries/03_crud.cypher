// C01-C07: alta, lectura, cambio de propiedad, cambio de extremo y bajas.
// Transaccion atomica. Rango temporal reservado; nunca modifica el canon.
:begin
// C01: precondicion visible: ningun nodo con este ID debe existir.
MATCH (v:EventoDeportivo {eventoId:'CRUD-G13-EVT-001'})
WITH count(v) AS actual
RETURN 'C01_preexistentes' AS codigo, actual, 0 AS esperado;
// C02: alta de incidencia temporal sobre dos jugadores del mismo equipo.
MATCH (p:Partido {partidoId:'PAR-001'}),
      (a:Jugador {jugadorId:'JUG-0020'}), (b:Jugador {jugadorId:'JUG-0021'})
CREATE (v:EventoDeportivo {eventoId:'CRUD-G13-EVT-001',tipo:'SUSTITUCION',minuto:70,
                         origen:'crud-controlado-grupo13',esDatoSintetico:true})
CREATE (v)-[:OCURRE_EN]->(p), (v)-[:INVOLUCRA {rol:'SALE'}]->(a), (v)-[:INVOLUCRA {rol:'ENTRA'}]->(b)
RETURN 'C02_creado' AS codigo, count(v) AS actual, 1 AS esperado;
// C03: lectura de la incidencia y sus participantes.
MATCH (v:EventoDeportivo {eventoId:'CRUD-G13-EVT-001',origen:'crud-controlado-grupo13'})-[r:INVOLUCRA]->(j:Jugador)
RETURN 'C03_lectura' AS codigo,v.eventoId AS evento,v.minuto AS minuto,r.rol AS rol,j.jugadorId AS jugador ORDER BY rol;
// C04: corregir minuto y metadato de una relacion.
MATCH (v:EventoDeportivo {eventoId:'CRUD-G13-EVT-001',origen:'crud-controlado-grupo13'})-[r:INVOLUCRA {rol:'ENTRA'}]->(:Jugador {jugadorId:'JUG-0021'})
SET v.minuto=72, r.motivo='CORRECCION_DE_PLANILLA'
RETURN 'C04_actualizado' AS codigo,v.minuto AS actual,72 AS esperado,r.motivo AS motivo;
// C05: cambiar el participante; eliminar la relacion exacta y crear su reemplazo.
MATCH (v:EventoDeportivo {eventoId:'CRUD-G13-EVT-001',origen:'crud-controlado-grupo13'})-[r:INVOLUCRA {rol:'ENTRA'}]->(:Jugador {jugadorId:'JUG-0021'}),
      (nuevo:Jugador {jugadorId:'JUG-0022'})
DELETE r
CREATE (v)-[:INVOLUCRA {rol:'ENTRA',motivo:'CORRECCION_DE_PLANILLA'}]->(nuevo)
RETURN 'C05_reasignado' AS codigo,nuevo.jugadorId AS actual,'JUG-0022' AS esperado;
// C06: visualizar exactamente el nodo/relaciones que se eliminan.
MATCH (v:EventoDeportivo {eventoId:'CRUD-G13-EVT-001',origen:'crud-controlado-grupo13'})-[r]->(destino)
RETURN 'C06_previsualizacion' AS codigo,v.eventoId AS evento,type(r) AS relacion,
       coalesce(destino.jugadorId,destino.partidoId) AS destino ORDER BY relacion,destino;
// C07: baja precisa de un unico nodo reservado y sus tres relaciones.
MATCH (v:EventoDeportivo {eventoId:'CRUD-G13-EVT-001',origen:'crud-controlado-grupo13'})
DETACH DELETE v
RETURN 'C07_eliminado' AS codigo,count(*) AS actual,1 AS esperado;
MATCH (v:EventoDeportivo {eventoId:'CRUD-G13-EVT-001'})
WITH count(v) AS actual
RETURN 'C07_residuos' AS codigo,actual,0 AS esperado;
:commit
