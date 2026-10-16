# Casos de uso y mapa de endpoints

Los casos se definieron antes que las rutas. Cada uno corresponde a un patrón de acceso ya diseñado en su hito; ninguna ruta acepta nombres de base, colecciones, Cypher, CQL, SQL ni comandos del consumidor.

**Consumidores**: la consola web del Fixture (aficionados y operadores de sala de prensa), herramientas de prueba (Swagger UI, Postman, cURL) y, a futuro, otros servicios internos.

## Casos de uso

| ID | Consumidor y necesidad | Fuente(s) | Entrada | Respuesta | Si no existe | Si la fuente cae | Tipo | Éxito |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CU1 | Aficionado explora selecciones por confederación | MongoDB | `confederacion?`, `pagina`, `tamanio ≤ 50` | Resumen de equipos + total | Lista vacía con total 0 (filtro válido) | 503 `mongodb` | Lectura | 200 con página ordenada por ranking |
| CU2 | Aficionado abre la ficha de un equipo | Redis → MongoDB | `equipoId` `EQ-NNN` | Ficha proyectada + `cache` | 404 | Redis caído: se lee MongoDB (`BYPASS`). MongoDB caído: 503 | Lectura (escribe caché) | 200 con los mismos datos en `MISS` y `HIT` |
| CU3 | Operador invalida la ficha tras una corrección | Redis | `equipoId` | Sin cuerpo | 204 igual (idempotente) | 503 `redis` | Invalidación | 204 y la próxima lectura es `MISS` |
| CU4 | Aficionado consulta el plantel | MongoDB | `equipoId`, `posicion?`, página | Jugadores por camiseta + total | 404 si el equipo no existe | 503 | Lectura | 200 |
| CU5 | Aficionado ve la agenda de su selección | Neo4j | `equipoId`, `limite ≤ 20` | Partidos con rol, rival y estadio | 404 si el equipo no está en el grafo | 503 `neo4j` | Lectura | 200 |
| CU6 | Prensa consulta un partido y sus incidencias | Neo4j | `partidoId` `PAR-NNN`, `limiteEventos ≤ 50` | Partido, estadio, equipos, eventos con involucrados | 404; sin eventos → `eventos: []` | 503 | Lectura | 200 |
| CU7 | Aficionado lee comentarios de un tramo del partido | Cassandra | `partidoId`, `desde`, `hasta` (≤ 5 min), `limite ≤ 50`, `cursor?` | Comentarios en orden descendente + `siguienteCursor` | Ventana sin filas → `items: []` | 503 `cassandra` | Lectura | 200 con ≤ 24 particiones |
| CU8 | Aficionado publica un comentario | Redis + Neo4j + Cassandra | `partidoId`, `Idempotency-Key`, `{usuarioId, contenido ≤ 280}` | Comentario creado con su partición | 404 si el partido no existe | 503 (nada queda a medias, ver idempotencia) | Creación | 201; repetición 200 sin nueva fila |
| CU9 | Consola abre una sesión de usuario | Redis | `{usuarioId, rol}` | `sesionId`, estado, TTL | — | 503 | Creación | 201 |
| CU10 | Consola valida una sesión | Redis | `sesionId` `SES-` + 24 hex | Datos públicos de la sesión y TTL restante | 404 `SESION_NO_VIGENTE` (inexistente, cerrada o vencida) | 503 (distinto de ausencia) | Lectura (no renueva) | 200 |
| CU11 | Usuario cierra sesión | Redis | `sesionId` | Sin cuerpo | 204 igual | 503 | Invalidación | 204 y la consulta posterior es 404 |
| CU12 | Analista ve la evolución estadística de un partido | InfluxDB | `partidoId`, `equipoId?`, `desde`/`hasta` (juntos u omitidos), `intervalo` ∈ 10s/30s/1m/5m | Puntos agregados por intervalo y equipo | Sin puntos → `puntos: []` | 503 `influxdb` | Lectura | 200 con ≤ 720 intervalos por equipo |
| CU13 | Árbitro u operador consulta el acta oficial | IRIS | `codigo` | Partido, árbitro y eventos con IDs IRIS | 404 | 503 `iris` | Lectura | 200 |
| CU14 | Operador avanza el estado del partido | IRIS | `codigo`, `{estado}` | `cambio` + acta actualizada | 404 | 503 | Actualización | 200; transición prohibida → 409 sin cambios |
| CU15 | Operador verifica la plataforma | Las seis | — | Estado y latencia de cada fuente | — | 503 con el detalle por fuente | Lectura | 200 solo si las seis responden |

## Mapa de endpoints

Prefijo común `/api/v1`.

| Método | Ruta | Fuente | Operación en la fuente | CU |
| --- | --- | --- | --- | --- |
| GET | `/salud` | Todas | `ping` de cada adaptador | 15 |
| GET | `/equipos` | MongoDB | `find` con proyección, `sort` por `rankingReferencia, equipoId`, `skip/limit` (índice `idx_equipos_confederacion_ranking`) + `count_documents` | 1 |
| GET | `/equipos/{equipoId}` | Redis, MongoDB | `GET cache:equipo:{id}`; si falta, `find_one` por `equipoId` (índice único) y `SET EX 300` | 2 |
| DELETE | `/equipos/{equipoId}/cache` | Redis | `DEL cache:equipo:{id}` | 3 |
| GET | `/equipos/{equipoId}/jugadores` | MongoDB | `count_documents` del equipo; `find` por `equipoId` (+ `posicion`) ordenado por camiseta (índice `uq_jugadores_equipo_camiseta`) | 4 |
| GET | `/equipos/{equipoId}/partidos` | Neo4j | `(Equipo)-[:DISPUTA]->(Partido)-[:SE_JUEGA_EN]->(Estadio)` + rival, `[..$limite]` | 5 |
| GET | `/partidos/{partidoId}` | Neo4j | `MATCH (p:Partido {partidoId:$id})` + estadio + equipos; eventos con `INVOLUCRA`, `LIMIT $limite` | 6 |
| GET | `/partidos/{partidoId}/comentarios` | Cassandra | `comentarios_por_partido` con `minuto IN ? AND segmento IN (0..3)`, rango de `creado_en`, `ORDER BY`, `LIMIT` | 7 |
| POST | `/partidos/{partidoId}/comentarios` | Redis, Neo4j, Cassandra | `SET NX` de la clave de idempotencia; existencia del partido; `BATCH LOGGED` en las dos tablas | 8 |
| POST | `/sesiones` | Redis | Script Lua `HSET` + `EXPIRE` atómico (igual al Hito 7) | 9 |
| GET | `/sesiones/{sesionId}` | Redis | `HGETALL` + `TTL` en una transacción | 10 |
| DELETE | `/sesiones/{sesionId}` | Redis | `DEL` | 11 |
| GET | `/partidos/{partidoId}/estadisticas` | InfluxDB | SQL parametrizado con `DATE_BIN`, filtro por `partido_id`, `equipo_id` y tiempo; `MAX(time)` acotado a 7 días si no hay ventana | 12 |
| GET | `/actas/{codigo}` | IRIS | SQL sobre la proyección de `FixtureH9.Partido` y `FixtureH9.Evento` (`WHERE Partido = ?`) | 13 |
| PUT | `/actas/{codigo}/estado` | IRIS | API nativa: `PorCodigoOpen` + método de instancia `CambiarEstado()` | 14 |

## Por qué cada fuente

- **MongoDB** guarda el documento canónico de equipos y jugadores; las lecturas usan los índices definidos en el Hito 4.
- **Redis** responde lecturas repetidas de la ficha (cache-aside con TTL), administra sesiones con vencimiento nativo y guarda claves de idempotencia con `SET NX`, que es atómico.
- **Neo4j** resuelve relaciones (partido–equipos–estadio–eventos–jugadores) con un recorrido acotado desde un nodo identificado, sin joins.
- **Cassandra** atiende el volumen de comentarios: una ventana de tiempo se traduce en un conjunto conocido y pequeño de particiones.
- **InfluxDB** agrega series por intervalo dentro de una ventana, sin traer todos los puntos.
- **IRIS** mantiene el acta como objeto con hijos dependientes y aplica la regla de transición en el propio modelo.

La escritura de comentarios es la única integración de varias fuentes en una request: Redis asegura que un reintento no duplique, Neo4j evita comentarios huérfanos y Cassandra guarda el dato. La ficha de equipo combina Redis y MongoDB por rendimiento, con degradación documentada.
