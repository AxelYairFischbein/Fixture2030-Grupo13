// V02: representacion estable de TODAS las propiedades, etiquetas y extremos.
// Se conservan los valores nativos: el numero 1 se distingue del texto '1'.
// Lectura global permitida; no modifica ni elimina datos.
CALL {
MATCH (n)
UNWIND keys(n) AS k
WITH n,k ORDER BY k
WITH n,collect([k,n[k]]) AS propiedades
RETURN labels(n)[0] AS tipo,coalesce(n.equipoId,n.jugadorId,n.partidoId,n.estadioId,n.eventoId) AS identidad,
       propiedades
UNION ALL
MATCH (a)-[r]->(b)
CALL (r) {
  UNWIND keys(r) AS k
  WITH r,k ORDER BY k
  RETURN collect([k,r[k]]) AS propiedades
}
RETURN type(r) AS tipo,
       coalesce(a.equipoId,a.jugadorId,a.partidoId,a.estadioId,a.eventoId)+'->'+
       coalesce(b.equipoId,b.jugadorId,b.partidoId,b.estadioId,b.eventoId) AS identidad,propiedades
}
RETURN tipo,identidad,propiedades
ORDER BY tipo,identidad;
