-- Keyspace del módulo de comentarios.
CREATE KEYSPACE IF NOT EXISTS fixture2030_comentarios
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE fixture2030_comentarios;

-- Principal para Q1 y Q2. Minuto UTC truncado y segmento entre 0 y 3.
CREATE TABLE IF NOT EXISTS comentarios_por_partido (
    partido_id text,
    minuto timestamp,
    segmento tinyint,
    creado_en timestamp,
    comentario_id text,
    usuario_id text,
    dia date,
    contenido text,
    estado text,
    likes int,
    PRIMARY KEY ((partido_id, minuto, segmento), creado_en, comentario_id)
) WITH CLUSTERING ORDER BY (creado_en DESC, comentario_id ASC);

-- Estructura secundaria para Q3. Conserva las claves de la principal.
CREATE TABLE IF NOT EXISTS comentarios_por_usuario (
    usuario_id text,
    dia date,
    creado_en timestamp,
    comentario_id text,
    partido_id text,
    minuto timestamp,
    segmento tinyint,
    contenido text,
    estado text,
    likes int,
    PRIMARY KEY ((usuario_id, dia), creado_en, comentario_id)
) WITH CLUSTERING ORDER BY (creado_en DESC, comentario_id ASC);
