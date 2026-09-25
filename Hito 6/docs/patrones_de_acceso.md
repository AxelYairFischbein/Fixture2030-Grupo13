# Patrones de acceso

## Problema de volumen

El módulo guarda mensajes breves de los partidos del Fixture 2030. Las tablas se diseñan a partir de las consultas que deben resolver. Las cifras siguientes son estimaciones para dimensionar el modelo, no resultados medidos.

Se proyectan 10 millones de comentarios durante el torneo y hasta 1 millón en un encuentro popular. En el pico se suponen 100.000 lectores conectados y 20.000 autores activos. Si cada autor envía un mensaje cada 10 segundos, ingresan 2.000 comentarios por segundo. Se considera también un pico extraordinario de 10.000 comentarios por segundo durante un minuto. No se supone que ese pico dure todo el partido.

Se estiman hasta 280 caracteres y 500 bytes por copia de cada comentario, incluyendo las claves. El tamaño real depende del texto, la compresión y el almacenamiento. Para el torneo siguiente se considera el doble de volumen.

## Preguntas prioritarias

Todas las fechas se interpretan en UTC. Las consultas incluyen los estados `visible`, `pendiente` y `oculto` para revisar los datos. No corresponden a una pantalla pública que deba excluir los comentarios ocultos.

| Patrón | Pregunta y parámetros | Orden y límite | Frecuencia estimada en pico |
|---|---|---|---|
| Q1 | ¿Cuáles son los comentarios recientes de un partido en el minuto indicado? `partido_id`, `minuto` y los cuatro segmentos conocidos | `creado_en DESC, comentario_id ASC`, hasta 20 | Una actualización cada 10 s por lector, hasta 10.000 lecturas/s |
| Q2 | ¿Qué comentarios llegaron a un partido entre `desde` incluido y `hasta` excluido? Intervalo de hasta 5 minutos y lista de minutos que lo intersectan | Mismo orden, hasta 50 en todo el intervalo | Hasta 100 lecturas/s de revisión |
| Q3 | ¿Qué publicó un usuario en un día UTC? `usuario_id`, `dia` | Mismo orden, hasta 20 | Hasta 200 lecturas/s de historial |

Q1 busca solo en el minuto indicado y devuelve vacío si no encuentra mensajes. Q2 permite revisar una ventana mayor. Q3 consulta un día del historial sin recorrer los datos de otros usuarios.

## Escrituras previstas

| Operación | Datos de entrada | Frecuencia estimada |
|---|---|---|
| Alta | Identificador estable, partido, autor, fecha UTC, contenido, estado y likes | 2.000 comentarios/s en el pico de diseño |
| Edición o moderación | Claves completas de las dos representaciones y nuevos valores | Hasta 100 comentarios/s |
| Borrado puntual | Claves completas de un comentario identificado | Hasta 10 comentarios/s |

Cada operación sobre un comentario afecta dos filas. Los likes guardan una cantidad no negativa que se reemplaza al editar. Se supone un único proceso actualizando ese valor por comentario. No se implementan incrementos concurrentes ni búsquedas globales por estado o contenido.

## Recuperación de varias particiones

Cada minuto tiene cuatro segmentos, numerados de 0 a 3. Q1 consulta los cuatro con `IN`. Q2 enumera los minutos UTC que intersectan `[desde, hasta)` y los cuatro segmentos. Una ventana de cinco minutos toca como máximo seis minutos y 24 particiones. Los límites son globales al SELECT, no cuatro resultados independientes de 20 filas.

En `consultas.cql`, `ORDER BY` ordena el conjunto por fecha e identificador antes de aplicar `LIMIT`. Al combinar `IN` sobre particiones con `ORDER BY`, cqlsh requiere `PAGING OFF`. Por eso se desactiva la paginación para estas respuestas pequeñas. El orden de clustering solo ordena cada partición, no el resultado combinado. No se utiliza `ALLOW FILTERING`.

## Coherencia con el TPO

Se conservan los identificadores `PAR-001` a `PAR-064` y el calendario sintético del Hito 5, desde el 10 de junio de 2030, con ocho partidos por día a las 18:00 UTC. Los Hitos 4 y 5 mantienen equipos, jugadores y relaciones deportivas. Aquí solo se referencia el partido mediante su identificador y se introduce un autor sintético `USR-...`. No se duplican planteles ni se ejecutan recorridos de grafos.

Cassandra no verifica claves foráneas contra los otros módulos, por lo que quien carga los comentarios debe usar identificadores válidos. Este módulo funciona sin iniciar MongoDB ni Neo4j. El volumen de comentarios es una estimación propia y no proviene de mediciones de los hitos anteriores.
