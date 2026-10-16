# Hito 10 · Contratos y errores

Grupo 13 · Ingeniería de Datos II · Fixture Mundial 2030

Cubre los apartados *Mapa de endpoints*, *Contratos*, *Validación*, *Errores* e *Idempotencia* de la sección 8 del enunciado. La fuente de verdad del comportamiento es [`casos_de_uso.md`](casos_de_uso.md); este documento resume lo que implementa `Hito 10/app/` y lo que publica el contrato [`openapi/openapi.yaml`](../openapi/openapi.yaml).

## 1. Contrato OpenAPI

| Elemento | Dónde |
|---|---|
| Contrato versionado | `openapi/openapi.yaml` (OpenAPI 3.1, título *Fixture 2030 · API integrada*, versión `0.8.0`). |
| Exploración interactiva | Swagger UI en `http://127.0.0.1:8000/docs` y ReDoc en `/redoc` con la API levantada (`scripts/iniciar_api.ps1`). |
| Generación | `scripts/exportar_openapi.ps1` → `scripts/exportar_openapi.py` → `app.openapi.contrato_yaml()`. Usa configuración ficticia: no lee `.env` ni se conecta a ninguna base. |
| Control de coherencia (RNF2) | `tests/test_openapi.py` compara el archivo versionado con `app.openapi()` y falla ante cualquier diferencia; `exportar_openapi.ps1 -Verificar` hace lo mismo sin escribir. El mismo archivo de pruebas verifica que ninguna operación declare `422`, que todas tengan tag, `summary` y `500`, que cada error declarado tenga ejemplos con códigos del contrato y que estén los 20 CU. Evidencia: `docs/evidencia/api_openapi_verificacion.txt`. |
| Ajustes al OpenAPI de FastAPI | `app/openapi.py` quita el `422` que FastAPI agrega por defecto (la API nunca lo devuelve: lo convierte en `400 VALIDACION`) y agrega las etiquetas por módulo. |
| Contenido | Tags por módulo (`salud`, `equipos`, `jugadores`, `partidos`, `comentarios`, `sesiones`, `cache`, `estadisticas`, `actas`), `summary` con el CU, parámetros con patrón/enum/límites, cuerpos (`NuevoComentario`, `Moderacion`, `SolicitudTransicion`), schemas de respuesta con ejemplos, el schema de error `RespuestaError` y todas las respuestas posibles de cada operación. |
| Autenticación | No se declara un `securityScheme`: la sesión es el encabezado `X-Session-Id`, documentado como parámetro de cada operación que lo usa. |
| Servidor | El contrato **no declara `servers`**; Swagger UI usa el origen desde el que se abre. La URL local por defecto es `http://127.0.0.1:8000` (ver [`conectividad_y_configuracion.md`](conectividad_y_configuracion.md)). |

## 2. Mapa de endpoints

Prefijo común: `/api/v1`. Todas las respuestas llevan `X-Request-Id`. “Sesión” = encabezado `X-Session-Id` validado en Redis.

| Método | Ruta | CU | Fuente(s) | Operación | Sesión / rol | Éxito |
|---|---|---|---|---|---|---|
| GET | `/salud` | — | las seis + catálogo | Lectura (ping) | — | 200 (`ok` o `degradado`) |
| GET | `/equipos/{equipoId}` | CU-01 | Redis + MongoDB | Lectura cache-aside | — | 200 + `X-Cache` |
| GET | `/equipos?confederacion=…` | CU-02 | MongoDB | Lectura paginada | — | 200 |
| GET | `/equipos/{equipoId}/jugadores` | CU-03 | MongoDB | Lectura paginada | — | 200 |
| GET | `/jugadores/{jugadorId}` | CU-04 | MongoDB | Lectura | — | 200 |
| GET | `/equipos/{equipoId}/partidos` | CU-05 | Neo4j | Recorrido | — | 200 |
| GET | `/partidos/{partidoId}/eventos` | CU-06 | Neo4j | Recorrido | — | 200 |
| GET | `/partidos?desde=…&hasta=…` | CU-07 | Neo4j | Lectura acotada | — | 200 |
| GET | `/partidos/{partidoId}/comentarios` | CU-08 | catálogo + Cassandra (+ Redis si hay sesión) | Lectura por partición | opcional; `moderador` ve todos los estados | 200 |
| POST | `/partidos/{partidoId}/comentarios` | CU-09 | Redis + catálogo + Cassandra | Creación idempotente | obligatoria | 201 |
| GET | `/usuarios/{usuarioId}/comentarios?dia=…` | CU-10 | Redis + Cassandra | Lectura por partición | autor o `moderador` | 200 |
| PATCH | `/partidos/{partidoId}/comentarios/{comentarioId}` | CU-20 | Redis + catálogo + Cassandra | Actualización validada | `moderador` | 200 |
| GET | `/sesiones/actual` | CU-11 | Redis | Lectura (no renueva) | obligatoria | 200 |
| POST | `/sesiones/actual/actividad` | CU-12 | Redis | Actualización (TTL 1800 s) | obligatoria | 200 |
| DELETE | `/sesiones/actual` | CU-13 | Redis | Invalidación | obligatoria | 204 |
| DELETE | `/cache/equipos/{equipoId}` | CU-14 | Redis | Invalidación | `operador` | 204 |
| GET | `/partidos/{partidoId}/equipos/{equipoId}/estadisticas/recientes` | CU-15 | catálogo + InfluxDB | Lectura por ventana | — | 200 |
| GET | `/partidos/{partidoId}/estadisticas/comparacion` | CU-16 | catálogo + InfluxDB | Lectura agregada | — | 200 |
| GET | `/partidos/{partidoId}/estadisticas/evolucion` | CU-17 | catálogo + InfluxDB | Lectura agregada | — | 200 |
| GET | `/partidos/{partidoId}/acta` | CU-18 | IRIS | Lectura de objeto | — | 200 |
| POST | `/partidos/{partidoId}/acta/transiciones` | CU-19 | Redis + IRIS | Actualización validada | `operador` | 200 |

No existe ningún endpoint que reciba nombres de base, colección, tabla o una consulta: cada ruta ejecuta una consulta fija del adaptador correspondiente.

### 2.1 Respuestas de error declaradas por operación

Tomadas de `openapi/openapi.yaml` (además de 404 `RUTA_NO_ENCONTRADA` y 405 `METODO_NO_PERMITIDO`, comunes a cualquier ruta).

| CU | 400 | 401 | 403 | 404 | 409 | 500 | 503 | 504 |
|---|---|---|---|---|---|---|---|---|
| Salud | | | | | | ✓ | | |
| CU-01, CU-03, CU-04, CU-05, CU-06 | ✓ | | | ✓ | | ✓ | ✓ | ✓ |
| CU-02, CU-07 | ✓ | | | | | ✓ | ✓ | ✓ |
| CU-08 | ✓ | ✓ | | ✓ | | ✓ | ✓ | ✓ |
| CU-09 | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ |
| CU-10 | ✓ | ✓ | ✓ | | | ✓ | ✓ | ✓ |
| CU-20 | ✓ | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ |
| CU-11, CU-12, CU-13 | ✓ | ✓ | | | | ✓ | ✓ | ✓ |
| CU-14 | ✓ | ✓ | ✓ | | | ✓ | ✓ | ✓ |
| CU-15, CU-16, CU-17, CU-18 | ✓ | | | ✓ | | ✓ | ✓ | ✓ |
| CU-19 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## 3. Validación (RF10, RNF3)

Toda la validación de formato ocurre **antes** de llamar al servicio: las rutas declaran los parámetros con tipos de Pydantic (`Path`, `Query`, `Header`, cuerpos con `extra="forbid"`). Las reglas entre parámetros (orden, tamaño de ventana, modos excluyentes) las valida el servicio en un método `preparar_*` antes de usar el adaptador. En la evidencia, una request inválida no genera ninguna línea `dependencia=…` en el log (`api_correlacion_request_id.txt`).

| Entrada | Regla | Dónde |
|---|---|---|
| `equipoId` | `^EQ-\d{3}$` | `app/schemas/equipos.py` |
| `jugadorId` | `^JUG-\d{4}$` | `app/schemas/jugadores.py` |
| `partidoId`, `estadioId` | `^PAR-\d{3}$`, `^EST-\d{2}$` | `app/schemas/partidos.py` |
| `usuarioId`, `comentarioId` | `^USR-\d{5}$`, `^[A-Za-z0-9-]{1,64}$` | `app/schemas/comentarios.py` |
| `X-Session-Id` | `^[A-Za-z0-9-]{8,64}$`; ausente → 401 `SESION_REQUERIDA` sin consultar Redis | `app/schemas/sesiones.py`, `app/services/sesiones.py` |
| `Idempotency-Key` | UUID obligatorio en CU-09 | `app/routes/comentarios.py` |
| Enums | `confederacion` (AFC, CAF, CONCACAF, CONMEBOL, OFC, UEFA, obligatoria), `posicion`, `resolucion` (`1m`, `5m`), `estado` de moderación (`visible`, `oculto`), `nuevoEstado` (`EN_JUEGO`, `FINALIZADO`) | schemas por módulo |
| Fechas | ISO-8601 con zona (`Z` u offset) → normalizadas a UTC; sin zona → 400. `dia` = `YYYY-MM-DD`. | `app/schemas/partidos.py` (`InstanteUTC`) |
| Intervalos | `desde < hasta`; CU-07 ≤ 7 días; CU-08 ≤ 5 min (y `minuto` excluyente con `desde`/`hasta`); CU-16 ≤ 5 min; CU-17 ≤ 2 h; CU-15 ventana fija de 60 s hasta `hasta` | `app/services/partidos.py`, `comentarios.py`, `estadisticas.py` |
| Límites (RNF12) | CU-02 `limite` 1–50; CU-03 1–24; CU-05 1–50; CU-06 1–200 (eventos); CU-07 1–64; CU-08 1–20 (minuto o últimos 60 s) / 1–50 (ventana); CU-10 1–20; CU-15 1–60; `pagina ≥ 1`. CU-17 devuelve como máximo 120 intervalos × 2 equipos; CU-18 como máximo 500 eventos. | rutas y adaptadores |
| Cursores | `antesDe` = `creadoEn|comentarioId` (CU-08, CU-10); respuesta con `siguienteCursor` o `null` | `app/services/comentarios.py` |
| Cuerpos | JSON con `extra="forbid"`: CU-09 `{contenido: 1–280}`, CU-20 `{creadoEn, estado}`, CU-19 `{nuevoEstado}` | `app/schemas/comentarios.py`, `actas.py` |

## 4. Formato de error único (RF11, RF12, RNF4)

Todo error, de cualquier origen, sale de `app/manejadores.py` con esta forma (`app/schemas/errores.py`):

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

- `requestId` es el mismo valor que el encabezado `X-Request-Id` y que el `request_id=` de las líneas de log.
- `detalles` lista campo y problema en español; nunca repite el valor recibido en los errores de validación.
- Nunca incluye URIs de conexión, credenciales, consultas Cypher/CQL/SQL, stack traces ni el mensaje crudo del driver: los adaptadores lanzan excepciones de `app/errors.py` con mensajes fijos y dejan el tipo de la excepción original solo en el log.

### 4.1 De dónde sale cada código

| Origen | Manejador | Respuesta |
|---|---|---|
| `ErrorDominio` y subclases (`app/errors.py`) | `_manejar_dominio` | `http_status` y `codigo` de la clase; para 503/504 registra `dependencia=… resultado=…` |
| `RequestValidationError` de FastAPI (parámetro, encabezado o cuerpo inválido) | `_manejar_validacion` | `400 VALIDACION` con un detalle por campo |
| `HTTPException` de Starlette (ruta o método inexistente) | `_manejar_http` | `404 RUTA_NO_ENCONTRADA` / `405 METODO_NO_PERMITIDO` con `Allow` |
| Cualquier otra excepción | `_manejar_inesperado` | `500 ERROR_INTERNO`; el stack trace queda en el log con el `request_id` |

### 4.2 Códigos

| HTTP | Código | Excepción | Cuándo |
|---|---|---|---|
| 400 | `VALIDACION` | `RequestValidationError`, `ValidacionInvalida` | Formato, enum, límite, fecha sin zona, intervalo invertido o excedido, campos extra. Antes de consultar. |
| 401 | `SESION_REQUERIDA` | `SesionRequerida` | Falta `X-Session-Id` en una operación protegida. |
| 401 | `SESION_NO_VIGENTE` | `SesionNoVigente` | Sesión inexistente, vencida, sin TTL o con `estado ≠ activa`. |
| 403 | `ROL_NO_AUTORIZADO` | `RolNoAutorizado` | Sesión vigente sin el rol necesario (o, en CU-10, que no es del autor). |
| 404 | `EQUIPO_NO_ENCONTRADO`, `JUGADOR_NO_ENCONTRADO`, `PARTIDO_NO_ENCONTRADO`, `ACTA_NO_ENCONTRADA`, `COMENTARIO_NO_ENCONTRADO`, `EQUIPO_NO_PARTICIPA` | `NoEncontrado(codigo)` | El recurso principal de la ruta no existe. |
| 404 | `RUTA_NO_ENCONTRADA` | `HTTPException` | Ruta inexistente. |
| 405 | `METODO_NO_PERMITIDO` | `HTTPException` | Método no admitido; encabezado `Allow`. |
| 409 | `TRANSICION_NO_PERMITIDA` | `Conflicto(codigo)` | CU-19: el estado actual no admite la transición (el estado actual va en `detalles`). |
| 409 | `IDEMPOTENCY_KEY_REUTILIZADA` | `Conflicto(codigo)` | CU-09: misma clave con otro contenido, partido o autor. |
| 503 | `DEPENDENCIA_NO_DISPONIBLE` | `DependenciaNoDisponible` | La fuente rechaza la conexión o no hay nodos; catálogo de partidos nunca cargado. |
| 504 | `DEPENDENCIA_TIMEOUT` | `DependenciaTimeout` | La fuente no respondió a tiempo; en escrituras el resultado es incierto; bloqueo de IRIS no obtenido en 2 s. |
| 500 | `ERROR_INTERNO` | `ErrorDominio` / no prevista | Error inesperado o de configuración (credencial rechazada, token inválido, envoltorio IRIS sin cargar). |

### 4.3 Ausencia, vacío válido y dependencia caída

Son tres respuestas distintas y nunca se mezclan (RNF9, §5.11 y §7 del enunciado):

| Situación | Ejemplo | Respuesta |
|---|---|---|
| Recurso principal inexistente | `GET /equipos/EQ-999/jugadores` | `404 EQUIPO_NO_ENCONTRADO` (se consulta primero `equipos`). |
| Consulta válida sin resultados | `GET /partidos?…&estadioId=EST-99`, partido sin comentarios en el minuto, `PAR-003` sin puntos en InfluxDB | `200` con `items: []` / `equipos: []`. |
| Dependencia caída o lenta | Cualquier fuente detenida | `503` o `504`, nunca `200 []`. |
| Degradación documentada | CU-01 con Redis caído | `200` desde MongoDB con `X-Cache: BYPASS` (única respuesta degradada; `casos_de_uso.md` CU-01). |
| Partido de comentarios/estadísticas | `PAR-999` | `404` validado contra el catálogo en memoria, sin consultar Cassandra ni InfluxDB; `503` si el catálogo nunca cargó. |

## 5. Lectura, escritura e idempotencia (RF19, RNF14)

| Tipo | Endpoints | Garantía ante repetición | Cómo se logra |
|---|---|---|---|
| Lectura sin efectos | CU-02 a CU-08, CU-10, CU-11, CU-15 a CU-18, salud | Repetir no cambia datos. CU-11 **no** renueva el TTL. | Solo `find`, `MATCH`, `SELECT`, `HGETALL`/`TTL`, SQL de lectura. |
| Lectura con efecto interno | CU-01 | Puede repoblar la caché (`SET EX 300`); no cambia datos de negocio. | Cache-aside. |
| Lectura con sesión | CU-08 con sesión, CU-10 | Renuevan la sesión del usuario (actividad), salvo un 403, que no es actividad. | Script Lua de renovación. |
| Creación idempotente | CU-09 | Misma `Idempotency-Key` + mismo contenido → mismo `comentarioId` y `creadoEn`, sin fila nueva. Misma clave + otro contenido → `409`. Sin clave → `400`. Un `404`/`503` previo no consume la clave. | `comentario_id` = la clave en minúsculas; registro `idem:comentario:<clave>` en Redis con `SET NX EX 86400` y huella SHA-256 de partido, autor y contenido + `creado_en`; en el reintento se lee la fila por clave primaria completa y, si existe, se devuelve **sin reescribirla** (no deshace una moderación); si no existe, se escribe el batch registrado, que completa una escritura pendiente. |
| Actualización absoluta | CU-20, CU-19 | Repetir con el mismo estado → `200 cambio: false` sin escribir. | CU-20 lee la fila por clave completa (si no existe → `404` sin escribir: un `UPDATE` CQL crearía la fila) y actualiza las dos tablas en un batch registrado. CU-19 compara el estado actual antes de llamar a `CambiarEstado()`; el bloqueo de IRIS serializa a dos operadores (el segundo recibe `409`). |
| Actualización de TTL | CU-12 | Repetir vuelve a fijar 1800 s. No recrea una sesión cerrada (`401`). | Script Lua con comprobación de existencia. |
| Invalidación | CU-13, CU-14 | `204` aunque la clave ya no exista; con Redis caído `503`, nunca `204`. | `DEL`. |
| Timeout en escritura | CU-09, CU-19, CU-20 | `504` = resultado incierto: reintentar la misma request es seguro por lo anterior. | — |

Evidencia: CU-09 y CU-20 en `docs/evidencia/cassandra_lista_de_control.txt`; CU-19 en `iris_lista_de_control.txt`; CU-12, CU-13 y CU-14 en `redis_lista_de_control.txt`.
