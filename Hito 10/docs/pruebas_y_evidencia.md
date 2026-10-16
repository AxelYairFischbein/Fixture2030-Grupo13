# Hito 10 · Pruebas y evidencia

Grupo 13 · Ingeniería de Datos II · Fixture Mundial 2030

Cubre los apartados *Pruebas* y *Rendimiento básico* de la sección 8 y la sección 5.12 del enunciado (RF15, RF17, RNF18), y cierra con la **matriz de trazabilidad** RF1–RF20 / RNF1–RNF18. Todo lo que se informa acá sale de corridas reales del 2026-10-16 en la notebook del equipo; los archivos citados están en [`evidencia/`](evidencia/).

## 1. Estrategia

| Nivel | Dónde | Qué usa | Cuándo corre |
|---|---|---|---|
| Unitarias | `tests/test_*.py` (21 archivos, 278 funciones, 426 casos con parámetros) | `fastapi.testclient` + adaptadores falsos de `tests/falsos.py` que imitan el contrato de cada adaptador real (incluidas sus fallas: `falla = DependenciaNoDisponible(...)`). Los adaptadores se reemplazan con `app.dependency_overrides`. Las pruebas `test_<fuente>_adaptador.py` prueban la traducción de excepciones de cada driver con clientes simulados. | Sin Docker: `pytest -m "not integration"`. |
| Integración | `tests/integracion/test_*.py` (6 archivos, 57 pruebas, `@pytest.mark.integration`) | La API real (`create_app` con `Hito 10/.env`) contra los contenedores de los Hitos 4–9, con los resultados esperados de cada ficha de `casos_de_uso.md`. Las sesiones se crean con IDs aleatorios y se borran al terminar; CU-19 usa un acta temporal `PAR-9xx` que se borra siempre. Si un contenedor o su muestra no está, la prueba se informa como omitida (*skipped*) con el motivo. | `pytest -m integration`. |
| Contrato | `tests/test_openapi.py`, `tests/test_coleccion_postman.py` | Compara `openapi/openapi.yaml` con `app.openapi()` y la colección de Postman con las rutas reales. | Con las unitarias. |
| Colección de Postman | `postman/fixture2030_collection.json` (23 carpetas, 125 requests) | Una request exitosa y sus escenarios de error por CU, con tests de Postman sobre código HTTP y estructura del cuerpo. | Runner de Postman o `newman` vía `scripts/ejecutar_pruebas.ps1`. |
| Evidencia por fuente | `scripts/evidencia_<fuente>.ps1 -ConDetencion` | La API levantada con `uvicorn` y `curl.exe -i` recorriendo la lista de control de cada fase; con `-ConDetencion` detiene el contenedor (`docker compose stop`), prueba 503/504 y lo vuelve a levantar. | A demanda. |
| Evidencia transversal | `scripts/evidencia_api.ps1`, `scripts/medir_latencia.ps1` | Unitarias, verificación del OpenAPI, correlación por `X-Request-Id`, revisión de secretos y latencia. | A demanda. |

## 2. Resultados de la corrida del 2026-10-16

Entorno: Windows 11 Pro, Python 3.13.4, pytest 9.1.1, Docker Desktop con los seis contenedores arriba y sus muestras cargadas.

| Prueba | Resultado | Evidencia |
|---|---|---|
| Unitarias (`pytest -m "not integration"`) | **426 passed** (≈ 90 s). Ver la sección 6 sobre un cuelgue intermitente. | `api_pytest_unitarias.txt` |
| Integración completa (`pytest -m integration`) | **57 passed**, 0 skipped, 0 failed (31 s). | `mongo_pytest_integracion.txt` (el script de MongoDB corre la suite completa) |
| Integración por fuente | Neo4j 10, Redis 9, Cassandra 8, InfluxDB 12, IRIS 10 passed. | `<fuente>_pytest_integracion.txt` |
| OpenAPI versionado = `app.openapi()` | Coincide. | `api_openapi_verificacion.txt` |
| Listas de control con `curl.exe` | Todas las respuestas con el código esperado, incluidas las detenciones de los seis contenedores. | `<fuente>_lista_de_control.txt` |
| Colección con `newman` | **No ejecutada**: `newman` no está instalado en la notebook. La colección se validó estructuralmente (`test_coleccion_postman.py`) y sus requests están cubiertas por las listas de control, pero no se corrió el Runner. | `api_pytest_unitarias.txt` (al final) |
| Correlación por request id | Cada request por fuente aparece en el log con su `request_id` en las líneas de acceso y de adaptador; la entrada inválida no tiene línea de adaptador; el ID de sesión no aparece en el log. | `api_correlacion_request_id.txt` |
| Secretos | 0 apariciones de las contraseñas reales, del token de InfluxDB y de las sesiones vigentes en los archivos versionables. | `api_revision_secretos.txt` |

## 3. Escenarios de la sección 5.12

| Escenario exigido | Pruebas automáticas | Evidencia con la API real |
|---|---|---|
| Request válida por módulo | `test_equipos.py`, `test_jugadores.py`, `test_partidos.py`, `test_comentarios.py`, `test_sesiones.py`, `test_estadisticas.py`, `test_actas.py`; integración de las seis fuentes (EQ-002 = 24 jugadores, PAR-001 = 2 eventos, Q1/Q2 de `consultas.cql`, PAR-001 = 300 muestras, acta PENDIENTE). | Primeras entradas de cada `<fuente>_lista_de_control.txt`. |
| Parámetro inválido | `test_validacion.py`, `test_errores.py`, `test_*` con `_es_400`, `test_cu16_ventana_invalida_es_400_sin_consultar`, `test_cu14_equipo_invalido_sin_sesion_tambien_es_400`. | `EQ-1`, `PAR-1`, confederación fuera del enum, fecha sin zona, ventana de 6 min / 3 h, intervalo invertido, `nuevoEstado=PENDIENTE`, `resolucion=10m`. |
| Recurso inexistente | `_es_404` en cada módulo; `EQUIPO_NO_PARTICIPA` y `COMENTARIO_NO_ENCONTRADO` en comentarios y estadísticas. | `EQ-999`, `JUG-9999`, `PAR-999`, `PAR-002` sin acta, `creadoEn` equivocado en CU-20. |
| Respuesta vacía válida | `test_listado_sin_coincidencias_es_200_vacio`, `test_plantel_vacio_de_equipo_existente_es_200`, `test_estadio_inexistente_es_vacio_valido`, `test_cu08_minuto_sin_comentarios_es_200_vacio`, `test_cu16_partido_sin_puntos_es_200_vacio`. | `estadioId=EST-99`, `PAR-003` sin puntos, CU-15 sin puntos. |
| Sesión ausente o expirada | `test_sesiones.py` (ausente, inexistente, vencida, sin TTL, inactiva, cerrada), `test_cu09_sesion_vencida_es_401`, `test_sesion_requerida_rechaza_sesion_vencida`; integración Redis con TTL corto. | CU-11/12 en `redis_lista_de_control.txt`, CU-09 sin sesión, CU-19 sin sesión. |
| Dependencia detenida o inaccesible | Un test por fuente con el falso en falla (`*_caido*`, `*_timeout*`, `test_dependencia_caida`); `test_api_arranca_con_neo4j_inaccesible` (integración, puerto cerrado). | Bloque *detenido* de cada `<fuente>_lista_de_control.txt`: 503 (o `BYPASS` en CU-01 con Redis caído) y recuperación al levantar. |
| Escritura repetida | `test_cu09_reintento_con_la_misma_clave_no_duplica`, `test_cu09_reintento_no_deshace_una_moderacion`, CU-13/14 repetidos, CU-19/20 con `cambio: false`. | CU-09 reintento y 409 en `cassandra_lista_de_control.txt`; CU-19 en `iris_lista_de_control.txt`. |
| Límites, paginación, ventanas | `test_limite_fuera_de_rango`, `test_plantel_paginado_y_filtrado`, `test_cu08_cursor_antes_de`, `test_limite_global_y_cursor_con_empate_en_el_mismo_milisegundo`, `test_cu17_ventana_de_dos_horas_es_valida`, `test_eventos_limite_cuenta_eventos`. | `limite=5&pagina=2` (CU-03), `limite=3` con `siguienteCursor` (CU-08), `limite=1` (CU-06), bins de 5 min (CU-17). |
| Documentación y respuesta compatibles | `test_openapi.py` (5 pruebas), `test_coleccion_postman.py`. | `api_openapi_verificacion.txt`. |

## 4. Índice de la evidencia

Cada archivo empieza con la fecha UTC de generación y cómo se obtuvo. Las respuestas son la salida cruda de `curl.exe -i` (encabezados + cuerpo + `tiempo_total_s`). Los IDs de sesión aparecen enmascarados (`SES-PRUEBA-3f9a…`).

| Archivo | Generado por | Contenido |
|---|---|---|
| `mongo_pytest_integracion.txt`, `mongo_lista_de_control.txt` | `evidencia_mongo.ps1 -ConDetencion` | CU-01 a CU-04; MongoDB detenido: CU-01 con copia en Redis → 200 `HIT`, sin copia → 503; CU-03 → 503. |
| `redis_pytest_integracion.txt`, `redis_lista_de_control.txt` | `evidencia_redis.ps1 -ConDetencion` | CU-01 MISS/HIT/BYPASS, CU-11 a CU-14; Redis detenido → 503 (no 401) y `BYPASS`. |
| `neo4j_pytest_integracion.txt`, `neo4j_lista_de_control.txt` | `evidencia_neo4j.ps1 -ConDetencion` | CU-05 a CU-07, catálogo con 64 partidos, ausencia de `estado`; Neo4j detenido → 503 y CU-08 sigue con el catálogo cargado. |
| `cassandra_pytest_integracion.txt`, `cassandra_lista_de_control.txt` | `evidencia_cassandra.ps1 -ConDetencion` | CU-08, CU-09 (idempotencia y 409), CU-10, CU-20; Cassandra detenida → 503. El comentario publicado se borra al final. |
| `influx_pytest_integracion.txt`, `influx_lista_de_control.txt` | `evidencia_influx.ps1 -ConDetencion` | CU-15 a CU-17 sobre la ventana de la carga de muestra; InfluxDB detenido → 503; token ausente de la evidencia. |
| `iris_pytest_integracion.txt`, `iris_lista_de_control.txt` | `evidencia_iris.ps1 -ConDetencion` | CU-18, CU-19 sobre un acta temporal (`EN_JUEGO`, `FINALIZADO`, 409, `cambio: false`); IRIS detenido → 503. |
| `api_pytest_unitarias.txt` | `evidencia_api.ps1` | Salida de `pytest -m "not integration" -v` y estado de `newman`. |
| `api_openapi_verificacion.txt` | `evidencia_api.ps1` | `exportar_openapi.ps1 -Verificar`. |
| `api_correlacion_request_id.txt` | `evidencia_api.ps1` | Respuesta y líneas de log con el mismo `request_id`, por fuente. |
| `api_revision_secretos.txt` | `evidencia_api.ps1` | Búsqueda de secretos reales y lista de apariciones de `password|token|secret` para revisión manual. |
| `api_latencia.txt` | `medir_latencia.ps1` | Latencia por endpoint con método, entorno, volumen y limitaciones. |
| `mongo_pytest.txt` | Fase 2 (histórico) | Corrida de pruebas unitarias de la Fase 2, anterior a las fases 3–8; la vigente es `api_pytest_unitarias.txt`. |

Los logs completos de la API de cada corrida (`*_api.log`) quedan en `docs/evidencia/` pero **no se versionan** (`*.log` está en `.gitignore`); la parte necesaria para RF18 está copiada en `api_correlacion_request_id.txt`.

## 5. Rendimiento básico (RNF18)

Única medición de rendimiento del hito: `scripts/medir_latencia.ps1` el 2026-10-16 (archivo completo en `evidencia/api_latencia.txt`). No hay otras cifras de rendimiento en la documentación; los `tiempo_total_s` de las listas de control son tiempos de una sola request y no se usan como medición.

**Método.** API en la notebook (`uvicorn`, un proceso, sin `--reload`, log en `warning`). Cliente `curl.exe` en la misma máquina: 1 request de calentamiento y 50 secuenciales por endpoint, sin concurrencia, conexión TCP nueva por request. Métrica: `time_total` de curl (conexión + request + respuesta completa). Percentiles por rango más cercano sobre las requests con el código esperado (0 errores en todos los casos).

**Entorno.** Windows 11 Pro, Intel Core Ultra 5 125U, 15,3 GB de RAM, Python 3.13.4; Docker Desktop 29.7.2 con 14 CPU y ~7,4 GiB asignados; un nodo por motor, puertos en `127.0.0.1`, timeouts de §6.3.

**Volumen.** Muestras de los Hitos 4–9: 64 equipos y 1.536 jugadores, 64 partidos, comentarios de muestra de `PAR-001`, 300 observaciones por equipo en la ventana de 5 min de `PAR-001` (de 21.600 puntos de la muestra) y un acta con dos eventos.

| Endpoint | p50 (ms) | p95 (ms) | máx (ms) |
|---|---|---|---|
| CU-01 ficha EQ-001, copia en Redis (`HIT`) | 4,6 | 22,9 | 25,8 |
| CU-01 ficha EQ-001, sin copia (`MISS` → MongoDB + `SET`) | 9,8 | 33,0 | 34,5 |
| CU-03 plantel EQ-002, 24 jugadores (MongoDB) | 9,7 | 17,7 | 25,2 |
| CU-06 eventos PAR-001 (Neo4j) | 10,5 | 15,3 | 113,0 |
| CU-08 comentarios de un minuto, 4 particiones (Cassandra) | 16,5 | 28,6 | 34,7 |
| CU-11 sesión vigente (Redis) | 8,2 | 10,2 | 11,1 |
| CU-16 comparación de 5 min (InfluxDB) | 32,2 | 46,6 | 47,5 |
| CU-18 acta PAR-001 (IRIS) | 6,3 | 9,4 | 14,2 |
| CU-01 con `EQ-1` → 400, sin consultar ninguna base | 3,1 | 5,8 | 22,1 |

**Lectura.** El 400 sin consulta (≈3 ms) es el piso de la API y de curl en esta máquina. La copia en Redis reduce a la mitad la mediana de CU-01 frente a ir a MongoDB. La agregación de InfluxDB es la operación más cara de la muestra. Los máximos aislados (113 ms en Neo4j) son picos de una request entre 50.

**Limitaciones.** Un solo cliente secuencial: no mide throughput ni concurrencia. Cliente, API y bases comparten la notebook. Volúmenes de laboratorio con cachés calientes. Una sola corrida. Las cifras sirven para comparar órdenes de magnitud entre fuentes en este entorno, no para afirmar capacidad en producción (por ejemplo, los picos de 10.000 lecturas/s de comentarios estimados en el Hito 6 no se probaron).

## 6. Limitaciones y problemas conocidos

- **Colección de Postman sin ejecución automática**: `newman` no está instalado en la notebook. Para cerrarlo: `npm install -g newman` y `.\scripts\ejecutar_pruebas.ps1`, o el Runner de Postman con el entorno de `.local/`.
- **Cuelgue intermitente de las unitarias**: en 2 de unas 14 corridas del 2026-10-16 un proceso de pytest quedó detenido sin consumir CPU (una vez en `test_cu19_iris_caido[falla0-503]`, con un volcado de hilos que solo mostraba un import en curso). No se reprodujo en las corridas siguientes (3 corridas completas y 8 de `test_actas.py`, todas OK). Causa no determinada; una hipótesis es que el `lifespan` de la app de prueba crea los adaptadores reales (el `MongoClient` abre hilos de monitoreo hacia el contenedor) aunque las rutas usen los falsos. Queda pendiente aislarlo; mientras tanto, si una corrida no avanza, cortarla y repetirla.
- **API en contenedor no probada**: todo se ejecutó con la API en la notebook. Ver [`conectividad_y_configuracion.md`](conectividad_y_configuracion.md) §5.
- **Muestra de InfluxDB con retención de 7 días**: los puntos del Hito 8 tienen fechas de la carga. Después de 7 días CU-15/16/17 responden `200` vacío (correcto según el contrato) y las pruebas de integración de InfluxDB fallan o se omiten hasta generar una muestra nueva.
- **Datos de muestra**: volúmenes de laboratorio (64 equipos, 1.536 jugadores, 64 partidos, los comentarios de muestra del Hito 6, 21.600 puntos, un acta). No permiten afirmar el comportamiento con los volúmenes de producción del Fixture.

## 7. Matriz de trazabilidad

Estados: **Cumplido** (implementado y con prueba o evidencia de esta corrida), **Parcial** (implementado, falta una parte o su verificación), **Pendiente** (no hecho o no verificable desde el código). Las rutas son relativas a `Hito 10/`; la evidencia está en `docs/evidencia/`.

### 7.1 Requisitos funcionales

| Req. | Requisito (resumen) | Archivo(s) | Prueba / evidencia | Estado |
|---|---|---|---|---|
| RF1 | Servicio HTTP con recursos del Fixture 2030 | `app/main.py`, `app/routes/` | Todas las listas de control; `test_salud.py` | Cumplido |
| RF2 | Casos de uso documentados antes de las rutas | `docs/casos_de_uso.md` | Commit `f719122 Hito 10 - Casos de uso`, anterior a los de los adaptadores | Cumplido |
| RF3 | Endpoints documentales en MongoDB | `routes/equipos.py`, `routes/jugadores.py`, `services/equipos.py`, `adapters/mongo_adaptador.py` | `test_equipos.py`, `test_jugadores.py`, `test_mongo_adaptador.py`, `integracion/test_mongo.py`; `mongo_lista_de_control.txt` | Cumplido |
| RF4 | Partidos/eventos en Neo4j con Cypher parametrizado | `routes/partidos.py`, `routes/equipos.py` (CU-05), `adapters/neo4j_adaptador.py` | `test_partidos.py`, `test_neo4j_adaptador.py::test_consultas_parametrizadas_con_limite_y_sin_estado`, `integracion/test_neo4j.py`; `neo4j_lista_de_control.txt` | Cumplido |
| RF5 | Consultar y registrar comentarios en Cassandra respetando la partición | `routes/comentarios.py`, `services/comentarios.py`, `adapters/cassandra_adaptador.py` | `test_comentarios.py`, `test_cassandra_adaptador.py`, `integracion/test_cassandra.py`; `cassandra_lista_de_control.txt` (Q1/Q2 = `consultas.cql`) | Cumplido |
| RF6 | Sesión en Redis, clave inexistente o expirada | `routes/sesiones.py`, `services/sesiones.py`, `adapters/redis_adaptador.py` | `test_sesiones.py`, `test_redis_adaptador.py`, `integracion/test_redis.py` (TTL corto); `redis_lista_de_control.txt` | Cumplido |
| RF7 | Estadísticas temporales de InfluxDB con intervalo/agregación | `routes/estadisticas.py`, `services/estadisticas.py`, `adapters/influx_adaptador.py` | `test_estadisticas.py`, `test_influx_adaptador.py`, `integracion/test_influx.py`; `influx_lista_de_control.txt` (reproduce el Hito 8) | Cumplido (muestra con retención de 7 días, §6) |
| RF8 | Entidad compleja en IRIS | `routes/actas.py`, `services/actas.py`, `adapters/iris_adaptador.py`, `iris/FixtureH10.Servicio.cls` | `test_actas.py`, `test_iris_adaptador.py`, `integracion/test_iris.py`; `iris_lista_de_control.txt` | Cumplido |
| RF9 | Separar HTTP, casos de uso y acceso por base | `app/routes/`, `app/services/` (`Protocol`), `app/adapters/` | Bloque final de cada `<fuente>_lista_de_control.txt`: ningún archivo de `routes/` ni `services/` importa un driver; `docs/arquitectura_y_adaptadores.md` | Cumplido |
| RF10 | Validar ruta, query y cuerpos antes de consultar | `app/schemas/`, métodos `preparar_*` de `app/services/` | `test_validacion.py`, `_es_400_sin_consultar`; `api_correlacion_request_id.txt` (400 sin línea de adaptador) | Cumplido |
| RF11 | Respuestas de éxito, ausencia, validación, conflicto, dependencia y error interno | `app/errors.py`, `app/manejadores.py`, `responses=` de cada ruta | `test_errores.py`, `test_openapi.py`; `docs/contratos_y_errores.md` §2.1 y §4 | Cumplido |
| RF12 | Formato de error consistente sin datos sensibles | `app/manejadores.py`, `app/schemas/errores.py` | `test_errores.py`, `test_request_id.py`, `test_cu18_no_expone_ids_licencia_ni_clases`; cuerpos de error en las listas de control | Cumplido |
| RF13 | OpenAPI y Swagger UI | `openapi/openapi.yaml`, `app/openapi.py`, `/docs` | `test_openapi.py` (5 pruebas); `api_openapi_verificacion.txt` | **Parcial**: el contrato no declara `servers` (§5.4 pide “servidor o URL local”); la URL local solo figura en la documentación. |
| RF14 | Colección de Postman / cURL reproducible con errores | `postman/fixture2030_collection.json`, `scripts/ejecutar_pruebas.ps1`, scripts `evidencia_*` (cURL) | `test_coleccion_postman.py`; escenarios con `curl.exe` en las listas de control | **Parcial**: la colección no se ejecutó con newman ni con el Runner (newman no instalado). Los mismos escenarios sí se reprodujeron con cURL. |
| RF15 | Pruebas: éxito, inválida, inexistente, dependencia caída | `tests/`, `tests/integracion/` | 426 unitarias y 57 de integración passed; §3 de este documento | Cumplido (ver cuelgue intermitente en §6) |
| RF16 | Configuración separada de secretos | `app/config/settings.py`, `.env.example`, `.gitignore` | `test_salud.py::test_timeouts_por_defecto_de_la_seccion_6_3`; `api_revision_secretos.txt`; `docs/conectividad_y_configuracion.md` | Cumplido |
| RF17 | Evidencia de que cada endpoint llega a su fuente | Scripts `evidencia_*.ps1` | Los 20 CU y `/salud` en las seis listas de control; líneas `dependencia=…` en `api_correlacion_request_id.txt` | Cumplido |
| RF18 | Request id que relacione respuesta y logs | `app/middleware.py`, `app/config/logging.py`, `_traducir` de cada adaptador | `test_request_id.py`; `api_correlacion_request_id.txt` | Cumplido. Los servicios solo registran anomalías (`cache=no_confirmada`, `catalogo=no_actualizado`); en una request normal las líneas son de acceso y de adaptador. |
| RF19 | Lectura vs. escritura e idempotencia | `docs/casos_de_uso.md` §6.4, `docs/contratos_y_errores.md` §5 | `test_cu09_reintento_*`, CU-13/14/19/20 repetidos; listas de Cassandra, Redis e IRIS | Cumplido |
| RF20 | Código, docs, contratos y pruebas en GitHub | Repositorio del equipo, carpeta `Hito 10/` | Historial `07cae71`…`ab9f6b8` (fases 1–8) | **Parcial**: la Fase 9 (documentos, scripts nuevos, evidencia regenerada y el cambio del `.gitignore` raíz que permite versionar `Hito 10/.gitignore`) está sin commit y la rama `moha` no está integrada en `main`. |

### 7.2 Requisitos no funcionales

| Req. | Aspecto | Archivo(s) | Prueba / evidencia | Estado |
|---|---|---|---|---|
| RNF1 | Separación de responsabilidades | `app/routes/`, `app/services/`, `app/adapters/` | Las rutas solo declaran el contrato y llaman a un servicio; grep de drivers en las listas de control | Cumplido |
| RNF2 | Contrato = implementación | `app/openapi.py`, `openapi/openapi.yaml` | `test_openapi.py`, `api_openapi_verificacion.txt`, `test_coleccion_postman.py::test_cada_operacion_del_contrato_tiene_requests` | Cumplido para OpenAPI. La alineación de la colección con las respuestas reales no se comprobó ejecutándola (RF14). |
| RNF3 | Rechazo de entradas inválidas antes de consultar | `app/schemas/`, `preparar_*` | Tests `_sin_consultar` (verifican que el falso no recibió llamadas); `api_correlacion_request_id.txt` | Cumplido |
| RNF4 | Respuestas coherentes | `app/schemas/` | `test_errores.py`, `test_openapi.py::test_cada_error_declarado_tiene_ejemplos_con_codigos_del_contrato` | Cumplido |
| RNF5 | Detalles de cada producto dentro de su adaptador | `app/adapters/` | Grep de imports en cada lista de control; `tests/falsos.py` reemplaza los adaptadores sin tocar rutas ni servicios | Cumplido |
| RNF6 | Configuración por entorno | `app/config/settings.py`, `.env.example` | Arranque fallido con mensaje que nombra la variable (`cargar_settings`); `docs/conectividad_y_configuracion.md` §3 | Cumplido |
| RNF7 | Sin secretos publicados | `.gitignore`, `Hito 10/.gitignore`, máscaras en los scripts | `api_revision_secretos.txt` (0 apariciones de contraseñas, token y sesiones vigentes), chequeos de `evidencia_influx.ps1` y `evidencia_iris.ps1` | Cumplido en los archivos de trabajo; **queda por commitear** el `.gitignore` raíz corregido: el versionado hoy en `main` ignora `Hito 10/.gitignore`, así que un clon no excluiría `.env` ni `.venv/`. Fuera del Hito 10, `Hito 4/README.md` muestra la contraseña de laboratorio del contenedor de MongoDB. |
| RNF8 | Timeouts definidos | `app/config/settings.py`, constructores de los adaptadores | `test_timeouts_por_defecto_de_la_seccion_6_3`, `test_tx_timeout_de_la_seccion_6_3_y_lectura_en_la_base_configurada`; `docs/conectividad_y_configuracion.md` §3.1 | Cumplido |
| RNF9 | Dependencia caída: sin espera indefinida ni datos sensibles | `_traducir` de cada adaptador, `app/manejadores.py` | Bloques *detenido* de las listas de control: 503 en ≤ 2,1 s por fuente, cuerpo con el formato único | Cumplido |
| RNF10 | Logs con ruta, método, request id, dependencia, resultado y duración | `app/middleware.py`, `app/config/logging.py`, adaptadores | `test_request_id.py::test_log_de_acceso_con_request_id_y_sin_sesion`; `api_correlacion_request_id.txt` | Cumplido |
| RNF11 | Reproducible siguiendo el README | `README.md`, `scripts/` | Los scripts se ejecutaron en la notebook de un integrante | **Pendiente**: falta que una persona que no programó la API la levante siguiendo solo el README (lista de control de la Fase 9). El cuelgue intermitente de §6 puede afectar esa prueba. |
| RNF12 | Paginación, límites, cursores o ventanas | Rutas (`limite`, `pagina`), `services/comentarios.py` (cursor), `services/estadisticas.py` y `partidos.py` (ventanas), `LIMIT`/`TOP` en los adaptadores | `test_limite_fuera_de_rango`, tests de cursor y ventana; `docs/contratos_y_errores.md` §3 | Cumplido |
| RNF13 | Cada consulta ligada a un patrón de acceso | Adaptadores (Q01…Q09 del Hito 4/5, Q1–Q3 del Hito 6, P2–P4 del Hito 8) | `docs/arquitectura_y_adaptadores.md` §2; CU-02 exige `confederacion`; Cassandra sin `ALLOW FILTERING` | Cumplido |
| RNF14 | Idempotencia documentada | `services/comentarios.py`, `redis_adaptador.py`, `services/actas.py` | `docs/contratos_y_errores.md` §5; tests y evidencia de RF19 | Cumplido |
| RNF15 | Legibilidad y organización | Estructura de `Hito 10/` (README §7) | Nombres por módulo y por fuente | Cumplido |
| RNF16 | GitHub con historial y acceso docente | Repositorio del equipo | Commits por fase 1–8 | **Parcial**: Fase 9 sin commit/push; el acceso del docente no se puede verificar desde el código. |
| RNF17 | Integridad de identificadores, timestamps y estados | Proyecciones de los adaptadores, `schemas/` | `test_cu18_no_expone_ids_licencia_ni_clases`, integración (`creadoEn` con milisegundos, `inicio` UTC, `ultimaObservacion`); cuerpos de las listas de control | Cumplido |
| RNF18 | Rendimiento con método y evidencia | `scripts/medir_latencia.ps1` | `api_latencia.txt`; §5 de este documento | Cumplido con las limitaciones declaradas (un cliente secuencial, una corrida, datos de muestra). |

### 7.3 Pendientes, en orden de prioridad

1. Commit y push de la Fase 9 y del `.gitignore` raíz; integrar la rama en `main` (RF20, RNF7, RNF16).
2. Instalar `newman` y correr `.\scripts\ejecutar_pruebas.ps1`, o ejecutar la colección con el Runner; guardar la salida en `docs/evidencia/` (RF14, RNF2).
3. Prueba de reproducibilidad por un integrante que no programó la API (RNF11).
4. Declarar `servers` (`http://127.0.0.1:8000`) en `app/openapi.py` y regenerar `openapi.yaml` (RF13, §5.4).
5. Aislar el cuelgue intermitente de las pruebas unitarias (§6).
