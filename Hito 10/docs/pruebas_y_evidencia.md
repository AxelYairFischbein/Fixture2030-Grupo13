# Pruebas, evidencia y rendimiento

## Método

| Herramienta | Qué cubre | Cómo |
| --- | --- | --- |
| `pytest` unitarias (`tests/unit`, 16) | Contrato, validación previa, errores, idempotencia, degradación, OpenAPI | Adaptadores en memoria; más un cliente Redis real contra un puerto cerrado. No requiere bases |
| `pytest` integración (`tests/integration`, 20) | Cada endpoint contra su fuente real, vacíos válidos, límites, escritura repetida, sesión vencida, transiciones IRIS, las seis fuentes inaccesibles | `TestClient` con los adaptadores reales y `.env` |
| Postman (32 requests) | Rutas principales y errores, encadenando cursor, sesión y comentario | Colección v2.1 con aserciones de estado y encabezados |
| cURL | Recorrido manual reproducible | [evidencia/03_recorrido_curl.txt](evidencia/03_recorrido_curl.txt) |
| Contenedor detenido | Dependencia caída de verdad | `docker compose stop redis` / `start` |

Ejecución: `scripts/ejecutar_pruebas.ps1` (exporta OpenAPI, verifica conectividad y corre todo) o `-SoloUnitarias`.

## Cobertura de escenarios exigidos

| Escenario | Prueba o evidencia |
| --- | --- |
| Request válida por módulo | `test_mongodb_*`, `test_neo4j_*`, `test_cassandra_*`, `test_redis_*`, `test_influx_*`, `test_iris_*` |
| Parámetro inválido | `test_entrada_invalida_no_consulta_la_fuente`, ventana > 5 min, intervalos > 720, estado fuera del enum (Postman) |
| Recurso inexistente | `EQ-999`, `PAR-999`, acta `NO-EXISTE` |
| Respuesta vacía válida | `test_cassandra_ventana_vacia_valida`, `test_influx_ventana_sin_puntos` |
| Sesión ausente o expirada | `test_sesion_ausente`, `test_redis_sesion_vencida` (TTL 1 s), sesión cerrada |
| Dependencia detenida | `test_dependencia_detenida_responde_503_acotado[6 fuentes]`, contenedor Redis detenido |
| Escritura repetida | `test_cassandra_escritura_repetida_no_duplica` (cuenta la fila en Cassandra), `test_escritura_repetida_no_duplica` |
| Límites, paginación, ventanas | Listado paginado (total 10 UEFA), cursor de comentarios (8 sin repetidos), tope de intervalos |
| Documentación = respuesta real | `test_openapi_versionado_coincide_con_la_aplicacion` + códigos verificados por Postman |
| Conflicto de negocio | Transición prohibida 409 sin cambio; `Idempotency-Key` con otro cuerpo 409 |

## Evidencia registrada (16/10/2026, UTC)

| Archivo | Contenido |
| --- | --- |
| [01_conectividad.txt](evidencia/01_conectividad.txt) | Las seis fuentes `ok` con su latencia y los contenedores activos |
| [02_pruebas.txt](evidencia/02_pruebas.txt) | `ejecutar_pruebas.ps1`: **36 aprobadas, 0 fallidas** |
| [03_recorrido_curl.txt](evidencia/03_recorrido_curl.txt) | 22 requests con encabezados y cuerpos: éxitos, 400, 404, 409, MISS/HIT, repetición idempotente |
| [04_dependencia_detenida.txt](evidencia/04_dependencia_detenida.txt) | Redis detenido: sesiones 503, ficha 200 `BYPASS`, salud 503 con detalle; Redis iniciado: 201 |
| [05_logs_correlacion.txt](evidencia/05_logs_correlacion.txt) | Líneas del log de la API para los `requestId` de la evidencia 04 |
| [06_latencia.txt](evidencia/06_latencia.txt) | Medición de latencia con método y entorno |

Las respuestas de la evidencia se obtuvieron con los comandos que figuran en cada archivo, contra la API iniciada con `scripts/iniciar_api.ps1`. La consola web se verificó en Chrome con las cuatro vistas (equipos, partido con gráfico, sesiones, actas).

Además, la colección Postman se validó ejecutando sus 32 requests en orden contra la API: todas devolvieron el estado esperado.

## Rendimiento básico

Método: `scripts/medir_latencia.py`, 200 requests secuenciales por ruta tras 10 de calentamiento, un cliente en la misma notebook, tiempo de ida y vuelta HTTP. Entorno: Windows 10, AMD Ryzen 5 3600, 32 GB, Python 3.14, uvicorn con un worker, seis contenedores en Docker Desktop. Volumen: muestras de laboratorio.

| Ruta | p50 ms | p95 ms | máx ms | Errores |
| --- | ---: | ---: | ---: | ---: |
| MongoDB `GET /equipos?tamanio=16` | 3,51 | 5,69 | 6,46 | 0 |
| Redis `GET /equipos/EQ-001` (HIT) | 2,62 | 4,24 | 4,96 | 0 |
| Neo4j `GET /partidos/PAR-001` | 12,83 | 16,34 | 20,18 | 0 |
| Cassandra comentarios 3 min (12 particiones) | 15,42 | 16,65 | 18,22 | 0 |
| InfluxDB estadísticas por minuto | 17,43 | 24,23 | 27,75 | 0 |
| IRIS `GET /actas/PAR-001` | 3,37 | 4,38 | 5,33 | 0 |

Interpretación acotada: la ficha en caché es la lectura más rápida; Neo4j, Cassandra e InfluxDB cuestan más por resolver dos consultas, 12 particiones o una agregación. La primera conexión a Cassandra tarda ~1,4 s (descubrimiento del clúster) y no está incluida porque hay calentamiento. **No** se midió concurrencia, carga sostenida ni volumen productivo; las cifras no permiten afirmar capacidad para millones de usuarios.

## Coherencia con el TPO

- Mismos identificadores en todas las fuentes: `EQ-001`, `JUG-0001`, `PAR-001`, `EST-01`, `USR-00001`, `ARB-001`.
- Se reutilizan índices (Hito 4), Cypher de los patrones Q01/Q06/Q07 (Hito 5), la tabla y la regla de segmento (Hito 6), el hash de sesión con Lua y los TTL (Hito 7), la tabla `estadisticas_equipo` y su agregación por intervalo (Hito 8) y el método `CambiarEstado()` (Hito 9).
- Ningún hito anterior fue modificado. Se documentan dos hallazgos del entorno: el healthcheck CRLF de Neo4j y el vencimiento de la muestra de InfluxDB por su retención de 7 días.
