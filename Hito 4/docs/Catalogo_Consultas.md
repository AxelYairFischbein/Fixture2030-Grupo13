# Catálogo de operaciones y consultas

Este catálogo documenta las operaciones ejecutables de `04_demo_crud.js` y `05_queries.js`. Los datos temporales usan los identificadores reservados `EQ-900` y `JUG-9000`, se eliminan al finalizar y no alteran el conjunto canónico.

## Operaciones CRUD controladas

| ID | Objetivo funcional | Colección | Filtro o condiciones | Campos devueltos | Índice relacionado | Resultado esperado |
|---|---|---|---|---|---|---|
| OP01 | Insertar un equipo de demostración válido. | `equipos` | Documento completo con `equipoId: EQ-900`. Rechazo si el identificador ya existe. | `acknowledged`, `insertedId`. | `uq_equipos_equipoId`, `uq_equipos_codigo`. | Un equipo temporal insertado. |
| OP02 | Insertar un jugador relacionado. | `jugadores` | Se comprueba previamente que existe `EQ-900`. Se inserta `JUG-9000`. | `acknowledged`, `insertedId`. | `uq_jugadores_jugadorId`, `uq_jugadores_equipo_camiseta`. | Un jugador temporal con referencia válida. |
| OP03 | Actualizar el estado del equipo. | `equipos` | `{ equipoId: "EQ-900" }`. | `matchedCount`, `modifiedCount`. | `uq_equipos_equipoId`. | Estado `CONFIRMADO`. Un documento coincidente y modificado. |
| OP04 | Actualizar el estado del plantel. | `jugadores` | `{ jugadorId: "JUG-9000" }`. No cambia `equipoId`. | `matchedCount`, `modifiedCount`. | `uq_jugadores_jugadorId`. | Estado RESERVA. Un documento coincidente y modificado. |
| OP05 | Comprobar actualizaciones y vínculo. | `jugadores` + `equipos` | `$match` por `JUG-9000`, `$lookup` por `equipoId`. | Identidad del jugador, estado del plantel, equipo y estado. | Ambos índices únicos de identificador. | Un resultado con jugador y equipo temporal actualizado. |
| OP06 | Eliminar el jugador temporal. | `jugadores` | `{ jugadorId: "JUG-9000", origen: "demostracion-controlada" }`. | `deletedCount`. | `uq_jugadores_jugadorId`. | Un jugador eliminado. |
| OP07 | Eliminar el equipo temporal después del jugador. | `equipos` | `{ equipoId: "EQ-900", origen: "demostracion-controlada" }`. | `deletedCount`. | `uq_equipos_equipoId`. | Un equipo eliminado. Recuentos 64/1.536 restaurados. |

El orden de eliminación evita crear una ventana con un jugador huérfano. Un bloque `finally` ejecuta la limpieza aun si falla una comprobación intermedia.

## Consultas funcionales

| ID | Objetivo funcional | Colección | Filtro o condiciones | Campos devueltos | Índice relacionado | Resultado esperado |
|---|---|---|---|---|---|---|
| Q01 | Recuperar equipo por identificador. | `equipos` | `{ equipoId: "EQ-013" }`. | `equipoId`, código, nombre, confederación, ranking. | `uq_equipos_equipoId`. | Un equipo. |
| Q02 | Recuperar jugador por identificador. | `jugadores` | `{ jugadorId: "JUG-0313" }`. | Identidad, equipo, posición y camiseta. | `uq_jugadores_jugadorId`. | Un jugador. |
| Q03 | Filtrar y ordenar equipos de CONMEBOL. | `equipos` | Confederación exacta y ranking `<= 50`. Orden ranking/equipo ascendente. | Identificador, nombre y ranking. | `idx_equipos_confederacion_ranking`. | Ocho equipos en la carga actual. |
| Q04 | Buscar delanteros por altura. | `jugadores` | Posición exacta y altura `>= 180` cm. Orden descendente y límite 10. | Identidad, equipo, apellido, altura y pie hábil. | `idx_jugadores_posicion_altura`. | Los primeros diez delanteros según el orden. |
| Q05 | Proyectar fichas resumidas. | `equipos` | `{ esDatoSintetico: true }`. Orden por identificador y límite 5. | Código, nombre y confederación. Excluye `_id`. | Sin índice adicional: 64 documentos y baja selectividad. | Cinco fichas resumidas. |
| Q06 | Paginar un plantel. | `jugadores` | `{ equipoId: "EQ-001" }`. Orden apellido/nombre/id, `skip(5)`, `limit(5)`. | Identidad, nombre, posición y camiseta. | `idx_jugadores_equipo_nombre`. | Página 2 de cinco jugadores. |
| Q07 | Recuperar todos los jugadores de un equipo. | `jugadores` | `{ equipoId: "EQ-002" }`. Orden estable por nombre. | Identidad, nombre, posición y camiseta. | `idx_jugadores_equipo_nombre`. | Exactamente 24 jugadores. |
| Q08 | Resumir plantel por posición. | `jugadores` | `$match` por `EQ-001`. `$group` por posición. | Posición, cantidad y promedio de altura en centímetros. | Prefijo `equipoId` de `idx_jugadores_equipo_nombre`. | Cuatro grupos. Cantidades 3/8/8/5. |
| Q09 | Consolidar equipo y plantel. | `equipos` + `jugadores` | AFC, ranking ascendente, límite 5 y `$lookup`. | Equipo, cantidad de jugadores y promedio de altura. | Índices de confederación/ranking y equipo de jugador. | Cinco equipos, cada uno con 24 jugadores. |
| Q10 | Detectar jugadores huérfanos. | `jugadores` + `equipos` | `$lookup` y arreglo de equipo vacío. | `jugadorId`, `equipoId`. | Índice por equipo en jugadores y único de equipo. | Arreglo vacío. |
| Q11 | Detectar planteles distintos de 24. | `equipos` + `jugadores` | `$lookup`, tamaño de plantel `!= 24`. | `equipoId`, cantidad. | Índices por `equipoId` en ambas colecciones. | Arreglo vacío. |
| Q12 | Contar equipos y jugadores por confederación. | `equipos` + `jugadores` | `$lookup`, `$group` por confederación y `$sort`. | Confederación, equipos y jugadores. | Índices de confederación y referencia de equipo. | Seis filas. Suma 64 equipos y 1.536 jugadores. |

## Consulta de rendimiento

| ID | Objetivo funcional | Colección | Filtro o condiciones | Campos devueltos | Índice relacionado | Resultado esperado |
|---|---|---|---|---|---|---|
| P01 | Medir el filtro por nacionalidad y altura antes y después de indexar. | `jugadores` | `nacionalidadCodigo: F01`, altura `>= 180`. Orden altura descendente e id ascendente. | `jugadorId`, apellido, altura. | `idx_jugadores_nacionalidad_altura`. | Los mismos 15 documentos. Antes `COLLSCAN`, después `IXSCAN`. |

El orden del índice P01 es igualdad (`nacionalidadCodigo`), rango/orden (`alturaCm`) y desempate estable (`jugadorId`). La comparación elimina y recrea sólo este índice no esencial. El resultado observado se conserva en `evidencias/11_comparacion_rendimiento_indice.txt`.
