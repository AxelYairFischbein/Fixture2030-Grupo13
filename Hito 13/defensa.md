# Defensa técnica - Fixture 2030, Grupo 13

Duración prevista de 18 minutos y 2 minutos de margen. Participan los dos integrantes como A y B. Asignar esos roles antes de exponer y ensayar el relevo. Ambos deben poder explicar cualquiera de las bases. Recursos visuales: repositorio, Swagger, Grafana y evidencia guardada.

## Guion y reparto

| Tiempo | Responsable | Qué explicar y mostrar |
| --- | --- | --- |
| 0:00–1:00 | A | Problema, patrones de acceso y alcance local. Diferenciar equipos, relaciones, comentarios, sesiones, estadísticas y actas |
| 1:00–4:00 | A | MongoDB y Redis desde Swagger. Listado, ficha cacheada y sesión. B explica la degradación BYPASS y el cierre |
| 4:00–6:00 | B | Neo4j. Partido con relaciones y agenda. A contrasta la muestra independiente de IRIS |
| 6:00–8:00 | B | Cassandra. Partición, cursor, orden y evidencia de la optimización. A explica persistencia y respaldo |
| 8:00–10:00 | A | IRIS e InfluxDB. Acta, validación encapsulada y consulta temporal con evidencia preparada. B explica retención y agregación |
| 10:00–12:30 | A y B | Distribución propuesta, consistencia y CAP. Recorrer las seis bases y distinguir propuestas del nodo ejecutado |
| 12:30–16:30 | B, con apoyo de A | Grafana con el intervalo guardado. Endpoints, fuentes, respuestas, carga, alertas y recuperación. A interpreta P95 y límites |
| 16:30–18:00 | A y B | Resultados, migraciones, límites, mejora transversal y cierre |
| 18:00–20:00 | Ambos | Margen para preguntas o demoras |

Son 18 minutos de contenido. El reparto es orientativo y ambos integrantes deben poder explicar las seis bases y continuar el recorrido del otro. Ensayar con las pestañas y evidencias ya abiertas.

## Qué problema resuelve cada estructura

| Base | Estructura implementada y acceso | Trade-off y evidencia a mostrar |
| --- | --- | --- |
| MongoDB | Colecciones `equipos` y `jugadores`. Ficha de equipo, plantel filtrado y paginado. Identidad, posición, altura y estado del plantel. Índices únicos y compuestos, validación de documentos | Documento flexible con índices para accesos definidos. Separar jugadores evita crecer el documento del equipo sin límite, pero exige referencias y consultas. Mostrar [índices](../Hito%204/scripts/indexes/03_indexes.js) y `/equipos/EQ-001/jugadores` |
| Neo4j | Nodos Equipo, Jugador, Partido, Estadio y Evento. Relaciones para participación, pertenencia, sede e involucrados. Recorrido de partido y agenda con rival | Las relaciones son explícitas y fáciles de recorrer. Los recorridos profundos pueden expandirse mucho. La API limita eventos y parametriza consultas. Mostrar [adaptador](../Hito%2010/app/adapters/neo4j_partidos.py) y `/partidos/PAR-001` |
| Cassandra | `comentarios_por_partido`, partición `(partido_id, minuto, segmento)`, clustering `creado_en DESC, comentario_id ASC`. Tabla por usuario con partición `(usuario_id, dia)` | Optimiza consultas conocidas y escritura distribuible. Duplica datos y exige mantener tablas. Cuatro segmentos dispersan una ventana, pero la lectura combina particiones. Mostrar [CQL](../Hito%206/scripts/esquema.cql) y cursor paginado |
| Redis | Hashes de sesión con TTL, ficha cacheada y reserva de idempotencia. Prefijo `fixture2030:h10`. `SET NX` y finalización controlan repetición de comentarios | Lecturas rápidas y expiración simple a cambio de memoria limitada y estados temporales. `noeviction` puede rechazar escrituras al alcanzar 64 MiB. No elimina claves por presión de memoria. Los TTL siguen venciendo. Una sesión nueva falla con 503, mientras una ficha puede continuar con 200 BYPASS si falla la escritura de caché. La ficha usa cache-aside y permite BYPASS, las sesiones requieren Redis |
| InfluxDB | `estadisticas_equipo_v2`, tags de partido y equipo, campos numéricos y tiempo. El estadio se retiró porque depende del partido y ningún acceso lo necesita. Ventanas acotadas y agregación por intervalos | Retención de siete días limita almacenamiento y elimina historia. Cardinalidad de tags y precisión temporal afectan costo. La API devuelve una lista vacía válida si no queda información. Mostrar [modelo](../Hito%208/docs/modelo_multidimensional.md) y `/partidos/PAR-001/estadisticas` |
| IRIS | `Persona` con herencia en `Jugador` y `Arbitro`, `Partido` persistente con hijos `Evento`, referencias e índice por código. Lectura de objeto y SQL sobre los mismos datos | Navegación y validación de dominio con guardado del árbol. Mayor acoplamiento a clases y reglas. Mostrar [Partido](../Hito%209/scripts/FixtureH9.Partido.cls) y `/actas/PAR-001` |

Explicar la carga como preparación de muestras sintéticas, separada de las consultas de la demostración. No ejecutar las cargas generales durante la defensa. Los modelos responden a patrones distintos, pero mantener seis productos agrega configuración, permisos, respaldos y diagnóstico. No se afirma que una base relacional sea incapaz de resolver el problema.

## Distribución, consistencia y CAP

Lo ejecutado es un nodo por producto en el mismo Docker Desktop. Las carpetas y volúmenes conservan datos tras detener e iniciar contenedores. Persistencia local no equivale a réplica ni alta disponibilidad. La falla ensayada es la detención de Redis, no una partición de red ni pérdida de una región.

| Base | Situación concreta y propuesta a defender |
| --- | --- |
| MongoDB | Instancia única. Un replica set y, si la carga lo justificara, sharding por una clave elegida según acceso serían pasos posteriores. Lectura de una réplica puede estar atrasada. Confirmaciones por mayoría priorizan consistencia de escrituras y pueden perder disponibilidad sin mayoría |
| Neo4j | Grafo local con restricciones. Réplicas de lectura no resuelven automáticamente el costo de recorridos ni distribuyen cualquier grafo. Un despliegue con consenso necesitaría mayoría para escrituras. No se verificó ese comportamiento aquí |
| Cassandra | Claves de partición y cuatro segmentos implementados. `SimpleStrategy`, factor de replicación 1 y consistencia ONE en la ejecución. No hay otra copia que responda ante caída. Para varios centros de datos se propondría `NetworkTopologyStrategy` y decidir RF y niveles de lectura/escritura. Con RF=3, R=2 y W=2 hay intersección, a costo de disponibilidad cuando faltan réplicas. No se midió |
| Redis | Un nodo, AOF `everysec`, sin réplicas ni Sentinel. Puede perder escrituras recientes ante fallo abrupto. Caché tolera reconstrucción desde MongoDB. Sesiones e idempotencia requieren decidir qué pérdida es aceptable antes de proponer replicación asíncrona o partición por claves |
| InfluxDB | Un nodo de Core, almacenamiento de objetos sobre archivos locales y retención. Particionar lógica temporal y agregar no significa tener un cluster distribuido. Se acepta falta de puntos vencidos, pero no se confunde con indisponibilidad del motor |
| IRIS | Un nodo con reglas y atomicidad del árbol en su base. Mirroring sería una propuesta adicional a evaluar. Una transacción IRIS no incluye los cambios en Neo4j ni en las otras fuentes |

N/R/W explícito se utiliza aquí solo al explicar Cassandra. MongoDB, Neo4j y Redis tienen mecanismos propios y no se describen con ese mismo esquema de quórum.

CAP describe decisiones ante una partición de red entre nodos. No significa elegir dos letras para todo el sistema en cualquier situación. Para actas y transiciones conviene preservar reglas y evitar dos estados oficiales divergentes. Una caché o estadística puede tolerar atraso según el negocio. Esa tolerancia debe definirse por operación. No existe transacción distribuida que vuelva atómica toda la plataforma.

PAR-001 FINALIZADO en el grafo y PENDIENTE en IRIS no es evidencia de consistencia eventual ni de una réplica atrasada. Son muestras independientes, con eventos distintos y sin mecanismo de sincronización. IRIS exige PENDIENTE en su muestra canónica. No cambiar ese estado para hacer coincidir las pantallas. Proponer autoridad y versionado de muestras como mejora de integración.

## Recorridos concretos

Abrir Swagger en <http://127.0.0.1:8000/docs>. En cada operación usar **Try it out**, completar los parámetros y ejecutar. Los prefijos de las rutas siguientes son `/api/v1`.

| Bloque | Request y resultado esperado |
| --- | --- |
| Salud previa, fuera del tiempo de exposición | `GET /salud` → 200 con seis fuentes `ok`. Si falla, utilizar la evidencia guardada y explicar cuál fuente no respondió |
| MongoDB | `GET /equipos?confederacion=UEFA&pagina=2&tamanio=5` → cinco equipos y total 10. `GET /equipos/EQ-001/jugadores?posicion=ARQUERO` → camisetas 1, 2 y 3, con estado del plantel y sin estadísticas internacionales |
| Caché | Ejecutar dos veces `GET /equipos/EQ-001` y mostrar `X-Cache` y `meta.fuentes`. Puede ser HIT desde el primer acceso si la clave sigue vigente. No afirmar MISS sin observarlo |
| Sesión temporal | `POST /sesiones` con `{"usuarioId":"USR-00001","rol":"lector"}` → 201. Copiar únicamente para la prueba el `sesionId`, consultarlo con GET y cerrarlo con `DELETE /sesiones/{sesionId}` → 204. Otra lectura devuelve 404. No guardar el identificador en capturas |
| Neo4j | `GET /partidos/PAR-001?limiteEventos=2` → equipos, estadio y dos eventos. `GET /equipos/EQ-001/partidos` → agenda con rivales EQ-002 y EQ-003. Si falta tiempo, mostrar solo el partido |
| Cassandra | `GET /partidos/PAR-001/comentarios?desde=2030-06-10T18:00:30Z&hasta=2030-06-10T18:02:10Z&limite=3` → tres filas y `meta.paginacion.siguienteCursor`. Copiar ese cursor al parámetro `cursor` para la segunda página. Explicar el orden y las 12 particiones de esta ventana |
| IRIS | `GET /actas/PAR-001` → PENDIENTE, árbitro y dos eventos. Mostrar [objetos y SQL](evidencia/auditoria-20261117/iris-objetos-sql.txt), con rechazo de un hijo inválido y transición prohibida sobre datos temporales |
| InfluxDB | `GET /partidos/PAR-001/estadisticas?intervalo=1m` → 200, posiblemente sin puntos por retención. Mostrar [la agregación con datos](evidencia/auditoria-20261117/influx-muestra-temporal.json), sus dos equipos y cinco intervalos por equipo. La base temporal ya fue eliminada |

Las requests principales son MongoDB y Redis. Neo4j y la segunda página de Cassandra completan el recorrido breve. IRIS e InfluxDB se pueden explicar con una lectura y evidencia preparada, sin cargar muestras durante la exposición. La consola existente es opcional y muestra los mismos endpoints.

En IRIS señalar `Persona`, sus subclases, la relación padre e hijo de `Partido` y `Evento`, `%Save()` y `CambiarEstado()`. Los índices generan búsquedas por código usadas por la API. Las validaciones y los helpers se mantienen por esas dependencias, pero no se recorre toda la demo.

## Monitoreo, falla y resultados

Abrir [Grafana en el intervalo de la auditoría](http://127.0.0.1:3000/d/fixture2030-h13?from=1794949531301&to=1794949895793), del 17 de noviembre de 18:05:31 a 18:11:35 UTC−03. La ejecución duró 6 min 4 s y se explica en cuatro minutos usando los resultados guardados. No iniciar ni esperar una demostración completa durante la exposición.

1. Señalar los endpoints de métricas: los tres permanecieron accesibles. Compararlos con el panel de bases: MongoDB siguió en 1 y Redis pasó de 1 a 0 y volvió a 1.
2. Relacionar esa caída con la API: ficha 200 BYPASS desde MongoDB y sesión 503. HTTP 200 en una lectura no demuestra que toda la plataforma esté sana.
3. Mostrar volumen, errores y latencia. Se emitieron 1.403 requests de carga, con 348 respuestas 404 y 102 respuestas 503 deliberadas. No hubo errores inesperados. P95 estima mediante buckets un percentil de la ventana de dos minutos, no el promedio del 95 % de las solicitudes. Al cierre de las tres fases fue 8,34, 8,59 y 8,55 ms.
4. Explicar conexiones: MongoDB mostró siete en las observaciones. Redis tuvo tres clientes antes y después, y un hueco durante la caída. El hueco no es una medición de cero.
5. Mostrar ambas alertas firing en el [resultado](evidencia/auditoria-20261117/monitoreo/demostracion.json), dentro de `fases.durante.observacion.alertas`. En [Prometheus](http://127.0.0.1:9090/query), consultar `ALERTS{alertstate="firing"} @ 1794949760.02025` en Table. Deben verse `FuenteNoDisponible` y `ErroresAPIAltos`, ambas con valor 1. Es una consulta histórica, no el estado actual.
6. Mostrar `fases.despues`, Redis recuperado, salud y sesión correctas, tasa 5xx en cero y alertas resueltas. Las ventanas y duraciones explican por qué las alertas tardan en resolverse. El cierre temporal fue 204.

Las reglas evalúan cada 15 segundos. Indisponibilidad exige 30 segundos. Errores elevados exige más de 5 % de 5xx y al menos 20 requests en dos minutos, sostenido un minuto. Los valores corresponden al entorno de prueba y no son un SLA demostrado. No hay notificaciones externas.

Para Cassandra, mostrar el volumen nombrado y el respaldo conservado, con huellas iguales después del reinicio. Para Hito 12 usar la [verificación identificada](../Hito%2012/evidencia/verificacion-20261115/README.md) de `5054f7f333133228cc23c635ad4c4491a4567974`. La auditoría repitió solo la lectura de 2.400 filas, con cero escrituras, en la misma imagen. No volvió a medir rendimiento ni comparó tiempos del nuevo almacenamiento. Los históricos no mostraron una mejora uniforme de P95 y P99.

## Alternativa si el entorno no responde

Mantener abierto el [informe de auditoría](evidencia/auditoria-20261117/README.md). Usar la [captura de la consola](evidencia/auditoria-20261117/01_interfaz.jpg), el [dashboard guardado](evidencia/auditoria-20261117/02_monitoreo.jpg), las [respuestas de origen y API](evidencia/auditoria-20261117/origen-y-api.json) y la [demostración completa](evidencia/auditoria-20261117/monitoreo/demostracion.json). Mostrar sus fechas y el commit `ed49e3fcb1dad4f1767dc17dbb0c87753e9cc4aa`.

Prometheus conserva siete días de series. Si ya expiraron o el entorno no responde, las capturas y JSON permiten explicar lo observado. Para IRIS e InfluxDB usar sus archivos enlazados arriba y para paginación la evidencia de Hito 12. No improvisar recargas, recreaciones ni cambios de estado en PAR-001. La [ejecución del 16 de noviembre](evidencia/demo-20261116-final/README.md) es un antecedente de otra versión, no una captura del código auditado.

## Cierre y preguntas

La solución relaciona cada patrón de acceso con un modelo concreto y permite identificar fallas de fuente sin perder la procedencia de las respuestas. Su límite principal es que integra muestras y servicios locales, no una plataforma mundial validada. La prioridad de mejora es acordar la autoridad del estado del partido y mantener muestras coherentes. Luego medir degradaciones como BYPASS y evaluar distribución con una carga y un objetivo definidos.

Preguntas para ensayar: qué cambia si Redis falla, qué garantiza un target UP, por qué una serie vacía no siempre es error, cómo se identifica la versión medida, qué costo introduce consultar cuatro segmentos y qué evidencia falta antes de prometer alta disponibilidad.
