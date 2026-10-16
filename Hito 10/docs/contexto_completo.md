# Contexto completo del Hito 10 - API REST integrada (Fixture 2030, Grupo 13)

Documento de contexto para retomar el trabajo o responder preguntas sobre el Hito 10. Describe qué se pidió, qué se construyó, cómo funciona cada parte, cómo se ejecuta, qué decisiones se tomaron, qué problemas aparecieron y qué queda pendiente.

---

## 1. Contexto de la materia

- Asignatura: Ingeniería de Datos II (UADE). Trabajo práctico grupal "Fixture Mundial 2030", Grupo 13.
- Repositorio: `https://github.com/AxelYairFischbein/Fixture2030-Grupo13`, carpetas `Hito 4` a `Hito 9`, `Hito 10` y `Hito 10a`.
- Cada hito anterior implementó un módulo NoSQL con Docker Compose y datos sintéticos:

| Hito | Motor | Módulo | Datos de muestra |
| --- | --- | --- | --- |
| 4 | MongoDB 8 | Equipos y jugadores (colecciones `equipos`, `jugadores`, base `fixture2030`) | 64 equipos `EQ-001..EQ-064` (códigos `F01..F64`), 1.536 jugadores `JUG-0001..JUG-1536`, 24 por equipo |
| 5 | Neo4j | Grafo: `Jugador-[:PERTENECE_A]->Equipo-[:DISPUTA {rol}]->Partido-[:SE_JUEGA_EN]->Estadio`, `EventoDeportivo-[:OCURRE_EN]->Partido`, `EventoDeportivo-[:INVOLUCRA {rol SALE/ENTRA}]->Jugador` | 64 partidos `PAR-001..PAR-064`, 8 estadios `EST-01..EST-08`, 128 eventos (sustituciones) |
| 6 | Cassandra | Comentarios masivos, keyspace `fixture2030_comentarios`. Tabla principal `comentarios_por_partido` con PK `((partido_id, minuto, segmento), creado_en, comentario_id)` y tabla secundaria `comentarios_por_usuario` con PK `((usuario_id, dia), creado_en, comentario_id)`. Segmento = `CRC32(comentario_id) % 4` | 12 comentarios `MUESTRA-001..012`, casi todos en PAR-001 entre 18:00 y 18:03 UTC del 10/06/2030 |
| 7 | Redis | Sesiones (hash con TTL 1800 s creado con Lua), caché de ficha de equipo (String JSON, TTL 300 s), ranking (sorted set). Puerto publicado 16379 | Claves demo `fixture2030:h7:demo:*` |
| 8 | InfluxDB 3 Core | Series temporales: base `fixture2030_h8`, tabla `estadisticas_equipo`, tags `partido_id, equipo_id, estadio_id`, fields `posesion_pct, pases_acumulados, tiros_intervalo`. Retención 7 días. Token en `Hito 8/.local/admin.token` | 21.600 puntos (PAR-001 y PAR-002, 90 min, 1/s), generados el 09/10/2026 y vencidos el 16/10/2026 |
| 9 | InterSystems IRIS | Objetos persistentes en namespace `USER`, paquete `FixtureH9`: `Persona` (base), `Jugador` y `Arbitro` (herencia), `Partido` (padre) con `Eventos` (relación parent/children con `Evento`). Método `Partido.CambiarEstado(nuevo)` que solo permite `PENDIENTE -> EN_JUEGO -> FINALIZADO` (error 5001 si no) | Un partido `PAR-001` en `PENDIENTE`, árbitro `ARB-001`, jugador `JUG-0001`, eventos con IDs `1\|\|1` y `1\|\|2` |

- Todos comparten identificadores (`EQ-001`, `PAR-001`, `JUG-0001`, `EST-01`, `USR-00001`), aunque no hay conexiones entre bases.
- El entorno es Windows 10 con PowerShell, Docker Desktop y Python 3.14.

## 2. Qué pide el Hito 10 (consigna)

PDF: `Hito 10a/Hito_10_Requisitos_Tecnicos_-_API_REST_Integrada_Fixture_2030.md.pdf`. Hay que hacer una API REST que acceda a los módulos NoSQL mediante **adaptadores separados**, con:

- Casos de uso documentados antes de las rutas.
- Un endpoint por fuente: Mongo (documentos), Neo4j (Cypher parametrizado), Cassandra (respetando la partición, lectura y escritura), Redis (sesión con clave inexistente o expirada), InfluxDB (intervalo y agregación) e IRIS (entidad compleja y transición validada).
- Separación entre rutas, servicios y adaptadores.
- Validación antes de consultar.
- Errores consistentes: ausencia, validación, conflicto, dependencia caída y error interno. Nunca un 200 que oculte una falla.
- OpenAPI con Swagger, colección Postman o cURL, y pruebas: éxito, inválido, inexistente, dependencia caída, vacío válido, sesión expirada, escritura repetida y límites.
- Configuración por variables de entorno, sin secretos en Git.
- Evidencia, request ID, idempotencia, timeouts, paginación, logs sin secretos y rendimiento con método.
- Documentación con apartados: casos de uso, arquitectura, endpoints, contratos, adaptadores, validación, errores, conectividad, idempotencia, pruebas, seguridad, rendimiento y coherencia con el TPO.
- Además, el usuario pidió **una interfaz gráfica** integrada.

## 3. Qué se construyó (resumen)

En la carpeta `Hito 10/`:

- La API **FastAPI** (Python) tiene 15 operaciones bajo `/api/v1` y escucha en `127.0.0.1:8000`.
- La **consola web** es un único `web/index.html`, sin dependencias externas, y la sirve la API en `/`.
- Swagger UI está en `/docs` y el contrato versionado en `openapi/openapi.yaml`.
- La colección Postman tiene 32 requests con aserciones.
- Hay **36 pruebas pytest**, todas aprobadas: 16 unitarias sin bases y 20 de integración contra las 6 bases reales.
- El script `fixture.ps1` agrupa los comandos (levantar, verificar, probar y detener).
- La documentación está en `docs/` y la evidencia en `docs/evidencia/`.
- No se modificó ningún hito anterior.

## 4. Estructura de archivos y rol de cada uno

```text
Hito 10/
├── fixture.ps1              # atajos: todo, bases, esperar, verificar, api, abrir, influx, iris-usuario, pruebas, unitarias, latencia, detener
├── README.md                # guía de uso
├── requirements.txt         # dependencias con versión fija
├── pytest.ini               # pythonpath=., filtros de warnings, marker "integracion"
├── .env.example             # todas las variables sin secretos (.env real ignorado por Git)
├── .gitignore               # .env, .local/, .venv/, __pycache__, *.token, *.key
├── app/
│   ├── main.py              # crear_app(): ensambla, middleware X-Request-ID + logs, handlers de error, ajuste OpenAPI, sirve la GUI
│   ├── routes.py            # rutas HTTP: parámetros con patrones/rangos, cuerpos, códigos documentados; arma {data, meta}
│   ├── services.py          # clase Servicios: casos de uso y reglas (sin HTTP ni drivers)
│   ├── schemas.py           # modelos Pydantic de request/response y patrones de IDs (fuente del OpenAPI)
│   ├── errors.py            # ApiError y subclases (400, 404, 409, 503) + cuerpo_error()
│   ├── contexto.py          # contextvars (request_id, trazas) y el context manager operacion()
│   ├── config.py            # lee el entorno y .env, dataclass Config
│   └── adapters/
│       ├── mongo_equipos.py         # pymongo
│       ├── neo4j_partidos.py        # neo4j driver
│       ├── cassandra_comentarios.py # cassandra-driver (+ pyasyncore)
│       ├── redis_kv.py              # redis-py: sesiones, caché, idempotencia
│       ├── influx_estadisticas.py   # httpx contra la API SQL v3 de InfluxDB
│       └── iris_actas.py            # intersystems-irispython (DB-API + API nativa)
├── web/index.html           # consola gráfica
├── openapi/openapi.yaml     # exportado desde la app (scripts/exportar_openapi.py)
├── postman/fixture2030_collection.json
├── tests/
│   ├── README.md
│   ├── unit/test_api.py             # adaptadores falsos en memoria
│   └── integration/test_integracion.py  # adaptadores reales contra los contenedores
├── scripts/
│   ├── iniciar_api.ps1              # crea .venv la primera vez y ejecuta uvicorn --factory
│   ├── verificar_conectividad.py    # ping a las 6 bases por sus adaptadores; exit 1 si alguna falla
│   ├── ejecutar_pruebas.ps1         # exporta OpenAPI, verifica conectividad y corre pytest (-SoloUnitarias)
│   ├── exportar_openapi.py          # escribe openapi/openapi.yaml
│   ├── medir_latencia.py            # 200 requests secuenciales por ruta, p50/p95/máx
│   ├── iris_crear_usuario_api.ps1   # crea el rol y el usuario IRIS de la API (password por stdin)
│   └── cargar_muestra_influx.py     # agrega puntos recientes a InfluxDB si venció la muestra del Hito 8
└── docs/
    ├── casos_de_uso.md              # CU1-CU15 + mapa de endpoints + por qué cada fuente
    ├── arquitectura_y_adaptadores.md# capas, tabla de adaptadores, decisiones, respuestas a las 20 preguntas guía
    ├── contratos_y_errores.md       # formato de respuesta y error, códigos, validación, paginación, idempotencia
    ├── conectividad_y_configuracion.md # hosts/puertos, variables, timeouts, seguridad, datos que agrega la API
    ├── pruebas_y_evidencia.md       # método de prueba, cobertura, evidencia, rendimiento, coherencia con el TPO
    ├── contexto_completo.md         # este archivo
    └── evidencia/01..06_*.txt
```

## 5. Arquitectura y flujo de un request

```
Cliente (GUI / Swagger / Postman / cURL)
  -> main.py middleware: toma o genera X-Request-ID, inicializa la lista de trazas, mide la duración, captura excepciones no previstas (500)
  -> routes.py: FastAPI valida path, query, headers y body con los patrones de schemas.py (si falla: 400, sin tocar ninguna base)
  -> services.py: aplica reglas (ventanas, cursor, cache-aside, idempotencia, PUT sin cambio) y llama a los adaptadores
  -> adapters/*: ejecutan la consulta fija y parametrizada dentro de `with operacion(fuente, nombre, ERRORES_DEL_DRIVER)`
  -> base NoSQL
```

**`contexto.operacion()`** es la pieza central de la integración:

- Mide la duración de cada operación contra una base.
- Escribe una línea de log: `req=<id> dep=<fuente> op=<operación> resultado=<ok|error:Tipo|...> ms=<x>`.
- Agrega `{fuente, operacion, resultado, ms}` a `meta.fuentes` de la respuesta. Así se ve qué bases tocó realmente cada request.
- **Traduce** las excepciones del driver (la tupla que pasa cada adaptador) a `DependenciaNoDisponible` (503). Nunca se loguean mensajes del driver, solo el nombre del tipo de excepción, para no filtrar hosts ni credenciales.

**Inyección de dependencias:**

- `crear_app(servicios=None)`: si no recibe servicios, construye los reales con `servicios_reales(config.cargar())`.
- Las pruebas unitarias pasan una instancia de `Servicios` con adaptadores falsos.
- uvicorn se inicia con `app.main:crear_app --factory`. No hay instancia a nivel de módulo, así que importar `app.main` no abre conexiones.

**Conexiones perezosas:**

- Los clientes se crean sin conectar. La API arranca aunque alguna base esté caída y se reconecta cuando vuelve.
- Cassandra conecta en el primer uso y reintenta si falló.
- IRIS usa una conexión con `threading.Lock` (el driver no es thread-safe) y la reabre tras una falla.
- Los endpoints son sincrónicos (`def`); FastAPI los corre en su pool de hilos.

## 6. Endpoints (prefijo `/api/v1`)

| Método y ruta | Fuente(s) | Qué hace | Códigos |
| --- | --- | --- | --- |
| `GET /salud` | las 6 | `ping` por adaptador. 200 si todas responden; si no, 503 con `error.detalles` = estado por fuente | 200, 503 |
| `GET /equipos?confederacion&pagina&tamanio` | MongoDB | `find` con proyección, orden `rankingReferencia, equipoId` (índice `idx_equipos_confederacion_ranking`), skip/limit + `count_documents` para el total | 200, 400, 503 |
| `GET /equipos/{equipoId}` | Redis → MongoDB | Cache-aside: `GET fixture2030:h10:cache:equipo:{id}`; si falta, `find_one` y `SET EX 300`. Header `X-Cache` y `meta.cache` = HIT / MISS / BYPASS (BYPASS = Redis caído, se degrada a Mongo) | 200, 400, 404, 503 |
| `DELETE /equipos/{equipoId}/cache` | Redis | `DEL` de la ficha. Idempotente | 204, 400, 503 |
| `GET /equipos/{equipoId}/jugadores?posicion&pagina&tamanio` | MongoDB | Verifica que exista el equipo y lista ordenando por `numeroCamiseta` (índice `uq_jugadores_equipo_camiseta`) | 200, 400, 404, 503 |
| `GET /equipos/{equipoId}/partidos?limite` | Neo4j | Agenda: partido, rol, rival, estadio; `[..$limite]` | 200, 400, 404, 503 |
| `GET /partidos/{partidoId}?limiteEventos` | Neo4j | Partido + estadio + equipos con rol (consulta 1); eventos con involucrados (consulta 2). Partido inexistente → 404; sin eventos → `eventos: []` | 200, 400, 404, 503 |
| `GET /partidos/{partidoId}/comentarios?desde&hasta&limite&cursor` | Cassandra | Ventana obligatoria ≤ 5 min. Calcula los minutos que la cubren y consulta `minuto IN ? AND segmento IN (0,1,2,3)` (≤ 24 particiones), `ORDER BY creado_en DESC, comentario_id ASC`, `LIMIT`. Cursor de continuación | 200, 400, 503 |
| `POST /partidos/{partidoId}/comentarios` (header `Idempotency-Key`) | Redis + Neo4j + Cassandra | Ver idempotencia (sección 8). 201 al crear; 200 + `Idempotent-Replayed: true` si se repite | 200, 201, 400, 404, 409, 503 |
| `GET /partidos/{partidoId}/estadisticas?equipoId&desde&hasta&intervalo` | InfluxDB | SQL con `DATE_BIN` (intervalo 10s/30s/1m/5m), promedio de posesión, suma de tiros y máximo de pases acumulados, agrupando por intervalo y equipo. Sin `desde`/`hasta`: últimos 10 min con datos (`MAX(time)` acotado a 7 días). Máx. 720 intervalos por equipo | 200, 400, 503 |
| `POST /sesiones` `{usuarioId, rol}` | Redis | Script Lua `HSET` + `EXPIRE 1800` atómico (igual que el Hito 7). ID `SES-` + 24 hex aleatorios | 201, 400, 503 |
| `GET /sesiones/{sesionId}` | Redis | `HGETALL` + `TTL` en una transacción. Vacío → 404 `SESION_NO_VIGENTE` (Redis no distingue "venció" de "nunca existió"). No renueva el TTL | 200, 400, 404, 503 |
| `DELETE /sesiones/{sesionId}` | Redis | `DEL`. Idempotente | 204, 400, 503 |
| `GET /actas/{codigo}` | IRIS | SQL sobre `FixtureH9.Partido` y `FixtureH9.Evento` (`Arbitro->Codigo`, `Jugador->Numero`, etc.), conservando los IDs de IRIS | 200, 400, 404, 503 |
| `PUT /actas/{codigo}/estado` `{estado}` | IRIS | Si ya está en ese estado → 200 `cambio: false`, sin guardar. Si no, API nativa: `PorCodigoOpen` + `invoke("CambiarEstado")`. Error 5001 → 409 `TRANSICION_INVALIDA` sin modificar | 200, 400, 404, 409, 503 |

Todas las operaciones documentan además 500. Las rutas `/` (GUI), `/docs` y `/openapi.json` no figuran en el esquema.

## 7. Formato de respuestas y errores

- Éxito: `{"data": ..., "meta": {"requestId", "fuentes": [{fuente, operacion, resultado, ms}], "paginacion": {pagina, tamanio, total, siguienteCursor} | null, "cache": "HIT|MISS|BYPASS" | null}}`.
- Error: `{"error": {"codigo", "mensaje", "requestId", "dependencia"?, "detalles"?}}`.

| Código de error | HTTP | Cuándo |
| --- | --- | --- |
| `VALIDACION_FALLIDA` | 400 | Path, query, header o body fuera del contrato. FastAPI usaría 422, pero se remapea a 400 en el handler y en el OpenAPI |
| `RECURSO_NO_ENCONTRADO` | 404 | Equipo, partido o acta inexistente |
| `SESION_NO_VIGENTE` | 404 | Sesión inexistente, cerrada o vencida |
| `RUTA_NO_ENCONTRADA` / `METODO_NO_PERMITIDO` | 404/405 | Ruta inválida |
| `TRANSICION_INVALIDA` | 409 | `CambiarEstado` rechazó la transición |
| `CONFLICTO` | 409 | `Idempotency-Key` reutilizada con otro cuerpo, o todavía en curso |
| `DEPENDENCIA_NO_DISPONIBLE` | 503 | Base caída, timeout o credencial rechazada (incluye `dependencia`) |
| `ERROR_INTERNO` | 500 | Excepción no prevista; el traceback solo va al log |

Encabezados: `X-Request-ID` en todas las respuestas (acepta uno entrante si cumple `[A-Za-z0-9-]{8,64}`), `X-Cache` y `Idempotent-Replayed`.

## 8. Reglas importantes

**Validación** (en `schemas.py` y `services.py`):

- Patrones: `EQ-\d{3}`, `PAR-\d{3}`, `USR-\d{5}`, `SES-[0-9a-f]{24}`, código de acta `[A-Z0-9][A-Z0-9-]{2,23}`, `Idempotency-Key` `[A-Za-z0-9-]{8,64}`, cursor `\d{13}_[A-Za-z0-9-]{1,64}`.
- Enums cerrados: confederación, posición, intervalo y estado.
- Rangos: página 1-1000; tamaño, límite y eventos 1-50; agenda 1-20.
- Cuerpos con `extra=forbid`; contenido de 1 a 280 caracteres.
- Fechas ISO; sin zona horaria se toman como UTC; `hasta > desde`.
- Las pruebas unitarias verifican que una entrada inválida no llame a ningún adaptador.

**Cursor de Cassandra:**

- Formato `"<epoch ms>_<comentarioId>"` del último ítem devuelto.
- La página siguiente ejecuta primero `creado_en = ts AND comentario_id > id` (empates del mismo milisegundo) y luego `creado_en >= desde AND creado_en < ts`.
- Así no se pierden ni repiten filas, aunque la consulta con `IN + ORDER BY` obliga a desactivar la paginación del driver (`fetch_size=None`).

**Idempotencia del POST de comentarios:**

1. Huella = SHA-256 de `[partido, usuarioId, contenido]`. Clave Redis = `fixture2030:h10:idem:comentario:{partido}:{Idempotency-Key}`.
2. `SET NX EX 86400` con `{"estado": "EN_CURSO", "huella"}`. Si ya existía: misma huella y `COMPLETADO` → devuelve el original (200); otra huella o `EN_CURSO` → 409.
3. Verifica que el partido exista en Neo4j (404 si no) y escribe un `BATCH LOGGED` con las dos tablas de Cassandra. El ID es `API-<uuid>`, `creado_en` es la hora actual con precisión de ms y el segmento sale del CRC32.
4. Guarda el resultado en la clave (`COMPLETADO`).
5. Si Neo4j o Cassandra fallan, se libera la clave. Si Redis falla después de escribir, la clave queda `EN_CURSO` hasta su TTL: los reintentos reciben 409 y no se duplica. Sin Redis no se aceptan publicaciones (503).

**Otras escrituras:** los DELETE son idempotentes (204 siempre). El PUT de acta es idempotente (`cambio: false`). `POST /sesiones` **no** es idempotente: cada llamada abre una sesión nueva.

**Límites:** comentarios ≤ 5 min y ≤ 50 por página; estadísticas ≤ 720 intervalos por equipo (por ejemplo, 2 h con intervalo de 10 s); eventos de IRIS `TOP 100`.

## 9. Configuración (`.env`, ignorado por Git)

| Variable | Valor en la notebook |
| --- | --- |
| `DEP_TIMEOUT_SEGUNDOS` | 3 (timeout por operación en los 6 clientes) |
| `MONGO_HOST/PORT/DB/USER/PASSWORD` | 127.0.0.1 / 27017 / fixture2030 / admin / (valor de laboratorio del Hito 4) |
| `NEO4J_URI/DATABASE/USER/PASSWORD` | bolt://127.0.0.1:7687 / neo4j / neo4j / (valor de laboratorio del Hito 5) |
| `CASSANDRA_HOSTS/PORT/KEYSPACE` | 127.0.0.1 / 9042 / fixture2030_comentarios (sin auth) |
| `REDIS_HOST/PORT/PASSWORD/PREFIX` | 127.0.0.1 / 16379 / vacío / `fixture2030:h10` (prefijo propio, no pisa la demo del Hito 7) |
| `SESION_TTL_SEGUNDOS`, `CACHE_EQUIPO_TTL_SEGUNDOS`, `IDEMPOTENCIA_TTL_SEGUNDOS` | 1800, 300, 86400 |
| `INFLUX_URL/DB`, `INFLUX_TOKEN` o `INFLUX_TOKEN_FILE` | http://127.0.0.1:8181 / fixture2030_h8 / `../Hito 8/.local/admin.token` |
| `IRIS_HOST/PORT/NAMESPACE/USER/PASSWORD` | 127.0.0.1 / 1972 / USER / fixture_api / (aleatoria, solo en `.env`) |

- **Usuario IRIS:** `scripts/iris_crear_usuario_api.ps1` crea el rol `fixture_api_rol` (`%DB_USER:RW`, `%Native_ClassExecution:U`) y el usuario `fixture_api`, más `GRANT SELECT ON SCHEMA FixtureH9`. Envía ObjectScript por stdin a `iris session IRIS -U %SYS` dentro del contenedor del Hito 9.
- **Notebook vs. Docker:** la API corre en la notebook y usa los puertos publicados en 127.0.0.1. Si corriera en un contenedor, habría que usar `host.docker.internal` o los nombres de servicio con sus puertos internos; solo cambia el `.env`.

## 10. Consola gráfica (`web/index.html`)

HTML, CSS y JS sin librerías, con modo oscuro automático. Usa solo la API pública mediante una función `llamar()` que actualiza una barra inferior con método, estado, ms, requestId, códigos de error, chips de `meta.fuentes` y el JSON completo. Escapa todo dato con `esc()` (los comentarios son texto de usuarios).

| Vista | Qué muestra | Fuentes |
| --- | --- | --- |
| Equipos | Tabla paginada con filtro de confederación. Al hacer clic: ficha con badge de caché, "Volver a leer" e "Invalidar caché"; plantel con filtro de posición; agenda (al hacer clic en un partido va a la vista Partido) | MongoDB, Redis, Neo4j |
| Partido | Detalle y eventos. Estadísticas con gráfico SVG de posesión por equipo y totales. Comentarios por ventana con "Cargar más" (cursor) y "Últimos 5 min". Formulario para publicar con `Idempotency-Key` aleatoria y botón "Reintentar el mismo envío" | Neo4j, InfluxDB, Cassandra, Redis |
| Sesiones | Abrir, consultar (TTL restante) y cerrar; tabla de sesiones abiertas en esta consola | Redis |
| Actas | Acta con árbitro y eventos (IDs IRIS), pasos de estado y botones de transición | IRIS |

En el encabezado: chips de salud de las 6 fuentes, botón "Revisar conectividad" y enlace a Swagger.

## 11. Cómo se ejecuta

Desde `Hito 10/` en PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\fixture.ps1 todo     # levanta las 6 bases (docker compose up -d de cada hito), espera a que respondan y arranca la API
.\fixture.ps1 abrir    # en otra terminal: abre http://127.0.0.1:8000/ y /docs
```

Otros comandos: `bases`, `esperar`, `verificar`, `api`, `influx`, `iris-usuario`, `pruebas`, `unitarias`, `latencia`, `detener` (hace `stop`, nunca `down -v`) y `ayuda`.

**Primera vez en otra máquina:**

1. Levantar los Hitos 4 a 9 y cargar sus muestras con los scripts de cada hito.
2. Copiar `.env.example` a `.env` y completar las contraseñas.
3. Ejecutar `.\fixture.ps1 iris-usuario`.
4. Ejecutar `.\fixture.ps1 todo`.
5. Si el gráfico de estadísticas sale vacío, ejecutar `.\fixture.ps1 influx`.

## 12. Pruebas y evidencia

**Unitarias** (`tests/unit/test_api.py`, 16): usan la clase `Falso`, un adaptador en memoria que cuenta llamadas y simula caídas con `operacion()`. Cubren:

- Éxito con requestId y trazas, y caché MISS→HIT.
- Entrada inválida sin llamadas a las bases.
- Ventana > 5 min, 404, sesión ausente y 503 sin detalle técnico.
- Degradación BYPASS y salud con 503.
- Repetición idempotente (una sola fila) y 409 por huella distinta; falta de `Idempotency-Key`; liberación de la clave ante 404.
- Transición 409 y PUT sin cambio; ruta inexistente.
- Driver real de Redis contra un puerto cerrado (503 en ~1 s), cálculo de minutos de la ventana y OpenAPI versionado igual al generado.

**Integración** (`tests/integration/test_integracion.py`, 20): contra las bases reales.

- Paginación de Mongo (10 equipos UEFA), caché e invalidación, plantel y equipo inexistente.
- Partido y agenda en Neo4j; cursor de Cassandra (8 comentarios sin repetidos en páginas de 3); ventana vacía.
- Escritura repetida: cuenta la fila en Cassandra y la borra al final.
- Ciclo de sesión y sesión vencida (TTL 1 s).
- InfluxDB con ventana, filtro por equipo, tope de intervalos y ventana sin puntos.
- IRIS: transiciones sobre un acta temporal `H10-TEMPORAL` creada y borrada en un fixture con la API nativa; acta de muestra.
- Las 6 fuentes "caídas" (cada driver apuntando al puerto 1) → 503 en menos de 8 s.

**Evidencia** (`docs/evidencia/`, 16/10/2026):

| Archivo | Contenido |
| --- | --- |
| `01_conectividad.txt` | Las 6 bases ok y `docker ps` |
| `02_pruebas.txt` | 36 pruebas aprobadas |
| `03_recorrido_curl.txt` | 22 requests con encabezados y JSON |
| `04_dependencia_detenida.txt` | `docker compose stop redis` → sesiones 503, ficha 200 BYPASS, salud 503; `start` → 201 |
| `05_logs_correlacion.txt` | Líneas de log por requestId |
| `06_latencia.txt` | Método, entorno y resultados |

**Latencia** (200 requests secuenciales, Ryzen 5 3600, 32 GB, 1 worker): p50 de 2,6 ms (Redis HIT), 3,4 ms (IRIS), 3,5 ms (Mongo), 12,8 ms (Neo4j), 15,4 ms (Cassandra con 12 particiones) y 17,4 ms (Influx). Sin errores. No se midió concurrencia.

**Postman:** las 32 requests se verificaron con un script que las ejecutó en orden (todas con el estado esperado). Newman no se ejecutó porque requiere `npx newman` y descargar un paquete de npm.

## 13. Problemas encontrados y cómo se resolvieron

| Problema | Solución |
| --- | --- |
| `cassandra-driver` no carga en Python ≥ 3.12 (se eliminó `asyncore`) | Dependencia `pyasyncore`, que restituye el módulo |
| La DLL de `intersystems-irispython` falla con rutas muy largas | Funciona con la ruta de `Hito 10/.venv` (la falla solo ocurría con un path temporal muy largo) |
| IRIS en `/durable` no arrancaba (`chown` como root) | Procedimiento documentado en el README del Hito 9: `chown 51773:51773 /durable` como root y reinicio |
| `_SYSTEM` de IRIS exige cambiar la contraseña | Usuario propio `fixture_api`; además hizo falta el recurso `%Native_ClassExecution` para invocar métodos |
| El script de usuario IRIS fallaba con `<SYNTAX>` | PowerShell 5.1 agrega un BOM al stdin. Se resolvió con `$OutputEncoding = UTF8Encoding($false)` |
| Fila del cursor IRIS ilegible al reutilizar el cursor | Convertir a `tuple()` antes de la segunda consulta |
| Redis caído demoraba ~15 s (reintentos por defecto de redis-py) | `retry=Retry(NoBackoff(), 0)`; ahora ~1-2 s |
| Neo4j del Hito 5 vacío y `cypher.sh` con CRLF (`set: Illegal option -`; el healthcheck figura `unhealthy`) | Se cargaron los `.cypher` con `cypher-shell -f` directo. El healthcheck sigue `unhealthy` pero la base funciona. No se tocó el Hito 5 |
| Git Bash convertía `/workspace/...` en rutas de Windows | `MSYS_NO_PATHCONV=1` |
| Muestra de InfluxDB vencida por la retención de 7 días; no se pudo mover `Hito 8/datos` (permiso denegado) | `scripts/cargar_muestra_influx.py` agrega 30 min recientes (1.440 puntos, paso de 5 s) reutilizando `dimensiones()` y `medidas()` del Hito 8 |
| Acentos rotos en los `.ps1` con PowerShell 5.1 | Archivos guardados en UTF-8 con BOM |
| Avisos de cassandra-driver (protocolo, balanceo, `USE keyspace`) | `protocol_version=5`, `DCAwareRoundRobinPolicy("datacenter1")` y tablas calificadas `keyspace.tabla` |

## 14. Estado de los datos en la notebook

- **MongoDB**: muestra del Hito 4 cargada (64 equipos y 1.536 jugadores).
- **Neo4j**: muestra del Hito 5 cargada.
- **Cassandra**: 12 comentarios de muestra, más un comentario de evidencia "Evidencia del Hito 10" (usuario `USR-00003`) en `PAR-064`.
- **IRIS**: muestra del Hito 9 (`Ejecutar()` → `DEMO OK`), `PAR-001` en `PENDIENTE`, y el rol y usuario de la API.
- **Redis**: claves `fixture2030:h10:*` (sesiones, cachés y claves de idempotencia, todas con TTL).
- **InfluxDB**: muestra original vencida, más 1.440 puntos recientes de PAR-001 y PAR-002 del 16/10/2026 (vencen en 7 días; se regeneran con `.\fixture.ps1 influx`).

## 15. Limitaciones y pendientes

- No hay autenticación de consumidores ni TLS; la API escucha solo en 127.0.0.1. Hay un nodo por motor y un worker de uvicorn, y la conexión a IRIS está serializada.
- Las transiciones válidas sobre `PAR-001` desde la GUI son **permanentes** e irreversibles. El `Verificar()` del Hito 9 espera `PENDIENTE`.
- La colección Postman publica un comentario real en `PAR-064` cada vez que se ejecuta.
- **Pendiente para el usuario:**
  - Hacer el commit y push del Hito 10 (no se hizo commit).
  - Decidir qué hacer con `Hito 10a/` (copia staged del Hito 9 con el PDF).
  - Borrar `C:\t10`, un venv temporal de prueba que no se pudo eliminar automáticamente.
  - Opcionalmente, ejecutar `npx newman run postman\fixture2030_collection.json`.
