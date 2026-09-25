USE fixture2030_comentarios;
CONSISTENCY ONE;

-- Doce comentarios estables y dos filas por comentario.
-- Cada batch contiene solamente las dos representaciones de un comentario.

-- MUESTRA-001, segmento 2.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:00:00Z', 2, '2030-06-10T18:00:20Z', 'MUESTRA-001', 'USR-00001', '2030-06-10', 'Buen comienzo', 'visible', 2);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:00:00Z', 2, '2030-06-10T18:00:20Z', 'MUESTRA-001', 'USR-00001', '2030-06-10', 'Buen comienzo', 'visible', 2);
APPLY BATCH;

-- MUESTRA-002, segmento 0.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:00:00Z', 0, '2030-06-10T18:00:30Z', 'MUESTRA-002', 'USR-00002', '2030-06-10', 'Revisar esta jugada', 'pendiente', 0);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:00:00Z', 0, '2030-06-10T18:00:30Z', 'MUESTRA-002', 'USR-00002', '2030-06-10', 'Revisar esta jugada', 'pendiente', 0);
APPLY BATCH;

-- MUESTRA-003, segmento 2.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:00:00Z', 2, '2030-06-10T18:00:55Z', 'MUESTRA-003', 'USR-00001', '2030-06-10', 'Gran pase al area', 'visible', 4);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:00:00Z', 2, '2030-06-10T18:00:55Z', 'MUESTRA-003', 'USR-00001', '2030-06-10', 'Gran pase al area', 'visible', 4);
APPLY BATCH;

-- MUESTRA-004, segmento 1.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:01:00Z', 1, '2030-06-10T18:01:05Z', 'MUESTRA-004', 'USR-00003', '2030-06-10', 'Mensaje oculto de muestra', 'oculto', 0);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:01:00Z', 1, '2030-06-10T18:01:05Z', 'MUESTRA-004', 'USR-00003', '2030-06-10', 'Mensaje oculto de muestra', 'oculto', 0);
APPLY BATCH;

-- MUESTRA-005, segmento 3.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:01:00Z', 3, '2030-06-10T18:01:20Z', 'MUESTRA-005', 'USR-00001', '2030-06-10', 'Buen remate', 'visible', 5);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:01:00Z', 3, '2030-06-10T18:01:20Z', 'MUESTRA-005', 'USR-00001', '2030-06-10', 'Buen remate', 'visible', 5);
APPLY BATCH;

-- MUESTRA-006, segmento 1.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:01:00Z', 1, '2030-06-10T18:01:20Z', 'MUESTRA-006', 'USR-00002', '2030-06-10', 'Atajada importante', 'visible', 3);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:01:00Z', 1, '2030-06-10T18:01:20Z', 'MUESTRA-006', 'USR-00002', '2030-06-10', 'Atajada importante', 'visible', 3);
APPLY BATCH;

-- MUESTRA-007, segmento 3.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:01:00Z', 3, '2030-06-10T18:01:45Z', 'MUESTRA-007', 'USR-00003', '2030-06-10', 'Comentario en revision', 'pendiente', 0);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:01:00Z', 3, '2030-06-10T18:01:45Z', 'MUESTRA-007', 'USR-00003', '2030-06-10', 'Comentario en revision', 'pendiente', 0);
APPLY BATCH;

-- MUESTRA-008, segmento 2.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:01:00Z', 2, '2030-06-10T18:01:59Z', 'MUESTRA-008', 'USR-00001', '2030-06-10', 'Se termina este minuto', 'visible', 1);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:01:00Z', 2, '2030-06-10T18:01:59Z', 'MUESTRA-008', 'USR-00001', '2030-06-10', 'Se termina este minuto', 'visible', 1);
APPLY BATCH;

-- MUESTRA-009, segmento 0.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:02:00Z', 0, '2030-06-10T18:02:05Z', 'MUESTRA-009', 'USR-00002', '2030-06-10', 'Sigue el partido', 'visible', 1);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:02:00Z', 0, '2030-06-10T18:02:05Z', 'MUESTRA-009', 'USR-00002', '2030-06-10', 'Sigue el partido', 'visible', 1);
APPLY BATCH;

-- MUESTRA-010, segmento 1.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:02:00Z', 1, '2030-06-10T18:02:10Z', 'MUESTRA-010', 'USR-00001', '2030-06-10', 'Fuera del limite superior de Q2', 'visible', 0);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-001', '2030-06-10T18:02:00Z', 1, '2030-06-10T18:02:10Z', 'MUESTRA-010', 'USR-00001', '2030-06-10', 'Fuera del limite superior de Q2', 'visible', 0);
APPLY BATCH;

-- MUESTRA-011, segmento 3.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-002', '2030-06-10T18:01:00Z', 3, '2030-06-10T18:01:10Z', 'MUESTRA-011', 'USR-00001', '2030-06-10', 'Comentario en otro partido', 'visible', 2);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-002', '2030-06-10T18:01:00Z', 3, '2030-06-10T18:01:10Z', 'MUESTRA-011', 'USR-00001', '2030-06-10', 'Comentario en otro partido', 'visible', 2);
APPLY BATCH;

-- MUESTRA-012, segmento 1.
BEGIN BATCH
INSERT INTO comentarios_por_partido (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-009', '2030-06-11T18:01:00Z', 1, '2030-06-11T18:01:10Z', 'MUESTRA-012', 'USR-00003', '2030-06-11', 'Mensaje del dia siguiente', 'oculto', 0);
INSERT INTO comentarios_por_usuario (partido_id, minuto, segmento, creado_en, comentario_id, usuario_id, dia, contenido, estado, likes)
VALUES ('PAR-009', '2030-06-11T18:01:00Z', 1, '2030-06-11T18:01:10Z', 'MUESTRA-012', 'USR-00003', '2030-06-11', 'Mensaje del dia siguiente', 'oculto', 0);
APPLY BATCH;
