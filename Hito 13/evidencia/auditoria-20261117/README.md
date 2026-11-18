# Auditoría integrada del 17 y 18 de noviembre de 2026

Se comprobaron las seis fuentes, la API, la consola existente y el monitoreo después de ajustar los modelos de MongoDB e InfluxDB y migrar la persistencia de Cassandra. Las operaciones temporales se limpiaron y los servicios afectados quedaron recuperados. El alcance sigue siendo un nodo por producto en Docker Desktop.

El código ejecutado es **`ed49e3fcb1dad4f1767dc17dbb0c87753e9cc4aa`**. La API se reconstruyó antes de validar y sus 31 archivos se compararon con los blobs de ese commit. La imagen es `sha256:1910fc8428d1528750a389e0461d0df55214da3125de557a385fceae6bdd5eae`. [version.json](version.json) registra la comparación inicial y [validacion-final.json](validacion-final.json) confirma la misma imagen y archivos después del reinicio del entorno. Los commits posteriores de documentación no cambian esta atribución.

## Matriz de revisión

| Hito | Criterio y estado anterior | Cambio o comprobación | Pruebas y límites |
| --- | --- | --- | --- |
| 4 | Jugadores incluía partidos y goles internacionales | Se retiraron los dos atributos de semilla, validadores, CRUD, consultas, índice, API, OpenAPI e interfaz. Se mantienen atributos propios del jugador y plantel | 1.536 documentos conservados salvo esos campos. CRUD, validación, integridad, 12 consultas y Q04 con IXSCAN correctos. La medición histórica del índice no se repitió |
| 5 | Carga, CRUD, análisis e integridad acompañados por muchos recorridos auxiliares | Se concentró la explicación en los recorridos principales. Se conservaron consultas y verificadores opcionales que respaldan consumidores y evidencia | 1.800 nodos, 2.112 relaciones, controles de integridad correctos y CRUD sin residuos. Carga MERGE revisada estáticamente y con evidencia histórica, sin recargar el grafo |
| 6 | `/var/lib/cassandra` usaba una carpeta de Windows | Migración al volumen nombrado `grupo13-hito6_cassandra_data`, conservando Cassandra 5.0.9 | 330 archivos restaurados y comparados, cuatro tablas con huellas iguales antes, después y tras reinicio. Se conservan origen y respaldo. No se ensayó pérdida del disco |
| 7 | `noeviction` estaba configurado, pero faltaba distinguir sus efectos | Se documentaron rechazo de escritura, expiración y caída. Se agregaron dos pruebas pequeñas de errores OOM | Sesión nueva: 503 tipado. Escritura de caché fallida: lectura MongoDB 200 BYPASS. OOM se probó con dobles, sin saturar Redis. Sesión, TTL y recuperación se probaron con el motor real |
| 8 | `estadio_id` repetía una dependencia de `partido_id` sin acceso que lo usara | Nueva tabla `estadisticas_equipo_v2` con tags de partido y equipo. Generador, consultas, validación y adaptador actualizados | Tabla original preservada, sin puntos retenidos al migrar. 20 puntos en una base temporal, agregación HTTP y tres pruebas selectivas correctas. Base temporal eliminada |
| 9 | Demo extensa y helpers que también apoyan pruebas y API | Recorrido de defensa centrado en herencia, padre e hijo, `%Save()`, navegación y SQL. Se conservan validaciones y búsquedas por índice utilizadas por la API | Igualdad objetos/SQL, rechazo de hijo inválido, atomicidad y transiciones sobre entidad temporal, sin residuos. La regla de transición exige usar el método de dominio |
| 10 | API y consola consumían los campos anteriores | Contratos y adaptadores coherentes con los modelos nuevos. Se preservan caché, sesión e idempotencia usadas en Hito 13 | 26 unitarias y 19 de integración aprobadas, una omitida por retención. Swagger, HTTP real y consola verificados. No se amplió la interfaz |
| 11 | Era necesario distinguir acceso funcional de identidad y permisos | El diagnóstico publicado ya separaba las capas. Se ejecutó sobre la versión nueva | 61 OK, 9 WARN, 0 FAIL, salida 2 por verificaciones independientes incompletas. No representa una caída de las bases |
| 12 | Existía verificación trazable de la variante optimizada en `5054f7f` | Se contrastaron los hashes con Git y la misma imagen. Tras migrar Cassandra se repitió solo la validación de datos | 2.400 filas íntegras, cero escrituras. Sin nueva carga ni comparación de rendimiento. Se mantiene la ausencia de mejora uniforme de P95/P99 en los históricos |
| 13 | Existía una demostración completa del 16 de noviembre | Nueva demostración sobre `ed49e3f` después de los ajustes, con falla y recuperación de Redis | Tres fases completas, seis paneles con datos, ambas alertas firing y luego resueltas. Captura histórica y consultas verificadas nuevamente el 18 de noviembre |

## Resultado funcional por componente

Los drivers de la API usan `host.docker.internal`. La comprobación de [conectividad](conectividad.md) registra destino, contexto, DNS, TCP, protocolo y lectura sin publicar credenciales.

| Fuente y contenedor | Puerto del host y contexto | Resultado real |
| --- | --- | --- |
| MongoDB, `fixture2030-mongodb` | 27017, `fixture2030` | Listado UEFA paginado, ficha, tres arqueros de EQ-001 y correspondencia con los documentos. El validador rechaza las estadísticas retiradas |
| Neo4j, `grupo13-hito5-neo4j-1` | 7687, `neo4j` | PAR-001 con equipos, estadio y eventos. Agenda de EQ-001 y análisis de caminos correctos |
| Cassandra, `grupo13-hito6-cassandra-1` | 9042, `fixture2030_comentarios` | Ventana con cursor contra lectura directa, orden completo, sin duplicados ni omisiones, conservando los ocho comentarios originales dentro de la ventana |
| Redis, `grupo13-hito7-redis-1` | 16379 → 6379, base 0 | Caché MISS/HIT, invalidación, sesión temporal, vencimiento y cierre. Durante la caída, ficha BYPASS y sesión 503. La otra instancia en 6379 no intervino |
| InfluxDB, `grupo13-hito8-influxdb-1` | 8181, `fixture2030_h8` | Consulta vacía válida en la base habitual. Agregación de diez filas temporales de PAR-001 en cinco intervalos, con dos equipos, comprobada por separado |
| IRIS, `grupo13-hito9-iris-1` | 1972, namespace `USER` | Acta y SQL coincidentes. Validación encapsulada y atomicidad sobre un árbol temporal, eliminado al finalizar |

La API conserva sus rutas y errores. La [correspondencia con el origen](origen-y-api.json) y las pruebas cubren validación previa, paginación, ausencia, conflicto, indisponibilidad 503 y timeout 504. La integración usa `TestClient` con drivers reales. El diagnóstico, la demostración y Swagger agregan requests HTTP al contenedor en 8000.

La consola mostró listado, ficha MISS/HIT, plantel filtrado con estado, agenda, partido, comentarios, mensaje explícito de estadísticas vacías, acta y apertura/cierre de sesión. La [captura de la interfaz](01_interfaz.jpg) corresponde al 17 de noviembre. El 18 se ejecutó `GET /api/v1/salud` desde Swagger con HTTP 200 y las seis fuentes `ok`.

`PAR-001` sigue FINALIZADO en Neo4j y PENDIENTE en IRIS. Las muestras tienen eventos distintos. La API consulta cada fuente y conserva su procedencia, sin sincronización ni transacción entre ellas.

## Pruebas, omisiones y permisos

El [resumen de pruebas](pruebas.json) separa las ejecuciones y sus métodos:

- API: **45 aprobadas, 0 fallidas, 1 omitida** el 17 de noviembre. La omisión corresponde a puntos recientes de InfluxDB, no a conexión fallida.
- Hito 11: **6 aprobadas**, con dobles para la clasificación del diagnóstico.
- Hito 13: **9 aprobadas**, con dobles para condiciones, esperas y finalización.
- InfluxDB temporal: **3 aprobadas, 43 deseleccionadas**. Es una repetición selectiva de casos de la misma suite, no tres pruebas nuevas para sumar al total.
- MongoDB: integridad, rechazos de validación, CRUD y consultas correctos. Neo4j: [integridad, CRUD y análisis](neo4j.txt). IRIS: [objetos, SQL, atomicidad y transiciones](iris-objetos-sql.txt).
- Compose de Hitos 4 a 10, 12 y 13 válido. `promtool check config` y `promtool check rules` correctos. Grafana provisionado con los seis paneles del JSON y fuente Prometheus saludable.

El diagnóstico tiene salida 2 porque no completa todas las verificaciones independientes de seguridad. MongoDB permitió consultar identidad y privilegio `find` sobre `equipos`. Neo4j permitió consultar identidad, pero su autorización queda **no verificada independientemente**. Redis permitió `ACL WHOAMI` y `ACL DRYRUN GET`, pero no acreditó autenticación por credencial. Cassandra, InfluxDB e IRIS no permitieron separar identidad y permisos con el diagnóstico disponible. Sus lecturas funcionales sí funcionaron. Otra advertencia corresponde a una clave de muestra Redis ausente. No se otorgaron permisos adicionales para cambiar estos resultados.

No hubo fallos funcionales inesperados en las pruebas completadas. Durante el registro de objetos IRIS fue necesario separar su salida de texto del JSON del comprobador. Se conservó la salida de objetos por separado y se volvió a comprobar la correspondencia con la API. Las interrupciones de acceso al navegador no se contabilizan como pruebas de la aplicación.

El lanzador de PowerShell y el ejemplo de Neo4j se ajustaron en `4ddebf43a6ffee603cb2ccf91c06e17bddf4acd9` para usar credenciales locales. Los generadores de evidencia de MongoDB validan Compose con `--quiet`. Se comprobaron cuatro escenarios del lanzador con archivos temporales, sintaxis de PowerShell y Bash, Compose de ambas bases y `fixture.ps1 estado` con HTTP 200. Estos archivos quedan fuera de la imagen de la API. La imagen y el SHA `ed49e3f` siguen identificando la ejecución de integración y monitoreo.

El registro histórico de configuración de MongoDB conserva un valor de ejemplo que coincidía con la credencial local. También hubo un valor de ejemplo de Neo4j en revisiones anteriores. Antes de compartir el repositorio, corresponde rotar ambas contraseñas y actualizar los `.env` locales de las bases, la API y los exporters que las usen. No se cambiaron las credenciales del entorno durante esta auditoría.

## Migraciones y respaldos

[migraciones.json](migraciones.json) registra fechas, hashes, imagen, montaje y recuentos. Los respaldos locales están en `C:\Users\denis\docker\backups\fixture-auditoria-20261117` y se conservan fuera del repositorio.

MongoDB: `mongodb-jugadores-original.json` guarda documentos completos, validador e índices. SHA256 `faea2b77b08a839d70a68f97acc79245c9284c2cf5247ff5d3fadfb198844940`. Se comprobó lectura y equivalencia antes de retirar exclusivamente los dos atributos. El [procedimiento de retorno](../../../Hito%204/README.md) rechaza sobrescribir cambios posteriores. No se ejecutó una restauración real sobre MongoDB después de migrar.

Cassandra: `cassandra.tar`, `origen.sha256`, `restaurado.sha256` y `docker-compose.rollback.yml` conservan el respaldo y el montaje anterior. El TAR tiene SHA256 `16b319890dd5a881884112c3d09140d7fbf86929fab964921e3af2f75b919574`. Los 330 archivos restaurados coincidieron antes de arrancar. Se mantuvo la imagen `sha256:ee178b38a2746a8e15a115bd038ad1f864391d04a84162a018cb0dd79511709a`, Cassandra 5.0.9. La carpeta original `C:\Users\denis\docker\data\cassandra` sigue conservada.

Las tablas de `fixture2030_comentarios` conservan 20.012 filas cada una. `fixture2030_h12.comentarios_por_partido` conserva 2.400 y su tabla por usuario está vacía. Las huellas de todas sus columnas coinciden antes, después y tras reiniciar. El [retorno al montaje anterior](../../../Hito%206/README.md) requiere conservar cualquier escritura posterior. No se hizo ese retorno ni se borraron almacenamientos.

InfluxDB: la versión instalada 3.12.0 no permite retirar un tag de la clave existente. Se creó la tabla reducida y se conservó la original, que ya no tenía puntos consultables. No hubo puntos vigentes que copiar. La base temporal identificada en [influx-muestra-temporal.json](influx-muestra-temporal.json) recibió 20 puntos con el generador existente, se consultó mediante la API y se eliminó. La API volvió a `fixture2030_h8`. La comprobación final de catálogo confirmó que `estadio_id` permanece solo en la tabla original y ambas tablas están sin puntos consultables. Los archivos históricos y sus timestamps no se modificaron. Para volver al esquema anterior se conservan su tabla y el código anterior, sin atribuirle los puntos temporales eliminados.

## Demostración de monitoreo

La [demostración nueva](monitoreo/demostracion.json) transcurrió el **17 de noviembre de 2026, 18:05:31 a 18:11:35, UTC−03**, durante 6 min 4 s. Finalizó con `completa: true`, sin fallos inesperados, Redis recuperado con PONG y cierre de sesión 204.

| Fase | Respuestas de carga | Resultado |
| --- | --- | --- |
| Antes | 351 de estado 200 y 116 de estado 404 | Fuentes disponibles, scraping UP, MongoDB y Redis en 1, caché HIT y ninguna alerta |
| Durante | 206 de estado 200, 102 de estado 404 y 102 de estado 503 | Exporter accesible y `redis_up=0`. Ficha 200 BYPASS, sesión 503 y ambas alertas firing |
| Después | 396 de estado 200 y 130 de estado 404 | Salud y sesión correctas, `redis_up=1`, tasa 5xx en cero, alertas resueltas y caché recuperada |

Hubo **1.403 requests de carga**, con 348 respuestas 404 y 102 respuestas 503 deliberadas. Las tasas de negocio al cierre de las fases fueron aproximadamente 3,87, 3,84 y 3,90 requests/s. El P95 estimado por buckets fue 8,34, 8,59 y 8,55 ms, con ventana móvil de dos minutos. Son observaciones de esta ejecución, no una comparación controlada contra noviembre 16 ni un SLA. La gráfica incluye un pico inicial durante la acumulación de muestras.

MongoDB mostró siete conexiones en las tres observaciones. Redis mostró tres clientes antes y después, y no tuvo muestra de clientes durante su caída. Ese hueco no significa cero clientes medidos. El target del exporter siguió UP y la fuente observada pasó a cero. La operación funcional de sesión confirmó la falla.

La [captura de Grafana](02_monitoreo.jpg), obtenida el 18 de noviembre, muestra los seis paneles con el intervalo histórico visible. La [validación final](validacion-final.json) registra consultas con muestras numéricas y `ALERTS{alertstate="firing"}` en el instante `1794949760.02025`, con `FuenteNoDisponible` y `ErroresAPIAltos`, ambas con valor 1. En el cierre no había alertas pendientes ni activas.

Abrir [Grafana en el intervalo exacto](http://127.0.0.1:3000/d/fixture2030-h13?from=1794949531301&to=1794949895793). Prometheus conserva siete días, por lo que las capturas y el JSON son el respaldo cuando expiren las series. Las condiciones y responsables de las dos alertas se mantienen en el [README del Hito 13](../../README.md).

## Reproducción acotada

Desde la raíz, con las credenciales locales y los contenedores existentes iniciados según el README del Hito 13:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/salud
docker exec grupo13-hito10-api-1 python -m pytest -q -ra
python -X utf8 -m unittest discover -s 'Hito 11/tests' -v
python -X utf8 -m unittest discover -s 'Hito 13' -p test_demo.py -v
docker compose -f 'Hito 13/docker-compose.yml' config --quiet
docker exec grupo13-hito13-prometheus-1 promtool check config /etc/prometheus/prometheus.yml
docker exec grupo13-hito13-prometheus-1 promtool check rules /etc/prometheus/reglas.yml
```

Antes de una demostración nueva, construir la API desde un commit limpio y verificar los archivos con [verificar_version.py](../../verificar_version.py), como indica el README. El comando ejecutado para esta evidencia fue:

```powershell
python -X utf8 'Hito 13/demo.py' --salida 'Hito 13/evidencia/auditoria-20261117/monitoreo' --falla-redis
```

No reutilizar esa carpeta para otra ejecución. La falla afecta únicamente `grupo13-hito7-redis-1`. No hacen falta cargas generales, recreación de bases ni eliminación de volúmenes. Durante la defensa se explica la ejecución guardada, sin esperar sus seis minutos.

## Trazabilidad y límites

La [verificación del Hito 12 del 15 de noviembre](../../../Hito%2012/evidencia/verificacion-20261115/README.md) conserva `5054f7f333133228cc23c635ad4c4491a4567974` y su imagen. [h12-version-conservada.json](h12-version-conservada.json) comprueba sus 28 archivos y [h12-integridad.json](h12-integridad.json) registra la lectura de las 2.400 filas después de migrar Cassandra, con cero escrituras. La optimización de empates del cursor no cambió. No se repitió la carga ni se comparó rendimiento con el almacenamiento nuevo.

La [demostración del 16 de noviembre](../demo-20261116-final/README.md) conserva `10f3c7d37e1bb6cb48067cc256a54991ade1d7c6`, sus 1.405 requests y sus capturas. El intento incompleto previo también se conserva. Ninguna cifra de esas ejecuciones se atribuye al código auditado aquí.

No se verificaron clusters, réplicas, regiones, alta disponibilidad ni capacidad masiva. No se probó agotamiento real de memoria ni pérdida del disco. La mejora transversal más directa es definir la autoridad del estado de partido y versionar muestras compartidas, a partir de la diferencia entre Neo4j e IRIS. No se agregó sincronización distribuida. El [guion de defensa](../../defensa.md) utiliza Swagger, Grafana y estas evidencias, con 18 minutos de contenido y 2 de margen.
