# Hito 13 - Monitoreo y defensa del Fixture 2030

La API del Hito 10 conserva sus seis adaptadores y agrega `/metrics`. Prometheus observa esa API, MongoDB mediante Percona Exporter y Redis mediante Redis Exporter. Grafana presenta un único dashboard de seis paneles. Prometheus se observa a sí mismo como cuarta fuente auxiliar.

El alcance es un entorno Windows con Docker Desktop y un nodo por producto. Las consultas funcionales siguen usando las bases y los datos existentes. No hay clusters ni alta disponibilidad comprobada.

## Inicio y acceso

Ejecutar desde la raíz del repositorio en PowerShell. Se requiere Docker Desktop con contenedores Linux. Python 3.12 o posterior en Windows permite ejecutar la demostración y la comprobación de versión. No necesita paquetes adicionales.

Si los contenedores ya existen, iniciarlos conservando sus datos:

```powershell
docker desktop start
docker start fixture2030-mongodb grupo13-hito5-neo4j-1 grupo13-hito6-cassandra-1 grupo13-hito7-redis-1 grupo13-hito8-influxdb-1 grupo13-hito9-iris-1
```

Esperar a que Cassandra termine de iniciar. Un contenedor iniciado no implica que su protocolo ya esté listo. En una instalación nueva, preparar una sola vez cada fuente según los [pasos del Hito 10](../Hito%2010/README.md). `fixture.cmd todo`, `preparar` e `influx` cargan muestras. No usarlos para encender datos existentes ni para corregir una conexión fallida.

Preparar las carpetas persistentes y los secretos locales una vez:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE/docker/data/fixture2030-h13/prometheus"
New-Item -ItemType Directory -Force "$env:USERPROFILE/docker/data/fixture2030-h13/grafana"
if (-not (Test-Path 'Hito 13/.env')) { Copy-Item 'Hito 13/.env.example' 'Hito 13/.env' }
notepad 'Hito 13/.env'
```

Completar `MONGODB_USER` y `MONGODB_PASSWORD` con credenciales locales válidas en `admin`. Establecer una contraseña propia en `GRAFANA_ADMIN_PASSWORD`. `REDIS_PASSWORD` queda vacío para la instancia del Hito 7 sin autenticación. No copiar secretos al JSON del dashboard ni a evidencias. La prueba usa el usuario local ya disponible de MongoDB. Limitarlo a `clusterMonitor` sería una mejora de permisos para una instalación compartida, no una capacidad comprobada aquí.

Construir la API desde un commit que incluya la instrumentación y comprobar la versión. Guardar primero los cambios de código en Git. `verificar_version.py` compara todos los archivos de `/app` con el commit y rechaza imágenes sin la etiqueta correcta o con montajes que sustituyan código:

```powershell
$revisionH13 = git rev-parse HEAD
docker compose -f 'Hito 10/docker-compose.yml' build --build-arg "VCS_REF=$revisionH13" api
docker compose -f 'Hito 10/docker-compose.yml' up -d --no-build api
Invoke-RestMethod http://127.0.0.1:8000/api/v1/salud
docker compose -f 'Hito 13/docker-compose.yml' config --quiet
docker compose -f 'Hito 13/docker-compose.yml' up -d
docker compose -f 'Hito 13/docker-compose.yml' exec -T prometheus promtool check config /etc/prometheus/prometheus.yml
```

`config --quiet` evita imprimir la configuración que contiene secretos. Las imágenes nuevas tienen versiones fijadas en [Compose](docker-compose.yml). Los contenedores de las bases se conservan, sin actualizar sus imágenes. Prometheus y Grafana persisten en `%USERPROFILE%/docker/data/fixture2030-h13/`. La retención de Prometheus es siete días. Grafana guarda usuarios y preferencias en su propia carpeta. Los exporters solo se exponen dentro de la red del Compose.

| Recurso | Acceso |
| --- | --- |
| Swagger y consola | <http://127.0.0.1:8000/docs> y <http://127.0.0.1:8000/> |
| Métricas de API | <http://127.0.0.1:8000/metrics> |
| Targets de Prometheus | <http://127.0.0.1:9090/targets> |
| Consultas y alertas | <http://127.0.0.1:9090/query> y <http://127.0.0.1:9090/alerts> |
| Grafana | <http://127.0.0.1:3000/d/fixture2030-h13> |

En Grafana ingresar como `admin` con la contraseña del `.env` local. Esa variable inicializa una base nueva de Grafana, no cambia una contraseña ya persistida. La fuente Prometheus y el dashboard se provisionan desde archivos. El JSON versionado es la fuente del diseño y las ediciones por interfaz están deshabilitadas.

## Componentes y alcance de la observación

| Componente | Modelo y función | Puerto del host | Observación y límite |
| --- | --- | --- | --- |
| API Hito 10 | HTTP, validación y coordinación de adaptadores | 8000 | `up` y métricas HTTP. Un `/metrics` accesible no comprueba las seis bases |
| MongoDB Hito 4 | Documentos de equipos y jugadores | 27017 | Exporter 0.47.1, interno 9216. `mongodb_up` y `mongodb_ss_connections`. No acredita cada índice ni todas las operaciones |
| Redis Hito 7 | Clave-valor, sesiones, caché e idempotencia | 16379 → 6379 | Exporter 1.76.0, interno 9121. `redis_up` y `redis_connected_clients`. No garantiza persistencia de cada clave |
| Neo4j Hito 5 | Grafo de equipo, jugador, partido, estadio y evento | 7687, interfaz 7474 | Salud y requests de partido y agenda. Sin exporter en esta entrega |
| Cassandra Hito 6 | Columnas anchas, comentarios por partición | 9042 | Salud, ventana con cursor y verificación separada del Hito 12. Sin métricas continuas del motor |
| InfluxDB Hito 8 | Series temporales de estadísticas | 8181 | Salud y consulta SQL desde API. Un resultado vacío puede ser válido por retención |
| IRIS Hito 9 | Objetos persistentes, actas y reglas de estado | 1972, portal 52773 | Salud y lectura del acta. No se modifica la muestra canónica |
| Prometheus 3.5.0 | Series de métricas y evaluación de reglas | 9090 | Scraping cada 15 s, timeout 10 s, reglas cada 15 s. Su caída elimina esta observación |
| Grafana 12.1.1 | Visualización de Prometheus | 3000 | Se comprueba acceso y dashboard. No almacena las series de las bases |

El job `redis` apunta a la instancia del Hito 7 en 16379. El contenedor adicional `fixture2030-redis` en 6379 no pertenece al recorrido de la API. No se lo detiene ni se lo usa como reemplazo.

Tres señales responden preguntas distintas:

1. `up{job="redis"}` indica si Prometheus pudo leer el exporter.
2. `redis_up` indica si ese exporter pudo consultar Redis. Puede valer cero mientras el target sigue UP.
3. `GET /api/v1/sesiones/{sesionId}` comprueba el resultado funcional. Con Redis detenido devuelve 503. Una ficha de equipo puede seguir respondiendo 200 con `X-Cache: BYPASS` porque consulta MongoDB.

## Métricas, dashboard y consultas

La instrumentación agrega un contador `fixture_http_requests_total` y un histograma `fixture_http_request_duration_seconds`. El contador registra requests finalizados por `method`, `route`, `status` y `traffic`. El histograma usa las mismas etiquetas salvo `status`. Cada proceso tiene su propio registro. Esta ejecución utiliza un único worker de Uvicorn.

`route` es la plantilla como `/api/v1/equipos/{equipoId}`. Las rutas desconocidas se agrupan en `__unmatched__` y los métodos no previstos en `OTHER`. No se usan IDs, parámetros, URLs completas, requestId ni mensajes de error como etiquetas. Se miden solamente rutas bajo `/api/v1/`. `/metrics`, Swagger, OpenAPI y la interfaz quedan fuera. `/api/v1/salud` tiene `traffic="salud"` y los paneles de negocio filtran `traffic="negocio"`.

La duración usa un reloj monotónico desde el ingreso al middleware hasta terminar de procesar la respuesta, incluido el envío del cuerpo por ASGI. No es la duración de red medida desde el navegador ni el tiempo interno de una base. Los buckets son 0,005, 0,01, 0,025, 0,05, 0,1, 0,25, 0,5, 1, 2,5, 5 y 10 segundos, más infinito.

El [dashboard JSON](grafana/dashboards/fixture2030.json) muestra endpoints de métricas, estado de las dos bases, latencia, requests por segundo, errores y conexiones por base. Usa rango inicial de 15 minutos y refresco de 15 segundos. Las tasas usan una ventana móvil fija de dos minutos, con unas ocho muestras por serie. Sin requests no hay latencia definida. Un gráfico vacío no equivale a cero.

| Consulta PromQL | Significado, unidad y período |
| --- | --- |
| `up{job=~"fixture-api\|mongodb\|redis"}` | Último scraping de los tres endpoints, 0 o 1. Sin ventana agregada |
| `mongodb_up{job="mongodb"}` y `redis_up{job="redis"}` | Estado observado por cada exporter, 0 o 1. Última muestra |
| `sum(rate(fixture_http_requests_total{job="fixture-api",traffic="negocio"}[2m]))` | Requests finalizados por segundo, media móvil de dos minutos. Incluye errores |
| `histogram_quantile(0.95, sum by (le) (rate(fixture_http_request_duration_seconds_bucket{job="fixture-api",traffic="negocio"}[2m])))` | P95 estimado en segundos para los requests de los últimos dos minutos |
| `sum(rate(fixture_http_requests_total{job="fixture-api",traffic="negocio",status=~"5.."}[2m]))` | Respuestas 5xx por segundo durante los últimos dos minutos |
| `mongodb_ss_connections{job="mongodb",conn_type="current"}` y `redis_connected_clients{job="redis"}` | Conexiones actuales y clientes conectados, cantidades instantáneas. Incluyen conexiones de monitoreo |

P95 es el umbral bajo el cual se estima que terminó el 95 % de las solicitudes. `histogram_quantile` interpola dentro de buckets, por lo que es una estimación, no el promedio del 95 % de las solicitudes. El panel también muestra la media como tasa de `_sum` dividida por tasa de `_count`. Las conexiones de MongoDB y Redis permiten distinguir actividad, pero no comparan velocidad ni cantidad de usuarios.

El panel de errores presenta 4xx y 5xx por separado. Si existe tráfico medido pero aún no hay una serie de esa clase de error, muestra cero mediante `or` con la tasa total multiplicada por cero. Si no existe tráfico medido, conserva la ausencia de datos.

Los nombres de las métricas de exporters se verifican sobre las versiones ejecutadas. Las referencias de implementación son [Percona Exporter](https://github.com/percona/mongodb_exporter), [Redis Exporter](https://github.com/oliver006/redis_exporter), [histogramas de Prometheus](https://prometheus.io/docs/practices/histograms/) y [provisioning de Grafana](https://grafana.com/docs/grafana/latest/administration/provisioning/). Las consultas del dashboard se guardan junto con sus resultados reales en la evidencia.

## Alertas operativas

Las dos reglas están en [reglas.yml](reglas.yml), cargadas y validadas por Prometheus. Se consultan en su interfaz. No hay canales externos de notificación.

| Alerta | Condición y duración | Severidad, responsable | Impacto y recuperación |
| --- | --- | --- | --- |
| `FuenteNoDisponible` | Target de API o exporter en cero, estado de MongoDB o Redis en cero, o ausencia de las series esperadas, durante 30 s | Crítica, integrante de operación del Grupo 13 | Pérdida de observación o acceso a una fuente. Revisar Targets, logs y contenedor. Iniciar el servicio existente y repetir una request funcional |
| `ErroresAPIAltos` | Más de 5 % de requests de negocio con 5xx en 2 min, al menos 20 requests en esa ventana y condición sostenida 1 min | Advertencia, integrante responsable de API del Grupo 13 | Consultas o sesiones fallan. Identificar ruta y dependencia mediante salud y logs por requestId. Recuperar la fuente y comprobar que descienden los 5xx |

Son valores del entorno de prueba. Treinta segundos evitan reaccionar a una única muestra fallida de 15 s. El mínimo de 20 requests reduce alarmas por una solicitud aislada. El 5 % permite mostrar una degradación deliberada con carga pequeña. No son un SLA demostrado ni una promesa de disponibilidad. Los errores 4xx deliberados no disparan la alerta de 5xx. Una serie ausente indica falta de observación, no demuestra que la base esté caída.

## Demostración reproducible

Con la API instrumentada, las fuentes disponibles y el monitoreo iniciado, ejecutar desde la raíz:

```powershell
$marcaH13 = Get-Date -Format 'yyyyMMdd-HHmmss'
python -X utf8 'Hito 13/demo.py' --falla-redis --salida "Hito 13/evidencia/demo-$marcaH13"
```

El script exige una carpeta nueva y verifica la imagen contra el commit antes de emitir carga. Comprueba salud y lecturas de las seis fuentes. Crea una sesión temporal que cierra al finalizar. Dos clientes alternan listado de equipos, ficha cacheada, lectura de sesión y equipo inexistente. Cada cliente espera medio segundo después de cada respuesta. El máximo teórico es cuatro requests por segundo y la tasa real baja con la latencia.

Las fases comienzan con 120 s de actividad previa, 105 s con Redis detenido y 135 s de recuperación. Si falta observar una condición, se mantiene la carga y se vuelve a comprobar cada 15 s. Los límites son 180 s para la primera fase y 240 s para cada una de las otras dos, más el cierre de las requests y consultas en curso. No se considera una alerta `pending` como `firing`.

La ventana móvil de dos minutos, el período sostenido de un minuto de `ErroresAPIAltos` y los ciclos independientes de scraping y evaluación impiden fijar la activación en un segundo exacto. El límite de cuatro minutos deja margen para esos ciclos. Al recuperar Redis también debe salir de la ventana el tráfico 5xx anterior y desaparecer toda alerta pendiente o activa. Si vence el plazo, se guarda el resultado incompleto con el motivo observado.

El 404 del equipo inexistente es deliberado. El 503 de la sesión durante la falla también lo es. Cualquier otro estado inesperado interrumpe la prueba y se registra. `finally` intenta recuperar Redis y cerrar la sesión por separado, conserva el error original y guarda el resultado parcial aunque falle alguna limpieza. La recuperación exige `PONG` y el cierre exige 204. Ante un cierre forzado de la terminal o del equipo, recuperar manualmente con `docker start grupo13-hito7-redis-1` y comprobar salud.

Sin `--falla-redis`, el script ejecuta solo los dos minutos iniciales. No hay escrituras en MongoDB, Neo4j, Cassandra, InfluxDB ni IRIS. La caché de la API puede renovarse y la sesión temporal usa el TTL existente de 1800 s. No se borran volúmenes ni se vuelven a cargar muestras.

## Datos, resultados y límites

La verificación inicial encontró Cassandra, Redis del Hito 7 e InfluxDB detenidos. Después de iniciar esos mismos contenedores, salud respondió correctamente para las seis fuentes. No fue necesario corregir sus adaptadores. InfluxDB respondió 200 con `puntos: []`. Su muestra anterior excede la retención de siete días y no se cargaron puntos nuevos para ocultar esa situación.

`PAR-001` es una referencia compartida por muestras didácticas independientes. La [carga del grafo](../Hito%205/queries/02_load.cypher) establece FINALIZADO y dos sustituciones. La [muestra de objetos](../Hito%209/scripts/FixtureH9.Demo.cls) crea un acta PENDIENTE con dos eventos diferentes y exige ese estado en su validación. El [dominio IRIS](../Hito%209/scripts/FixtureH9.Partido.cls) permite PENDIENTE → EN_JUEGO → FINALIZADO. No existe propagación de estados entre módulos. No deben presentarse como una única acta sincronizada. La API conserva cada fuente y muestra su procedencia.

La nueva [verificación del Hito 12](../Hito%2012/evidencia/verificacion-20261115/README.md) identifica la variante optimizada en `5054f7f333133228cc23c635ad4c4491a4567974`. Conserva datos e históricos. No cambia la conclusión anterior: no hubo una mejora uniforme de P95 y P99 en las mediciones históricas.

La [ejecución completa del 16 de noviembre](evidencia/demo-20261116-final/README.md) duró 6 min 4 s, de 23:47:01 a 23:53:05, UTC−03. Se reconstruyó la API desde `10f3c7d37e1bb6cb48067cc256a54991ade1d7c6` y se compararon los 30 archivos del contenedor con ese commit. El [resultado](evidencia/demo-20261116-final/demostracion.json) conserva `completa: true`, tres fases comprobadas, cierre de sesión 204 y ningún fallo inesperado. Los commits posteriores de documentación y evidencia no sustituyen el SHA ejecutado.

| Fase | Respuestas de la carga | Resultado observado al cierre de la fase |
| --- | --- | --- |
| Antes, 120 s programados | 352 de estado 200 y 116 de estado 404 | Seis fuentes sanas, tres endpoints de métricas UP, MongoDB y Redis en 1, caché HIT y ninguna alerta |
| Durante, 105 s programados | 206 de estado 200, 102 de estado 404 y 102 de estado 503 | Exporter de Redis UP con `redis_up=0`, ficha 200 con BYPASS, sesión 503 y ambas alertas `firing` |
| Después, 135 s programados | 396 de estado 200 y 131 de estado 404 | Redis con PONG, salud y sesión 200, `redis_up=1`, 5xx/s en cero y ninguna alerta pendiente o activa |

Se emitieron 1.405 requests de carga. Los 349 errores 404 y 102 errores 503 fueron deliberados. Las consultas de los seis paneles devolvieron datos. La tasa de negocio al cierre de cada fase fue aproximadamente 3,88, 3,85 y 3,90 requests/s, sobre ventanas móviles de dos minutos. El P95 estimado fue 9,61, 9,28 y 9,12 ms. La falla no produjo un aumento sostenido de latencia, porque Redis rechazó pronto la operación y la ficha continuó desde MongoDB. El panel de errores y el estado del exporter detectaron la degradación.

MongoDB mantuvo siete conexiones en las tres observaciones. Redis mostró tres clientes antes y después. Durante la caída, `redis_connected_clients` no tuvo muestra, por lo que ese hueco no debe interpretarse como una medición de cero clientes. La disponibilidad de Redis se interpreta con `redis_up` y se confirma con las requests de sesión.

El [intento previo incompleto](evidencia/demo-20261116/README.md) se conserva por separado. La nueva ejecución alcanzó ambas alertas dentro del primer tramo de 105 s. No necesitó extender la espera, cuyo comportamiento de reintento y vencimiento está cubierto por pruebas unitarias. No se cambiaron umbrales para obtener ese resultado.

Están guardados la [captura de targets](evidencia/demo-20261116-final/01_targets.png), el [entorno y la fuente Grafana](evidencia/demo-20261116-final/entorno.json) y las [validaciones](evidencia/demo-20261116-final/validacion.txt). Las capturas `02_dashboard.png` y `03_alertas.png` están pendientes. Sus pantallas, rango y rutas exactas figuran en el [resumen de la ejecución](evidencia/demo-20261116-final/README.md). La publicación queda pendiente hasta completar esas dos capturas.

El guion está en [defensa.md](defensa.md). La prueba es breve, local y con dos clientes. No acredita tolerancia a particiones de red, réplicas, regiones, alta disponibilidad ni capacidad para tráfico mundial. Los pings no cubren todas las operaciones. La retención vacía no prueba agregaciones con datos recientes.

Una mejora transversal propuesta es definir la autoridad del estado de partido y versionar las muestras compartidas. La diferencia comprobada entre Neo4j e IRIS justifica ese acuerdo de integración. Primero habría que especificar qué representa cada estado y cómo se valida una proyección. No se implementa sincronización distribuida en esta entrega. Como mejora de observación, medir el porcentaje de `BYPASS` permitiría detectar degradación de caché aunque la respuesta HTTP siga siendo 200.

## Validación y detención

```powershell
docker compose -f 'Hito 13/docker-compose.yml' config --quiet
docker compose -f 'Hito 13/docker-compose.yml' exec -T prometheus promtool check config /etc/prometheus/prometheus.yml
python -X utf8 -m unittest discover -s 'Hito 13' -p 'test_demo.py' -v
docker compose -f 'Hito 10/docker-compose.yml' exec -T api python -m pytest tests/unit -q -p no:cacheprovider
docker compose -f 'Hito 10/docker-compose.yml' exec -T api python -m pytest tests/integration -q -rs -p no:cacheprovider
```

La versión ejecutada aprobó 43 pruebas de la API y nueve pruebas de la demostración. No hubo fallos en esta validación. Se omitió una prueba de estadísticas recientes de InfluxDB por ausencia de puntos retenidos. La consulta vacía válida y la disponibilidad de InfluxDB sí se comprobaron. Las pruebas de integración usan datos temporales y limpian sus escrituras. La paginación Cassandra comprueba orden completo contra una lectura directa, cursores distintos, ausencia de duplicados y conservación de los ocho comentarios de la muestra original, aunque coexistan otros comentarios. Los errores tipados distinguen indisponibilidad 503 de timeout 504 y comprueban su código y dependencia. Revisar siempre el resumen de omisiones. No ejecutar una carga de datos solo para obtener un resultado verde.

Se conserva el [registro inicial de pruebas](evidencia/pruebas-iniciales-9e93200.txt), con 41 aprobadas, dos fallidas y una omitida en `9e93200`. Sus fallos correspondían a esperar solo ocho comentarios cuando coexistían 108 y a exigir 503 ante un timeout MongoDB que devuelve 504. Se ajustaron las comprobaciones a los datos coexistentes y al contrato de errores, conservando las verificaciones de orden, integridad y tiempo. Ese registro histórico no corresponde al resultado de la versión final ejecutada.

```powershell
docker compose -f 'Hito 13/docker-compose.yml' stop
docker compose -f 'Hito 10/docker-compose.yml' stop api
```

Estos comandos conservan datos y contenedores. Las bases se pueden detener individualmente al terminar, coordinando su uso. No ejecutar `down -v` ni eliminar carpetas persistentes. `.env` y `.local` permanecen fuera de Git para proteger credenciales.
