USE fixture2030_comentarios;
CONSISTENCY ONE;

-- Alta identificada fuera de la muestra.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:03:00Z', 0, '2030-06-10T18:03:15Z', 'PRUEBA-CRUD-001', 'USR-PRUEBA', '2030-06-10', 'Comentario de prueba', 'pendiente', 0);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:03:00Z', 0, '2030-06-10T18:03:15Z', 'PRUEBA-CRUD-001', 'USR-PRUEBA', '2030-06-10', 'Comentario de prueba', 'pendiente', 0);
APPLY BATCH;

-- Lectura puntual en ambas representaciones.
SELECT comentario_id, contenido, estado, likes FROM comentarios_por_partido
WHERE partido_id = 'PAR-001' AND minuto = '2030-06-10T18:03:00Z' AND segmento = 0 AND creado_en = '2030-06-10T18:03:15Z' AND comentario_id = 'PRUEBA-CRUD-001';
SELECT comentario_id, contenido, estado, likes FROM comentarios_por_usuario
WHERE usuario_id = 'USR-PRUEBA' AND dia = '2030-06-10' AND creado_en = '2030-06-10T18:03:15Z' AND comentario_id = 'PRUEBA-CRUD-001';

-- Actualización delimitada por cada clave completa.
BEGIN BATCH
UPDATE comentarios_por_partido SET contenido = 'Comentario editado', estado = 'visible', likes = 3
WHERE partido_id = 'PAR-001' AND minuto = '2030-06-10T18:03:00Z' AND segmento = 0 AND creado_en = '2030-06-10T18:03:15Z' AND comentario_id = 'PRUEBA-CRUD-001';
UPDATE comentarios_por_usuario SET contenido = 'Comentario editado', estado = 'visible', likes = 3
WHERE usuario_id = 'USR-PRUEBA' AND dia = '2030-06-10' AND creado_en = '2030-06-10T18:03:15Z' AND comentario_id = 'PRUEBA-CRUD-001';
APPLY BATCH;
SELECT comentario_id, contenido, estado, likes FROM comentarios_por_partido
WHERE partido_id = 'PAR-001' AND minuto = '2030-06-10T18:03:00Z' AND segmento = 0 AND creado_en = '2030-06-10T18:03:15Z' AND comentario_id = 'PRUEBA-CRUD-001';
SELECT comentario_id, contenido, estado, likes FROM comentarios_por_usuario
WHERE usuario_id = 'USR-PRUEBA' AND dia = '2030-06-10' AND creado_en = '2030-06-10T18:03:15Z' AND comentario_id = 'PRUEBA-CRUD-001';

-- Borrado exclusivo de PRUEBA-CRUD-001. No afecta la muestra.
BEGIN BATCH
DELETE FROM comentarios_por_partido
WHERE partido_id = 'PAR-001' AND minuto = '2030-06-10T18:03:00Z' AND segmento = 0 AND creado_en = '2030-06-10T18:03:15Z' AND comentario_id = 'PRUEBA-CRUD-001';
DELETE FROM comentarios_por_usuario
WHERE usuario_id = 'USR-PRUEBA' AND dia = '2030-06-10' AND creado_en = '2030-06-10T18:03:15Z' AND comentario_id = 'PRUEBA-CRUD-001';
APPLY BATCH;

-- Ambas consultas deben devolver cero filas.
SELECT comentario_id FROM comentarios_por_partido
WHERE partido_id = 'PAR-001' AND minuto = '2030-06-10T18:03:00Z' AND segmento = 0 AND creado_en = '2030-06-10T18:03:15Z' AND comentario_id = 'PRUEBA-CRUD-001';
SELECT comentario_id FROM comentarios_por_usuario
WHERE usuario_id = 'USR-PRUEBA' AND dia = '2030-06-10' AND creado_en = '2030-06-10T18:03:15Z' AND comentario_id = 'PRUEBA-CRUD-001';
