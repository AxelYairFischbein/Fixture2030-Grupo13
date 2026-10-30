# Data Mart y alternativa relacional

## Pregunta analítica

¿Qué partidos concentran más comentarios visibles por minuto y cómo cambia esa actividad según la fase del torneo?

La propuesta separa el recorrido operacional de páginas, que entrega comentarios individuales, de una proyección para comparar actividad. Es conceptual. No hay otro motor, ETL ni tablero ejecutándose.

## Fuentes, grano y correspondencias

| Atributo | Procedencia | Transformación y uso |
| --- | --- | --- |
| `partido_id` | Cassandra `comentarios_por_partido.partido_id` y Neo4j `Partido.partidoId` | Correspondencia exacta del identificador, por ejemplo `PAR-001`. Clave natural de la dimensión partido |
| `minuto_utc` | Cassandra `creado_en` | Convertir a UTC y truncar al minuto. El bucket `minuto` se contrasta con esa derivación |
| `comentario_id` | Cassandra `comentario_id` | Identidad para deduplicar antes de agregar. No se incorporan filas de `comentarios_por_usuario`, que representan los mismos comentarios |
| `usuario_id` | Cassandra `usuario_id` | Contar participantes distintos dentro del grupo. No se copia el texto de los comentarios al Data Mart |
| `estado` | Cassandra `estado` | Conservar la categoría para distinguir visibles de otros estados, sin convertir faltantes en visibles |
| `fase`, `grupo`, `inicio` | Neo4j `Partido` | Atributos de la dimensión partido. Mantener el último valor extraído y la fecha de extracción |
| `estadio_id` | Relación Neo4j `Partido-[:SE_JUEGA_EN]->Estadio.estadioId` | Atributo descriptivo del partido, sin multiplicar las filas del hecho por estadio |

El hecho `actividad_comentarios` tiene **una fila por partido, minuto UTC y estado**. La clave única es esa terna. Las dimensiones son partido, tiempo y estado. El tiempo permite derivar fecha y hora sin confundir zonas horarias. Cada lote conserva identificador, instante de extracción por fuente, versión de la transformación y rango cubierto.

Las medidas son `cantidad_comentarios` y `usuarios_distintos`. La cantidad se puede sumar entre minutos o partidos después de deduplicar. Los usuarios distintos no se suman entre minutos porque una misma persona puede participar varias veces. Para obtener usuarios únicos de un período mayor se necesita recalcular sobre identidades, no sumar el resumen. La vista solicitada filtra `estado = 'visible'` y compara cantidad por minuto y fase.

## Extracción, actualización y calidad

Se propone un lote cada minuto, con retraso aceptable de hasta dos minutos. Extrae las particiones de los partidos conocidos y los últimos diez minutos, normaliza tipos e identificadores y reemplaza los agregados de esas ventanas. No recorre todo el histórico para cada request de la API.

Una tabla de preparación deduplica por la identidad completa de Cassandra `(partido_id, minuto, segmento, creado_en, comentario_id)`. También detecta un mismo `comentario_id` bajo claves contradictorias, que se registra como inconsistencia y no se cuenta dos veces. El segmento es una distribución física, no una dimensión analítica. Una clave de partido que no se pueda resolver se conserva como dimensión desconocida, con indicador de dato pendiente, en vez de descartar sus comentarios.

Los datos tardíos de hasta diez minutos entran en la siguiente extracción solapada. Se propone revisar las últimas 24 horas una vez al día para incorporar llegadas o cambios de estado anteriores. El esquema operacional no tiene una marca de modificación, por lo que un checkpoint basado solamente en `creado_en` no detecta todas las correcciones. Cambios más antiguos requieren un reproceso explícito del período. No se promete actualización inmediata de esas correcciones.

Si falla Cassandra, no se avanza el checkpoint ni se publica un lote parcial. Si falla Neo4j, se conserva la dimensión conocida con su antigüedad informada o se marca desconocida. Los agregados se publican juntos después de validarlos. Repetir un lote reemplaza las mismas claves del hecho. No suma otra vez sobre un agregado anterior.

La validación exige que la suma de cantidades del lote coincida con los comentarios únicos válidos de la fuente, que `usuarios_distintos <= cantidad_comentarios` y que ninguna clave del hecho se repita. Se registran extraídos, duplicados, inconsistentes, aceptados y publicados. Una lectura sin filas no se transforma automáticamente en cero si la extracción falló. Un cero válido requiere una ventana consultada satisfactoriamente.

La fuente operacional conserva detalle y atiende ventanas pequeñas con cursores. El Data Mart permite agrupar por fase y períodos mayores, pero incorpora retraso y pierde texto, identidad individual y orden de los comentarios al agregar. La carga local del Hito 12 solo mide el camino operacional. Los tiempos del Data Mart no fueron medidos.

## Alternativa relacional concreta

Una implementación conceptual en PostgreSQL puede usar `partido(partido_id PK, fase, grupo, inicio, estadio_id)`, `usuario(usuario_id PK)` y `comentario`. El estadio se relaciona con el catálogo correspondiente. Las claves foráneas impiden comentarios para usuarios o partidos inexistentes dentro de la misma base.

```sql
CREATE TABLE comentario (
    partido_id varchar(7) NOT NULL REFERENCES partido(partido_id),
    comentario_id varchar(64) NOT NULL,
    usuario_id varchar(9) NOT NULL REFERENCES usuario(usuario_id),
    creado_en timestamptz NOT NULL,
    contenido text NOT NULL,
    estado text NOT NULL,
    likes integer NOT NULL CHECK (likes >= 0),
    PRIMARY KEY (partido_id, comentario_id)
);
CREATE INDEX comentario_ventana
ON comentario (partido_id, creado_en DESC, comentario_id ASC);
```

La continuación de una página mantiene el mismo orden mixto del endpoint. Los parámetros se enlazan mediante el driver, sin concatenar valores:

```sql
SELECT creado_en, comentario_id, usuario_id, contenido, estado, likes
FROM comentario
WHERE partido_id = :partido
  AND creado_en >= :desde AND creado_en < :hasta
  AND (creado_en < :cursor_fecha
       OR (creado_en = :cursor_fecha AND comentario_id > :cursor_id))
ORDER BY creado_en DESC, comentario_id ASC
LIMIT :limite;
```

La primera página omite el predicado del cursor. Una transacción puede actualizar el comentario y sus relaciones de forma atómica. Para una lectura estable entre varias páginas bajo escrituras concurrentes habría que definir un snapshot o una política de consistencia. Ni una sucesión de requests independientes ni este ensayo de solo lectura prueban por sí solos esa garantía.

| Aspecto | Cassandra utilizada | Alternativa relacional |
| --- | --- | --- |
| Acceso | Clave compuesta por partido, minuto y segmento, consultas preparadas y orden temporal | Índice por partido y orden del cursor, sin segmentos manuales |
| Integridad referencial | El motor no comprueba claves foráneas entre partido, usuario y comentario | Restricciones y transacciones dentro del motor |
| Analítica | Proyección separada para evitar consultas que no sigan las particiones | SQL y joins facilitan reportes, con costo que debe medirse |
| Distribución | El modelo permite distribuir particiones, pero este ensayo usa un solo nodo y consistencia ONE | El índice y una instancia pueden ser suficientes para un volumen moderado. Distribuir también requiere diseño |
| Trade-off | Duplicación de representaciones, consultas específicas y coordinación de ventanas | Costo de índices, restricciones y competencia entre transacciones y reportes |

La alternativa relacional conviene cuando importan las relaciones verificadas y consultas variadas con un volumen manejable. Cassandra resulta pertinente para patrones conocidos por partición y un crecimiento que justifique distribuirlos. Esta prueba no demuestra una superioridad universal ni asigna tiempos a PostgreSQL, que no se instaló ni se midió.
