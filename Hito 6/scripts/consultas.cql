USE fixture2030_comentarios;
CONSISTENCY ONE;
-- IN de particiones con ORDER BY exige desactivar la paginación.
-- Se mantienen límites pequeños y un máximo documentado de 24 particiones.
PAGING OFF;

-- Q1. Recientes del minuto 18:01 de PAR-001, hasta 20 en total.
SELECT creado_en, comentario_id, usuario_id, contenido, estado, likes
FROM comentarios_por_partido
WHERE partido_id = 'PAR-001' AND minuto = '2030-06-10T18:01:00Z'
  AND segmento IN (0, 1, 2, 3)
ORDER BY creado_en DESC, comentario_id ASC
LIMIT 20;

-- Q2. Ventana [18:00:30, 18:02:10) que cruza tres minutos y 12 particiones.
SELECT creado_en, comentario_id, usuario_id, contenido, estado, likes
FROM comentarios_por_partido
WHERE partido_id = 'PAR-001'
  AND minuto IN ('2030-06-10T18:00:00Z', '2030-06-10T18:01:00Z', '2030-06-10T18:02:00Z')
  AND segmento IN (0, 1, 2, 3)
  AND creado_en >= '2030-06-10T18:00:30Z' AND creado_en < '2030-06-10T18:02:10Z'
ORDER BY creado_en DESC, comentario_id ASC
LIMIT 50;

-- Q3. Historial diario del autor sin recorrer las particiones de partidos.
SELECT creado_en, comentario_id, partido_id, contenido, estado, likes
FROM comentarios_por_usuario
WHERE usuario_id = 'USR-00001' AND dia = '2030-06-10'
ORDER BY creado_en DESC, comentario_id ASC
LIMIT 20;

PAGING ON;
