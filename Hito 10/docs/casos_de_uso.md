# Hito 10 · Casos de uso y recursos de la API integrada

Grupo 13 · Ingeniería de Datos II · Fixture Mundial 2030

Este documento cumple el punto 5.1 del Hito 10: identifica los casos de uso **antes** de definir rutas y métodos definitivos. Cada caso de uso parte de un patrón de acceso que ya fue modelado, cargado y probado en los Hitos 4 a 9 del repositorio. No se agregan consultas que esos módulos no resuelvan con sus claves, índices o recorridos.

## 1. Criterios de diseño

1. **Un caso de uso, una operación concreta.** No existe un endpoint genérico que reciba base, colección o consulta. Las rutas representan recursos del Fixture (equipos, jugadores, partidos, comentarios, sesiones, estadísticas, actas).
2. **Cada consulta usa el patrón de acceso diseñado para su fuente.** Se cita la consulta del hito de origen (por ejemplo, Hito 4 Q06 o Hito 6 Q1).
3. **Se combinan fuentes solo cuando el caso de uso lo exige.** Hay tres integraciones justificadas: caché Redis delante de MongoDB (CU-01), sesión Redis antes de escribir en Cassandra (CU-09, CU-10) y sesión Redis con rol antes de modificar IRIS (CU-19, CU-14).
4. **La validación ocurre antes de consultar.** Un identificador con formato incorrecto devuelve 400 sin tocar la base.
5. **Ausencia, vacío válido y dependencia caída son respuestas distintas.** Nunca se devuelve 200 con una lista vacía para ocultar un timeout.
6. **Los identificadores de negocio se conservan entre módulos.** `EQ-001…EQ-064`, `JUG-0001…JUG-1536`, `PAR-001…PAR-064`, `EST-01…EST-08` y `USR-…` son los mismos en todos los hitos. La API nunca expone `_id` de MongoDB, IDs internos de Neo4j ni `%ID` de IRIS.

## 2. Consumidores

| Código | Consumidor | Qué necesita | Autenticación |
|---|---|---|---|
| **APP** | Aplicación web/móvil del aficionado | Fichas, planteles, agenda, comentarios, estadísticas en vivo | Anónimo para lecturas públicas. Sesión para publicar |
| **MOD** | Moderador de comentarios | Revisar ventanas e historiales con todos los estados, y ocultar o publicar comentarios | Sesión con rol `moderador` |
| **OPS** | Operador de partido / backoffice | Acta del partido, transiciones de estado, invalidación de caché | Sesión con rol `operador` |
| **ANA** | Panel analítico de estadísticas | Comparaciones y evolución por minuto | Anónimo o sesión, según despliegue |
| **INT** | Middleware interno de la propia API | Validar la sesión antes de una operación protegida | No es un endpoint público: reutiliza el adaptador Redis |

La sesión se envía en el encabezado `X-Session-Id`, nunca en la ruta ni en la query: así no queda registrada en logs de acceso ni en el historial del navegador (RNF7, RNF10).

## 3. Mapa de recursos

| Recurso | Fuente autoritativa | Hito de origen | Identificador |
|---|---|---|---|
| Equipo (ficha) | MongoDB `fixture2030.equipos` | 4 | `equipoId` `^EQ-\d{3}$` |
| Jugador (ficha) | MongoDB `fixture2030.jugadores` | 4 | `jugadorId` `^JUG-\d{4}$` |
| Ficha de equipo cacheada | Redis (copia, no autoritativa) | 7 | misma `equipoId` |
| Partido (calendario y rivales) | Neo4j `:Partido`, `:Equipo`, `:Estadio` | 5 | `partidoId` `^PAR-\d{3}$` |
| Evento deportivo y participantes | Neo4j `:EventoDeportivo` | 5 | `eventoId` |
| Comentario | Cassandra `fixture2030_comentarios` | 6 | `(partido_id, minuto, segmento, creado_en, comentario_id)` |
| Sesión | Redis hash `sesion:<id>` | 7 | `X-Session-Id` |
| Estadística temporal | InfluxDB `fixture2030_h8.estadisticas_equipo` | 8 | tags `partido_id`, `equipo_id`, `estadio_id` + `time` |
| Acta del partido (estado, árbitro, eventos) | IRIS `FixtureH9.Partido` / `FixtureH9.Evento` | 9 | `Codigo` = `partidoId` |

### 3.1 Decisión: el estado del partido pertenece a IRIS

Neo4j e IRIS guardan partidos, pero con responsabilidades distintas. **IRIS es la única fuente autoritativa del estado del partido.** En Neo4j, `Partido.estado` es solo una propiedad descriptiva del nodo que se cargó con la muestra del Hito 5: la API no la expone, no la usa para decidir nada y no la actualiza.

| Dato del partido | Fuente autoritativa | Casos de uso | Quién puede modificarlo |
|---|---|---|---|
| Estado (`PENDIENTE`, `EN_JUEGO`, `FINALIZADO`) | **IRIS** `FixtureH9.Partido.Estado` | CU-18 (lectura), CU-19 (transición) | Solo CU-19, mediante `CambiarEstado()` |
| Árbitro y eventos del acta (GOL, TARJETA, CAMBIO) | **IRIS** `FixtureH9.Evento` | CU-18 | Fuera del alcance de la API |
| Calendario (`inicio`, `grupo`, `fase`), rivales, rol local o visitante, estadio | **Neo4j** | CU-05, CU-07 | Fuera del alcance de la API |
| Incidencias como relaciones entre jugadores y equipos | **Neo4j** `EventoDeportivo` | CU-06 | Fuera del alcance de la API |

Reglas que se derivan:

1. **Las respuestas de Neo4j no incluyen `estado`.** CU-05 y CU-07 devuelven calendario y relaciones; para saber si un partido está pendiente, en juego o finalizado, el consumidor llama a CU-18. Así nunca aparecen dos valores distintos del mismo dato: hoy la muestra de Neo4j tiene todos los partidos en `FINALIZADO` y el acta de `PAR-001` en IRIS está `PENDIENTE`.
2. **CU-19 escribe solo en IRIS.** No hay sincronización hacia Neo4j, de modo que la transición no es una escritura distribuida entre dos bases ni puede quedar aplicada a medias. La propiedad de Neo4j queda desactualizada y eso es aceptable porque nadie la lee a través de la API.
3. **El identificador común es `partidoId`** (`Partido.partidoId` en Neo4j y `Partido.Codigo` en IRIS). Que un partido exista en Neo4j no implica que tenga acta en IRIS: en ese caso CU-18 devuelve `404 ACTA_NO_ENCONTRADA` y CU-05, CU-06 y CU-07 siguen funcionando.
4. **Eventos de Neo4j y eventos del acta son conceptos distintos** y tienen rutas distintas: `/partidos/{id}/eventos` (incidencias como relaciones del grafo) y `/partidos/{id}/acta` (registro oficial con su máquina de estados).

### 3.2 Decisión: catálogo de partidos en memoria cargado desde Neo4j

Cassandra e InfluxDB guardan `partido_id` como un valor más y no pueden saber si ese partido existe. Para que la API responda `404 PARTIDO_NO_ENCONTRADO` en comentarios y estadísticas, mantiene un **catálogo de partidos en memoria** construido desde Neo4j, que es la fuente del calendario (sección 3.1). MongoDB no guarda partidos (el Hito 4 se limita a equipos y jugadores), así que no puede cumplir esa función.

| Aspecto | Definición |
|---|---|
| Contenido | `partidoId` → `equipos` participantes (los dos `equipoId` de `DISPUTA`). 64 entradas en la muestra. |
| Carga | Al iniciar la API, con un único Cypher parametrizado y con `LIMIT`: `MATCH (e:Equipo)-[:DISPUTA]->(p:Partido) RETURN p.partidoId, collect(e.equipoId)`. |
| Refresco | Cada 10 minutos en segundo plano. Un partido nuevo en Neo4j puede tardar hasta ese plazo en ser aceptado. |
| Neo4j caído al iniciar | La API arranca igual. El catálogo queda `no_cargado` y se reintenta como máximo una vez cada 30 s cuando llega una request que lo necesita. Mientras tanto, esas operaciones responden `503 DEPENDENCIA_NO_DISPONIBLE` (no `200` ni `404`, porque no se puede saber si el partido existe). |
| Neo4j caído después de cargar | Se sigue usando el último catálogo cargado. Comentarios y estadísticas no dependen de que Neo4j esté disponible en cada request. |
| Observabilidad | `GET /api/v1/salud` informa el estado del catálogo (`cargado`, cantidad de partidos, hora de la última carga). |
| Casos de uso que lo usan | CU-08, CU-09, CU-20 (partido) y CU-15, CU-16, CU-17 (partido y, en CU-15, que el equipo participe). |

Se descartaron dos alternativas: consultar Neo4j en cada request (suma latencia al camino más usado, hasta 10.000 lecturas/s de comentarios, y acopla la disponibilidad de comentarios a la de Neo4j) y crear una colección de partidos en MongoDB (duplica el calendario y contradice el alcance del Hito 4).

**Evolución prevista:** el catálogo valida solo que el partido *exista*. Como IRIS es dueña del ciclo de vida del partido, una mejora futura es que IRIS valide además si el partido *admite* comentarios en su estado actual (por ejemplo, rechazar comentarios en un partido `PENDIENTE`). Queda fuera de este hito porque hoy IRIS solo tiene el acta de `PAR-001` y bloquearía los comentarios de los demás partidos.

## 4. Resumen de casos de uso

| CU | Caso de uso | Consumidor | Ruta propuesta | Fuente(s) | Operación |
|---|---|---|---|---|---|
| CU-01 | Ver ficha de un equipo | APP | `GET /api/v1/equipos/{equipoId}` | Redis + MongoDB | Lectura (cache-aside) |
| CU-02 | Listar equipos de una confederación | APP | `GET /api/v1/equipos?confederacion=…` | MongoDB | Lectura paginada |
| CU-03 | Ver plantel de un equipo | APP | `GET /api/v1/equipos/{equipoId}/jugadores` | MongoDB | Lectura paginada |
| CU-04 | Ver ficha de un jugador | APP | `GET /api/v1/jugadores/{jugadorId}` | MongoDB | Lectura |
| CU-05 | Ver agenda y rivales de un equipo | APP | `GET /api/v1/equipos/{equipoId}/partidos` | Neo4j | Lectura (recorrido) |
| CU-06 | Ver eventos y participantes de un partido | APP | `GET /api/v1/partidos/{partidoId}/eventos` | Neo4j | Lectura (recorrido) |
| CU-07 | Ver partidos de un rango de fechas | APP | `GET /api/v1/partidos?desde=…&hasta=…` | Neo4j | Lectura acotada |
| CU-08 | Leer comentarios de un partido | APP, MOD | `GET /api/v1/partidos/{partidoId}/comentarios` | Cassandra | Lectura por partición |
| CU-09 | Publicar un comentario | APP | `POST /api/v1/partidos/{partidoId}/comentarios` | Redis + Cassandra | Creación idempotente |
| CU-10 | Ver historial diario de un autor | MOD, APP (propio) | `GET /api/v1/usuarios/{usuarioId}/comentarios?dia=…` | Redis + Cassandra | Lectura por partición |
| CU-20 | Moderar un comentario | MOD | `PATCH /api/v1/partidos/{partidoId}/comentarios/{comentarioId}` | Redis (sesión) + Cassandra | Actualización validada |
| CU-11 | Consultar la sesión vigente | APP, INT | `GET /api/v1/sesiones/actual` | Redis | Lectura |
| CU-12 | Registrar actividad de la sesión | APP | `POST /api/v1/sesiones/actual/actividad` | Redis | Actualización (renueva TTL) |
| CU-13 | Cerrar la sesión | APP | `DELETE /api/v1/sesiones/actual` | Redis | Invalidación |
| CU-14 | Invalidar la ficha cacheada de un equipo | OPS | `DELETE /api/v1/cache/equipos/{equipoId}` | Redis (+ sesión) | Invalidación |
| CU-15 | Ver estado reciente de un equipo en un partido | APP | `GET /api/v1/partidos/{partidoId}/equipos/{equipoId}/estadisticas/recientes` | InfluxDB | Lectura por ventana |
| CU-16 | Comparar los equipos de un partido | ANA | `GET /api/v1/partidos/{partidoId}/estadisticas/comparacion` | InfluxDB | Lectura agregada |
| CU-17 | Ver evolución por minuto | ANA | `GET /api/v1/partidos/{partidoId}/estadisticas/evolucion` | InfluxDB | Lectura agregada |
| CU-18 | Ver el acta de un partido | APP, OPS | `GET /api/v1/partidos/{partidoId}/acta` | IRIS | Lectura de objeto |
| CU-19 | Cambiar el estado de un partido | OPS | `POST /api/v1/partidos/{partidoId}/acta/transiciones` | Redis (sesión) + IRIS | Actualización validada |

**Alcance acordado: se implementan los 20 casos de uso.** Cobertura del Hito 10: RF3 (CU-01 a CU-04), RF4 (CU-05 a CU-07), RF5 (CU-08 a CU-10 y CU-20), RF6 (CU-11 a CU-14), RF7 (CU-15 a CU-17) y RF8 (CU-18 y CU-19). CU-08, CU-09, CU-15, CU-16, CU-17 y CU-20 validan además el partido contra el catálogo de la sección 3.2.

## 5. Fichas de casos de uso

Cada ficha responde las nueve preguntas del punto 5.1 en el mismo orden. Los códigos de error remiten a la sección 6.

---

### CU-01 · Ver ficha de un equipo

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP, al abrir la pantalla de una selección. Lectura muy repetida (Hito 7: hasta 500 lecturas/s en un pico hipotético). |
| Qué recibe o envía | Recibe un `equipoId`. Envía la ficha pública del equipo. |
| Fuentes | **Redis** como caché (`cache:equipo:<equipoId>`, String JSON, `SET … EX 300`) y **MongoDB** como fuente de verdad (`equipos`, índice `uq_equipos_equipoId`, Hito 4 Q01). |
| Datos de entrada | Path `equipoId`, obligatorio, `^EQ-\d{3}$`. |
| Respuesta esperada | `200` con `equipoId`, `codigo`, `nombre`, `confederacion`, `region`, `rankingReferencia`, `sedeBase{ciudad,pais}`, `participacionesMundiales`, `titulosMundiales`, `estado`. Proyección explícita: no se envían `_id`, `origen`, `esDatoSintetico`, `creadoEn`, `actualizadoEn`. Encabezado `X-Cache: HIT \| MISS \| BYPASS`. |
| Si el dato no existe | Miss en Redis y `findOne` sin resultado → `404 EQUIPO_NO_ENCONTRADO`. No se cachea la ausencia. |
| Si la dependencia no está | Redis caído o con timeout → se lee MongoDB y se responde `200` con `X-Cache: BYPASS` (respuesta degradada documentada; Hito 7). Si falla el `SET`, se responde igual sin informar que quedó cacheado. MongoDB caído con miss → `503 DEPENDENCIA_NO_DISPONIBLE`. MongoDB caído con hit vigente → `200` desde caché (la copia dura como máximo 300 s). |
| Tipo de operación | Lectura. El repoblado de caché es un efecto interno, no un cambio de negocio. |
| Criterio de éxito | `200` con la ficha completa del contrato y el mismo `equipoId` solicitado. Un segundo pedido dentro de 300 s devuelve `X-Cache: HIT` sin consultar MongoDB. |

### CU-02 · Listar equipos de una confederación

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP, en el listado de selecciones filtrado por confederación. |
| Qué recibe o envía | Recibe filtros. Envía una página de fichas resumidas. |
| Fuentes | **MongoDB** `equipos`, índice `idx_equipos_confederacion_ranking` (Hito 4 Q03). |
| Datos de entrada | Query `confederacion` **obligatoria**, enum `AFC, CAF, CONCACAF, CONMEBOL, OFC, UEFA` (evita un listado global sin filtro, RNF13). `rankingMax` opcional, entero 1–250. `limite` 1–50, por defecto 20. `pagina` ≥ 1. |
| Respuesta esperada | `200` con `items[]` (`equipoId`, `codigo`, `nombre`, `rankingReferencia`), `pagina`, `limite`, `total`. Orden `rankingReferencia ASC, equipoId ASC` (estable, coincide con el índice). |
| Si el dato no existe | Filtros válidos sin coincidencias → `200` con `items: []`. Una confederación fuera del enum es `400`, no una lista vacía. |
| Si la dependencia no está | `503 DEPENDENCIA_NO_DISPONIBLE` o `504 DEPENDENCIA_TIMEOUT`. Nunca `200` vacío. |
| Tipo de operación | Lectura. |
| Criterio de éxito | Los resultados respetan filtro, orden y límite; `explain` muestra `IXSCAN` sobre el índice compuesto. |

### CU-03 · Ver plantel de un equipo

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP, en la pestaña “Plantel” de una selección. |
| Qué recibe o envía | Recibe `equipoId` y paginación. Envía jugadores ordenados. |
| Fuentes | **MongoDB** `jugadores`, índice `idx_jugadores_equipo_nombre` (Hito 4 Q06/Q07); comprobación previa de existencia en `equipos` por `uq_equipos_equipoId`. |
| Datos de entrada | Path `equipoId` `^EQ-\d{3}$`. Query `posicion` opcional (`ARQUERO`, `DEFENSOR`, `MEDIOCAMPISTA`, `DELANTERO`). `limite` 1–24, por defecto 24. `pagina` ≥ 1. |
| Respuesta esperada | `200` con `equipoId`, `items[]` (`jugadorId`, `nombre`, `apellido`, `posicion`, `numeroCamiseta`, `estadoPlantel`), `pagina`, `limite`, `total`. Orden `apellido, nombre, jugadorId`. |
| Si el dato no existe | Equipo inexistente → `404 EQUIPO_NO_ENCONTRADO`. Equipo existente sin jugadores para el filtro → `200` con `items: []`. Por eso se consulta primero `equipos` con proyección `{_id:1}`. |
| Si la dependencia no está | `503` / `504`. |
| Tipo de operación | Lectura. |
| Criterio de éxito | Para `EQ-002` sin filtros devuelve exactamente 24 jugadores (control del Hito 4). La página 2 con `limite=5` de `EQ-001` coincide con Q06. |

### CU-04 · Ver ficha de un jugador

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP, al tocar un jugador del plantel o de un evento. |
| Qué recibe o envía | Recibe `jugadorId`. Envía la ficha del jugador. |
| Fuentes | **MongoDB** `jugadores`, índice `uq_jugadores_jugadorId` (Hito 4 Q02). |
| Datos de entrada | Path `jugadorId` `^JUG-\d{4}$`. |
| Respuesta esperada | `200` con `jugadorId`, `equipoId`, `nombre`, `apellido`, `fechaNacimiento` (ISO-8601), `nacionalidadCodigo`, `posicion`, `numeroCamiseta`, `pieHabil`, `alturaCm`, `partidosInternacionales`, `golesInternacionales`, `estadoPlantel`. Sin `_id` ni campos de control. |
| Si el dato no existe | `404 JUGADOR_NO_ENCONTRADO`. |
| Si la dependencia no está | `503` / `504`. |
| Tipo de operación | Lectura. |
| Criterio de éxito | `200` con el `jugadorId` pedido y su `equipoId` válido (sin huérfanos, Hito 4 Q10). |

### CU-05 · Ver agenda y rivales de un equipo

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP, en la sección “Partidos” de una selección. |
| Qué recibe o envía | Recibe `equipoId`. Envía sus partidos con rival, rol y estadio. |
| Fuentes | **Neo4j**, recorrido `(:Equipo)-[:DISPUTA]->(:Partido)<-[:DISPUTA]-(rival)` y `(:Partido)-[:SE_JUEGA_EN]->(:Estadio)` (Hito 5 Q04 + Q06). Cypher parametrizado con `$equipoId`. |
| Datos de entrada | Path `equipoId` `^EQ-\d{3}$`. Query `limite` 1–50, por defecto 20. |
| Respuesta esperada | `200` con `equipoId`, `items[]` (`partidoId`, `inicio` ISO UTC, `grupo`, `fase`, `rol` LOCAL/VISITANTE, `rival{equipoId,codigo,nombre}`, `estadio{estadioId,nombre,ciudad}`). Orden `inicio ASC, partidoId ASC`. **No incluye el estado del partido**: la propiedad `estado` del nodo no se proyecta en el Cypher, porque la fuente autoritativa es IRIS (sección 3.1). |
| Si el dato no existe | El Cypher hace `MATCH (e:Equipo {equipoId:$id})` y luego `OPTIONAL MATCH` del recorrido. Sin nodo `Equipo` → `404 EQUIPO_NO_ENCONTRADO`. Equipo sin partidos → `200` con `items: []`. (Hito 5 Q13 mostró que un `MATCH` simple devuelve `jugadores=0` para `EQ-999`: la API no debe confundir eso con un vacío válido.) |
| Si la dependencia no está | `ServiceUnavailable` / `SessionExpired` del driver → `503`; timeout de transacción → `504`. |
| Tipo de operación | Lectura. |
| Criterio de éxito | Para `EQ-001` devuelve `PAR-001` (rival `EQ-002`) y `PAR-033` (rival `EQ-003`), ambos LOCAL en `EST-01`, como en Q04/Q06. |

### CU-06 · Ver eventos y participantes de un partido

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP, en el detalle de un partido (sustituciones y participantes). |
| Qué recibe o envía | Recibe `partidoId`. Envía los eventos con los jugadores involucrados. |
| Fuentes | **Neo4j**, recorrido `(:Partido)<-[:OCURRE_EN]-(:EventoDeportivo)-[i:INVOLUCRA]->(:Jugador)-[:PERTENECE_A]->(:Equipo)` (Hito 5 Q07). |
| Datos de entrada | Path `partidoId` `^PAR-\d{3}$`. Query `limite` 1–200, por defecto 50 (límite sobre eventos, no sobre filas). |
| Respuesta esperada | `200` con `partidoId`, `items[]` (`eventoId`, `tipo`, `minuto`, `participantes[]` con `jugadorId`, `nombre`, `apellido`, `equipoId`, `rol` SALE/ENTRA). Orden `minuto ASC, eventoId ASC`; dentro de cada evento, participantes en orden `SALE`, `ENTRA`. Nodos y relaciones se transforman a JSON plano; no se envían IDs internos de Neo4j. |
| Si el dato no existe | Partido inexistente → `404 PARTIDO_NO_ENCONTRADO`. Partido válido sin eventos → `200` con `items: []` (exigido por 5.6). |
| Si la dependencia no está | `503` / `504`. |
| Tipo de operación | Lectura. |
| Criterio de éxito | Para `PAR-001` devuelve dos eventos: minuto 60 (EQ-001: sale JUG-0020, entra JUG-0021) y minuto 65 (EQ-002: sale JUG-0044, entra JUG-0045). |

### CU-07 · Ver partidos de un rango de fechas

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP, en el calendario del día o de la semana. |
| Qué recibe o envía | Recibe un intervalo. Envía los partidos con estadio. |
| Fuentes | **Neo4j**, `(:Partido)-[:SE_JUEGA_EN]->(:Estadio)` filtrado por `Partido.inicio` con el índice `idx_partido_inicio` (Hito 5 Q09). |
| Datos de entrada | Query `desde` y `hasta` **obligatorias**, ISO-8601 con zona horaria, `desde < hasta`, intervalo ≤ 7 días (rango semiabierto `[desde, hasta)`). Una fecha sin zona → `400`; una con offset se acepta y se normaliza a UTC (misma regla para todas las fechas de la API, §6.5). `estadioId` opcional `^EST-\d{2}$`. `limite` 1–64, por defecto 64. |
| Respuesta esperada | `200` con `items[]` (`partidoId`, `inicio`, `grupo`, `fase`, `estadio{estadioId,nombre,ciudad}`). Orden `inicio, partidoId`. Sin `estado` (sección 3.1). |
| Si el dato no existe | Intervalo sin partidos → `200` con `items: []`. Estadio inexistente con formato válido → `200` vacío (es un filtro, no el recurso principal). |
| Si la dependencia no está | `503` / `504`. |
| Tipo de operación | Lectura. |
| Criterio de éxito | `desde=2030-06-10T00:00:00Z&hasta=2030-06-11T00:00:00Z` devuelve `PAR-001…PAR-008` en `EST-01…EST-08`. Un intervalo invertido o de más de 7 días da `400` sin ejecutar Cypher. |

### CU-08 · Leer comentarios de un partido

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP (refresco cada ~10 s, hasta 10.000 lecturas/s en el pico estimado del Hito 6) y MOD (revisión de ventanas). |
| Qué recibe o envía | Recibe un partido y un minuto o una ventana. Envía comentarios ordenados del más reciente al más antiguo. |
| Fuentes | Catálogo de partidos en memoria (sección 3.2) y **Cassandra** `comentarios_por_partido`, partición `(partido_id, minuto, segmento)`. Modo minuto = Hito 6 Q1 (4 particiones). Modo ventana = Hito 6 Q2 (minutos que intersectan `[desde, hasta)` × 4 segmentos, máximo 24 particiones). Sin `ALLOW FILTERING`. |
| Datos de entrada | Path `partidoId` `^PAR-\d{3}$`. Query, mutuamente excluyentes: `minuto` (ISO UTC; si falta, minuto UTC actual truncado) **o** `desde` + `hasta` (ISO UTC, `desde < hasta`, ventana ≤ 5 min). `limite`: 1–20 en modo minuto, 1–50 en modo ventana. `antesDe` opcional: cursor `creadoEn|comentarioId` del último ítem recibido. |
| Respuesta esperada | `200` con `partidoId`, `items[]` (`comentarioId`, `usuarioId`, `creadoEn`, `contenido`, `estado`, `likes`), `siguienteCursor`. Orden `creadoEn DESC, comentarioId ASC` aplicado **antes** del límite global (el adaptador fusiona las particiones; el límite no es por partición). Para APP solo se devuelven `estado = visible`; MOD recibe todos los estados. |
| Si el dato no existe | Partido fuera del catálogo (sección 3.2) → `404 PARTIDO_NO_ENCONTRADO` sin consultar Cassandra. Partido existente sin comentarios en el minuto o la ventana → `200` con `items: []`. Catálogo no cargado → `503`. |
| Si la dependencia no está | `NoHostAvailable` / `Unavailable` → `503`; `ReadTimeout` / `OperationTimedOut` → `504`. Explícitamente prohibido devolver `200 []` (5.7). |
| Tipo de operación | Lectura. |
| Criterio de éxito | Respuesta con orden y límite globales correctos y sin filtrado completo de tabla. Contra la muestra del Hito 6, los resultados coinciden con `consultas.cql`. |

### CU-09 · Publicar un comentario

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP, cuando un usuario con sesión escribe en el partido (pico de diseño: 2.000 altas/s). |
| Qué recibe o envía | Recibe el texto. Envía el comentario creado con sus claves. |
| Fuentes | **Redis**: validación y renovación de la sesión en un único `EVAL` (Hito 7) y registro de idempotencia. **Catálogo de partidos** (sección 3.2). **Cassandra**: batch registrado con una fila en `comentarios_por_partido` y otra en `comentarios_por_usuario` (Hito 6). |
| Datos de entrada | Encabezados `X-Session-Id` (obligatorio) e `Idempotency-Key` (obligatorio, UUID). Path `partidoId` `^PAR-\d{3}$`. Body JSON `{ "contenido": string 1–280 caracteres }`; se rechazan propiedades adicionales. **El cliente no envía** `usuarioId`, `creadoEn`, `minuto`, `segmento`, `dia`, `estado` ni `likes`: los calcula el servidor (`usuario_id` de la sesión, `minuto` = truncado UTC, `segmento` = CRC32(`comentario_id`) mod 4, `dia` UTC, `likes = 0`). |
| Respuesta esperada | `201` con `comentarioId`, `partidoId`, `usuarioId`, `creadoEn`, `contenido`, `estado`, `likes`. |
| Si el dato no existe | Sin sesión → `401 SESION_REQUERIDA`; sesión ausente o vencida → `401 SESION_NO_VIGENTE`. Partido fuera del catálogo (sección 3.2) → `404 PARTIDO_NO_ENCONTRADO`, sin escribir y sin consumir la `Idempotency-Key`. |
| Si la dependencia no está | Redis caído → `503` (no se puede validar la sesión; no se escribe). Cassandra caída → `503`. `WriteTimeout` → `504` con mensaje “resultado incierto, reintente con la misma Idempotency-Key”. |
| Tipo de operación | **Creación idempotente.** El comentario nace con `estado = visible` y se modera después con CU-20 (decisión de la sección 7). El `comentario_id` es la `Idempotency-Key`. En Redis se guarda `idem:comentario:<key>` con `SET NX EX 86400` y el hash del body + `creado_en`. Un reintento con la misma clave y el mismo body reutiliza el mismo `creado_en`, por lo que el batch hace upsert sobre la **misma clave primaria completa** y no duplica (y además completa una copia que hubiera quedado pendiente). Misma clave con otro body → `409 IDEMPOTENCY_KEY_REUTILIZADA`. Sin este mecanismo, un reintento generaría otro `creado_en` y Cassandra crearía una segunda fila. |
| Criterio de éxito | `201` y el comentario visible en CU-08 (modo minuto) y en CU-10 con las mismas claves. Repetir la request con la misma clave devuelve el mismo `comentarioId` y la cantidad de filas no cambia. |

### CU-10 · Ver historial diario de un autor

| Pregunta | Respuesta |
|---|---|
| Quién consume | MOD (revisión de un usuario) o APP cuando el usuario consulta lo que él mismo publicó. |
| Qué recibe o envía | Recibe autor y día. Envía sus comentarios de ese día. |
| Fuentes | **Redis** (sesión y rol) + **Cassandra** `comentarios_por_usuario`, partición `(usuario_id, dia)` (Hito 6 Q3). |
| Datos de entrada | `X-Session-Id`. Path `usuarioId` `^USR-\d{5}$`. Query `dia` obligatorio (`YYYY-MM-DD`, UTC). `limite` 1–20. `antesDe` opcional (cursor). |
| Respuesta esperada | `200` con `usuarioId`, `dia`, `items[]` (`comentarioId`, `partidoId`, `creadoEn`, `contenido`, `estado`, `likes`), `siguienteCursor`. |
| Si el dato no existe | No hay registro de usuarios en este módulo: un autor sin comentarios ese día → `200` con `items: []`. Si la sesión no es del mismo `usuarioId` ni tiene rol `moderador` → `403 ROL_NO_AUTORIZADO`. |
| Si la dependencia no está | Redis → `503`. Cassandra → `503` / `504`. |
| Tipo de operación | Lectura. |
| Criterio de éxito | Devuelve solo filas de una partición, en el orden del clustering, y coincide con lo publicado en CU-09. |

### CU-20 · Moderar un comentario

| Pregunta | Respuesta |
|---|---|
| Quién consume | MOD, después de revisar comentarios con CU-08 (todos los estados) o CU-10 (historial de un autor). Frecuencia de diseño: hasta 100 ediciones por segundo (Hito 6). |
| Qué recibe o envía | Recibe el comentario a moderar y el estado destino. Envía el comentario con su estado anterior y el resultante. |
| Fuentes | **Redis**: sesión con rol `moderador`. **Cassandra**: lectura puntual en `comentarios_por_partido` con la clave primaria completa y luego batch registrado que actualiza `estado` en `comentarios_por_partido` y en `comentarios_por_usuario` (operación de edición del Hito 6, `crud.cql`). |
| Datos de entrada | `X-Session-Id` con rol `moderador`. Path `partidoId` `^PAR-\d{3}$` y `comentarioId`. Body `{ "creadoEn": ISO-8601 UTC con milisegundos, "estado": "visible" \| "oculto" }`, sin propiedades adicionales. `creadoEn` es obligatorio porque forma parte de la clave primaria y el moderador lo obtiene de la respuesta de CU-08 o CU-10. El servidor deriva `minuto`, `segmento` (CRC32 de `comentarioId` mod 4) y, de la fila leída, `usuario_id` y `dia`. No se modera `likes`: es interacción de los usuarios, no una decisión de moderación. |
| Respuesta esperada | `200` con `comentarioId`, `partidoId`, `usuarioId`, `creadoEn`, `estadoAnterior`, `estado`, `cambio`. |
| Si el dato no existe | Partido fuera del catálogo → `404 PARTIDO_NO_ENCONTRADO`. Si la lectura por clave completa no devuelve fila → `404 COMENTARIO_NO_ENCONTRADO` y **no se escribe nada**. La lectura previa es obligatoria: en CQL un `UPDATE` sobre una clave inexistente crea la fila, de modo que actualizar a ciegas con un `creadoEn` equivocado fabricaría un comentario fantasma. Sin sesión → `401`; sin rol `moderador` → `403 ROL_NO_AUTORIZADO`. `estado` fuera de `visible`/`oculto` → `400`. |
| Si la dependencia no está | Redis → `503` (no se autoriza). Cassandra → `503`; `WriteTimeout` → `504` con resultado incierto: el batch registrado completa la escritura pendiente y el moderador puede reintentar la misma request. |
| Tipo de operación | **Actualización validada e idempotente.** El estado es un valor absoluto, no un incremento: repetir la request deja el mismo resultado. Si el estado actual ya es el pedido, responde `200` con `cambio: false` sin escribir. Transiciones permitidas: `pendiente → visible`, `pendiente → oculto`, `visible → oculto` y `oculto → visible` (restaurar). Volver a `pendiente` no está permitido (`400`). Igual que en el Hito 6, se asume un único moderador editando cada comentario; dos moderaciones simultáneas sobre el mismo comentario se resuelven por última escritura. |
| Criterio de éxito | `200` y el nuevo estado visible en las **dos** representaciones: CU-08 (vista del partido) y CU-10 (historial del autor) devuelven el mismo `estado`. Un comentario `oculto` deja de aparecer en CU-08 para la APP y sigue apareciendo para MOD. La cantidad de filas no cambia. |

### CU-11 · Consultar la sesión vigente

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP al iniciar o volver a primer plano; INT antes de cada operación protegida. |
| Qué recibe o envía | Recibe el identificador de sesión. Envía si está vigente y sus atributos públicos. |
| Fuentes | **Redis** hash `sesion:<id>` (`HGETALL` + `TTL`, Hito 7). |
| Datos de entrada | Encabezado `X-Session-Id`, `^[A-Za-z0-9-]{8,64}$`. |
| Respuesta esperada | `200` con `usuarioId`, `rol`, `estado`, `expiraEnSegundos`. No se devuelven `ultima_actividad` ni el propio identificador (no los necesita el consumidor). **No renueva el TTL** (una inspección no es actividad, Hito 7). |
| Si el dato no existe | Clave ausente, `TTL = -2`, `TTL = -1` (sin vencimiento, no aceptada) o `estado ≠ activa` → `401 SESION_NO_VIGENTE`. Redis no distingue “vencida” de “nunca existió”: ambos casos tienen el mismo código. Encabezado ausente → `401 SESION_REQUERIDA` sin consultar Redis. |
| Si la dependencia no está | `503 DEPENDENCIA_NO_DISPONIBLE`. Nunca `401`: Redis caído no significa sesión inválida, y el cliente no debe borrar su sesión local por un `503`. |
| Tipo de operación | Lectura. |
| Criterio de éxito | `200` solo si la clave existe, `estado = activa` y `TTL > 0`, que es la definición de acceso válido del Hito 7. |

### CU-12 · Registrar actividad de la sesión

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP, ante una acción del usuario que cuenta como actividad. INT reutiliza la misma operación en CU-09 y CU-10. |
| Qué recibe o envía | Recibe la sesión. Envía el nuevo vencimiento. |
| Fuentes | **Redis**, script `EVAL` que comprueba existencia y estado, hace `HSET ultima_actividad` con `TIME` del servidor y `EXPIRE 1800` de forma atómica (Hito 7). |
| Datos de entrada | `X-Session-Id`. Sin body. |
| Respuesta esperada | `200` con `expiraEnSegundos: 1800`. |
| Si el dato no existe | El script devuelve 0 → `401 SESION_NO_VIGENTE`. No se recrea una sesión ausente. |
| Si la dependencia no está | `503` / `504`. Ante timeout no se informa un TTL nuevo (Hito 7). |
| Tipo de operación | Actualización. Repetirla solo vuelve a fijar el TTL en 1800 s: es segura ante reintentos. |
| Criterio de éxito | `200` y un `TTL` posterior cercano a 1800 s. Si un cierre (CU-13) ocurrió antes, la renovación devuelve `401` y la sesión sigue ausente. |

### CU-13 · Cerrar la sesión

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP, al pulsar “Salir”. |
| Qué recibe o envía | Recibe la sesión. No envía cuerpo. |
| Fuentes | **Redis** `DEL sesion:<id>`. |
| Datos de entrada | `X-Session-Id`. |
| Respuesta esperada | `204`. |
| Si el dato no existe | `204` igualmente: cerrar una sesión ausente deja el mismo estado final (Hito 7: repetir el cierre devuelve 0 y la sesión sigue ausente). |
| Si la dependencia no está | `503`. Es importante no responder `204`: el usuario no debe creer que cerró la sesión si no se confirmó. |
| Tipo de operación | Invalidación idempotente. |
| Criterio de éxito | `204` y CU-11 con la misma sesión devuelve `401 SESION_NO_VIGENTE`. |

### CU-14 · Invalidar la ficha cacheada de un equipo

| Pregunta | Respuesta |
|---|---|
| Quién consume | OPS, inmediatamente después de modificar la ficha del equipo en MongoDB (paso 6 del cache-aside del Hito 7). |
| Qué recibe o envía | Recibe el `equipoId`. No envía cuerpo. |
| Fuentes | **Redis** `DEL cache:equipo:<equipoId>`; sesión y rol en Redis. |
| Datos de entrada | `X-Session-Id` con rol `operador`. Path `equipoId` `^EQ-\d{3}$`. |
| Respuesta esperada | `204`. |
| Si el dato no existe | Copia ausente → `204` (no había nada que invalidar). Sin rol → `403 ROL_NO_AUTORIZADO`. |
| Si la dependencia no está | `503`. Mientras la invalidación no se confirme, la copia puede durar hasta 300 s; el operador debe reintentar (Hito 7: no se continúa leyendo una copia potencialmente vieja). |
| Tipo de operación | Invalidación idempotente. |
| Criterio de éxito | `204` y el siguiente CU-01 responde `X-Cache: MISS` con la ficha actualizada de MongoDB. |

### CU-15 · Ver estado reciente de un equipo en un partido

| Pregunta | Respuesta |
|---|---|
| Quién consume | APP, en la vista “en vivo” (lectura conceptual cada 5 s, Hito 8 P2). |
| Qué recibe o envía | Recibe partido, equipo y fin de ventana. Envía las últimas observaciones con su timestamp. |
| Fuentes | Catálogo de partidos (sección 3.2) e **InfluxDB** `fixture2030_h8.estadisticas_equipo`, filtro por tags `partido_id` y `equipo_id`, ventana `[hasta − 60 s, hasta)` (Hito 8 P2). |
| Datos de entrada | Path `partidoId` `^PAR-\d{3}$`, `equipoId` `^EQ-\d{3}$`. Query `hasta` ISO UTC opcional (por defecto, ahora). `limite` 1–60, por defecto 5. |
| Respuesta esperada | `200` con `partidoId`, `equipoId`, `estadioId`, `items[]` (`time`, `posesionPct`, `pasesAcumulados`, `tirosIntervalo`) en orden descendente y `ultimaObservacion`. El consumidor compara `ultimaObservacion` con la hora actual para detectar datos atrasados. |
| Si el dato no existe | Sin puntos en la ventana → `200` con `items: []` y `ultimaObservacion: null`. Significa “no hay observaciones”, **no** que las estadísticas valgan cero (Hito 8). Partido fuera del catálogo → `404 PARTIDO_NO_ENCONTRADO`; equipo que no disputa ese partido → `404 EQUIPO_NO_PARTICIPA`. Ambos se resuelven con el catálogo (sección 3.2) antes de consultar InfluxDB. |
| Si la dependencia no está | HTTP 5xx o error de conexión del cliente Influx → `503`; timeout → `504`. Token inválido → `500 ERROR_INTERNO` (es un error de configuración), con detalle solo en logs. |
| Tipo de operación | Lectura. |
| Criterio de éxito | Hasta `limite` puntos de una sola serie dentro de la ventana, con sus timestamps intactos (RNF17). |

### CU-16 · Comparar los equipos de un partido

| Pregunta | Respuesta |
|---|---|
| Quién consume | ANA (consulta conceptual cada minuto, Hito 8 P3). |
| Qué recibe o envía | Recibe partido y ventana. Envía una fila por equipo con medidas agregadas. |
| Fuentes | **InfluxDB**, SQL con `AVG(posesion_pct)`, `SUM` de diferencias `LAG(pases_acumulados)` incluyendo la muestra anterior a la ventana, y `SUM(tiros_intervalo)` (Hito 8 `consultas_temporales.py`). |
| Datos de entrada | Path `partidoId`. Query `desde` y `hasta` obligatorias, ISO UTC, `desde < hasta`, ventana ≤ 5 min. |
| Respuesta esperada | `200` con `partidoId`, `desde`, `hasta`, `equipos[]` (`equipoId`, `muestras`, `muestrasEsperadas`, `posesionMedia`, `pasesNuevos`, `tiros`, `intervalosInvalidos`, `completo`). Se documenta la agregación de cada medida. |
| Si el dato no existe | Partido fuera del catálogo → `404 PARTIDO_NO_ENCONTRADO`. Partido existente sin puntos → `200` con `equipos: []`. Ventana incompleta o con contador que retrocede → `200` con `completo: false` e `intervalosInvalidos > 0`; no se rellenan huecos con ceros. |
| Si la dependencia no está | `503` / `504`. |
| Tipo de operación | Lectura agregada. |
| Criterio de éxito | Para la reproducción de PAR-001 del Hito 8 (ventana de 5 min): EQ-001 300 muestras, 49,975 %, 30 pases, 1 tiro; EQ-002 300 muestras, 50,025 %, 25 pases, 1 tiro; `intervalosInvalidos = 0`. |

### CU-17 · Ver evolución por minuto

| Pregunta | Respuesta |
|---|---|
| Quién consume | ANA, en un gráfico de tendencia (Hito 8 P4). |
| Qué recibe o envía | Recibe partido, ventana y resolución. Envía un intervalo por equipo y minuto. |
| Fuentes | **InfluxDB**, `DATE_BIN` por minuto UTC con las mismas agregaciones de CU-16 (Hito 8 `agregaciones.py`). |
| Datos de entrada | Path `partidoId`. Query `desde`, `hasta` obligatorias, ventana ≤ 2 h (límite de consulta documentado en el Hito 8). `resolucion` ∈ {`1m`, `5m`}, por defecto `1m`. `equipoId` opcional. Máximo de filas: 120 intervalos × 2 equipos. |
| Respuesta esperada | `200` con `resolucion`, `series[]` por equipo con `intervalos[]` (`inicio`, `muestras`, `posesionMedia`, `pasesNuevos`, `tiros`, `completo`). |
| Si el dato no existe | Partido fuera del catálogo → `404 PARTIDO_NO_ENCONTRADO`; `equipoId` que no disputa el partido → `404 EQUIPO_NO_PARTICIPA`. Partido existente sin puntos → `200` con `series: []`. Intervalos incompletos marcados con `completo: false`. |
| Si la dependencia no está | `503` / `504`. |
| Tipo de operación | Lectura agregada, calculada bajo demanda (no se materializa). |
| Criterio de éxito | Cinco intervalos por equipo para la ventana de prueba de PAR-001 cuyas sumas coinciden con CU-16 (30 y 25 pases). |

### CU-18 · Ver el acta de un partido

| Pregunta | Respuesta |
|---|---|
| Quién consume | OPS (gestión del partido) y APP. Es la **única** operación de la API que informa el estado de un partido (sección 3.1). |
| Qué recibe o envía | Recibe `partidoId`. Envía el acta: estado, árbitro y eventos registrados. |
| Fuentes | **IRIS** namespace `USER`, clases `FixtureH9.Partido` (índice único `PorCodigo`) y `FixtureH9.Evento` (relación parent/children e índice `PorPartido`). Lectura por SQL proyectado o por apertura del objeto vía índice (Hito 9). |
| Datos de entrada | Path `partidoId` `^PAR-\d{3}$` (se mapea a `Partido.Codigo`). |
| Respuesta esperada | `200` con `partidoId`, `estadioId`, `estado`, `arbitro{codigo,nombre,nacionalidad}`, `eventos[]` (`tipo` GOL/TARJETA/CAMBIO, `minuto`, `jugador{codigo,nombre,numero,posicion}`), ordenados por `minuto`. No se exponen `%ID` (`1`, `1\|\|1`), la licencia del árbitro ni nombres de clases. |
| Si el dato no existe | Sin `Partido` con ese código → `404 ACTA_NO_ENCONTRADA`. Hoy la muestra de IRIS solo contiene `PAR-001`: un `PAR-002` existe en Neo4j pero no tiene acta, y se informa así. Acta sin eventos → `200` con `eventos: []`. |
| Si la dependencia no está | Error de conexión o login del SDK → `503`; timeout → `504`. |
| Tipo de operación | Lectura. |
| Criterio de éxito | Para `PAR-001` devuelve estado `PENDIENTE`, estadio `EST-01`, el árbitro `ARB-001` y sus dos eventos, coherentes con `FixtureH9.Demo.Verificar()`. |

### CU-19 · Cambiar el estado de un partido

| Pregunta | Respuesta |
|---|---|
| Quién consume | OPS (operador de partido) al iniciar y al finalizar el encuentro. |
| Qué recibe o envía | Recibe el estado destino. Envía el estado anterior y el resultante. |
| Fuentes | **Redis** (sesión y rol `operador`) + **IRIS**: el adaptador abre el `Partido` por `PorCodigo` con bloqueo exclusivo y llama a `CambiarEstado(nuevo)`, que valida y guarda (Hito 9). Nunca se usa `UPDATE` SQL, que eludiría la regla. **No se escribe en Neo4j**: la transición tiene una sola fuente y no requiere coordinación entre bases (sección 3.1). Como el SDK nativo invoca mejor métodos de clase, se recomienda un `ClassMethod` envoltorio (por ejemplo, `FixtureH10.Servicio.Transicionar(codigo, nuevo)`, versionado en `Hito 10/iris/` para no modificar el Hito 9) que devuelva un código de resultado. |
| Datos de entrada | `X-Session-Id` con rol `operador`. Path `partidoId`. Body `{ "nuevoEstado": "EN_JUEGO" \| "FINALIZADO" }`; cualquier otro valor (incluido `PENDIENTE`) es `400` sin consultar IRIS. |
| Respuesta esperada | `200` con `partidoId`, `estadoAnterior`, `estadoActual`, `cambio: true`. |
| Si el dato no existe | Acta inexistente → `404 ACTA_NO_ENCONTRADA`. Sesión → `401`; rol insuficiente → `403`. Transición no permitida (por ejemplo `FINALIZADO → EN_JUEGO` o `PENDIENTE → FINALIZADO`) → `409 TRANSICION_NO_PERMITIDA`, con el estado actual en `detalles`; el estado persistido no cambia. |
| Si la dependencia no está | Redis → `503` (no se autoriza). IRIS → `503`; timeout → `504` con resultado incierto. |
| Tipo de operación | Actualización validada. **Idempotencia**: si el estado actual ya es el solicitado, la API responde `200` con `cambio: false` sin llamar a `CambiarEstado`. Así un reintento tras un `504` es seguro: o la transición no se había aplicado y se aplica, o ya estaba aplicada y no se repite. Una carrera entre dos operadores la resuelve el bloqueo del objeto y la validación de `CambiarEstado` (el segundo recibe `409`). |
| Criterio de éxito | `200` y CU-18 muestra el nuevo estado. `PENDIENTE → EN_JUEGO → FINALIZADO` se aplica; reabrir un partido finalizado devuelve `409` y conserva `FINALIZADO`, igual que la demo del Hito 9. Las pruebas usan un acta temporal, no `PAR-001`. |

## 6. Convenciones transversales

### 6.1 Formato de error único

```json
{
  "error": {
    "codigo": "PARTIDO_NO_ENCONTRADO",
    "mensaje": "No existe un partido con el identificador indicado.",
    "requestId": "8f0c2a1e-6b3d-4f7a-9d55-2a1b7c9e4d10",
    "detalles": [ { "campo": "partidoId", "problema": "PAR-999 no existe" } ]
  }
}
```

Nunca incluye URIs de conexión, credenciales, consultas Cypher/CQL/SQL, stack traces ni mensajes crudos del driver. El `requestId` también viaja en el encabezado `X-Request-Id` (se acepta el del cliente si es un UUID válido) y aparece en cada línea de log del router, el servicio y el adaptador (RF18).

### 6.2 Códigos HTTP

| HTTP | Código de error | Cuándo |
|---|---|---|
| 400 | `VALIDACION` | Parámetro ausente, formato o enum inválido, intervalo invertido o excedido, body con campos extra. Se responde antes de consultar. |
| 401 | `SESION_REQUERIDA` | Falta `X-Session-Id` en una operación protegida. |
| 401 | `SESION_NO_VIGENTE` | Sesión ausente, vencida, sin TTL o con `estado ≠ activa`. |
| 403 | `ROL_NO_AUTORIZADO` | Sesión vigente sin el rol necesario. |
| 404 | `EQUIPO_NO_ENCONTRADO`, `JUGADOR_NO_ENCONTRADO`, `PARTIDO_NO_ENCONTRADO`, `ACTA_NO_ENCONTRADA`, `COMENTARIO_NO_ENCONTRADO`, `EQUIPO_NO_PARTICIPA` | El recurso principal de la ruta no existe. |
| 404 | `RUTA_NO_ENCONTRADA` | La ruta no existe en la API. |
| 405 | `METODO_NO_PERMITIDO` | La ruta existe pero no admite ese método HTTP (el encabezado `Allow` indica los métodos válidos). |
| 409 | `TRANSICION_NO_PERMITIDA` | Regla de negocio violada por el estado actual. |
| 409 | `IDEMPOTENCY_KEY_REUTILIZADA` | Misma clave con distinto contenido. |
| 503 | `DEPENDENCIA_NO_DISPONIBLE` | La fuente rechaza la conexión o no hay nodos disponibles. También cuando el catálogo de partidos todavía no pudo cargarse. |
| 504 | `DEPENDENCIA_TIMEOUT` | La fuente no respondió dentro del límite; en escrituras, el resultado es incierto. |
| 500 | `ERROR_INTERNO` | Error inesperado o de configuración; el detalle queda solo en logs. |

### 6.3 Timeouts propuestos (RNF8, RNF9)

| Fuente | Parámetro del cliente | Valor propuesto |
|---|---|---|
| MongoDB | `serverSelectionTimeoutMS`, `socketTimeoutMS` | 2 s / 3 s |
| Neo4j | `connection_timeout`, timeout de transacción | 2 s / 3 s |
| Cassandra | `request_timeout` del perfil de ejecución | 2 s |
| Redis | `socket_connect_timeout`, `socket_timeout` | 0,5 s / 0,5 s |
| InfluxDB | timeout HTTP del cliente | 5 s |
| IRIS | timeout de conexión del SDK | 3 s |

Son valores iniciales para el entorno local con un nodo por motor. Se documentan junto a la medición que los respalde; sin medición no se publican cifras de latencia (RNF18).

### 6.4 Lectura, escritura e idempotencia (RF19)

| Tipo | Casos de uso | Comportamiento ante repetición |
|---|---|---|
| Lectura sin efectos | CU-02 a CU-08, CU-10, CU-11, CU-15 a CU-18 | Repetir no cambia datos. |
| Lectura con efecto interno | CU-01 | Puede repoblar la caché; no cambia datos de negocio. |
| Creación | CU-09 | Idempotente por `Idempotency-Key`; sin clave → `400`. |
| Actualización | CU-12, CU-19, CU-20 | CU-12 reestablece el TTL; CU-19 y CU-20 fijan un estado absoluto y devuelven `cambio: false` si ya era el pedido. |
| Invalidación | CU-13, CU-14 | `204` aunque la clave ya no exista. |

### 6.5 Fechas

Toda fecha de entrada es ISO-8601 con zona horaria explícita (`Z` o un offset como `-03:00`). Una fecha sin zona es ambigua y se rechaza con `400 VALIDACION` antes de consultar. Las fechas con offset se normalizan a UTC. Toda fecha de salida se informa en UTC con sufijo `Z`.

## 7. Decisiones tomadas y alcance

Todas las decisiones abiertas en la versión anterior de este documento quedaron resueltas por el equipo.

### 7.1 Decisiones de diseño

| Decisión | Elección | Alternativa descartada | Justificación |
|---|---|---|---|
| Fuente del estado del partido | IRIS, única fuente autoritativa (sección 3.1) | Exponer también `Partido.estado` de Neo4j | Evita dos valores distintos del mismo dato; CU-19 escribe en una sola base. |
| Sincronización del estado hacia Neo4j | No se sincroniza | Copia asincrónica de IRIS a Neo4j | Nadie lee ese valor a través de la API; evita una escritura en dos bases. |
| Partido inexistente en Cassandra e InfluxDB | `404` validado contra un catálogo en memoria cargado desde Neo4j (sección 3.2) | `200` vacío documentado; consulta a Neo4j por request; colección de partidos en MongoDB | Distingue ausencia de vacío válido sin sumar latencia ni acoplar la disponibilidad de comentarios a Neo4j. |
| Estado inicial de un comentario | `visible`, con moderación posterior (CU-20) | `pendiente`, con moderación previa | Es un chat en vivo con picos de 2.000 altas/s; esperar una aprobación lo volvería inútil. |
| Moderación | Se implementa CU-20: cambia `estado` entre `visible` y `oculto` | Dejar el rol `moderador` solo con lectura | Un rol de moderación sin una operación para moderar sería incoherente. |
| Paginación | MongoDB por `pagina`/`limite`; Cassandra por cursor `(creadoEn, comentarioId)` | Cursor también en MongoDB | Con 64 equipos y 24 jugadores por plantel `skip/limit` es suficiente y coincide con el Hito 4. Con más volumen se migraría a cursor por la clave del índice. |
| Alcance | Los 20 casos de uso | Solo un núcleo de 10 | Cubre RF3–RF8 completos y todas las fuentes con lectura, escritura, invalidación y transición. |

### 7.2 Fuera del alcance de la API

| Funcionalidad | Motivo |
|---|---|
| Ranking de partidos más visitados (Sorted Set del Hito 7) | El incremento no es idempotente y el Hito 7 decidió no reintentarlo ante una respuesta perdida. |
| Creación de sesiones (login) | El Hito 7 supone un acceso validado fuera del módulo. La API consulta, renueva y cierra sesiones; las de prueba se crean con `Hito 10/scripts/crear_sesiones_prueba.ps1`. |
| Escritura de estadísticas | El productor es el proveedor o generador del Hito 8. La API solo lee. |
| Edición de `likes` | Es interacción de usuarios, no moderación, y el Hito 6 no implementa incrementos concurrentes. |

### 7.3 Evoluciones futuras

- **Reglas de comentario según el estado del partido:** IRIS, como dueña del ciclo de vida, validaría si un partido admite comentarios en su estado actual. Requiere que todos los partidos tengan acta en IRIS (sección 3.2).
- **Sincronización del estado hacia Neo4j:** solo si otra vista del grafo lo necesitara; sería asincrónica, después de cada transición confirmada, con consistencia eventual.
- **Paginación por cursor en MongoDB** si los volúmenes crecen.
