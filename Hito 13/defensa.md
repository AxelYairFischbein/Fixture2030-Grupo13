# Defensa técnica - Fixture 2030, Grupo 13

Duración prevista de 18 minutos y 2 minutos de margen. Participan los dos integrantes como A y B. Asignar esos roles antes de exponer y ensayar el relevo. Ambos deben poder explicar cualquiera de las bases. Recursos visuales: repositorio, Swagger, Grafana y evidencia guardada.

## Guion y reparto

| Tiempo | Responsable | Qué explicar y mostrar |
| --- | --- | --- |
| 0:00–1:30 | A | Problema y alcance. Fixture con equipos, planteles, relaciones entre partidos, comentarios, sesiones, estadísticas y actas. Diferentes accesos justifican estructuras distintas |
| 1:30–5:00 | A | MongoDB, Neo4j e IRIS. Mostrar un esquema o consulta por base y la diferencia de PAR-001 |
| 5:00–8:30 | B | Cassandra, Redis e InfluxDB. Mostrar claves de partición, TTL y consulta temporal |
| 8:30–11:00 | A | Distribución propuesta, replicación, consistencia y CAP. Separar diseño de ejecución en un nodo |
| 11:00–13:30 | B | Dos recorridos mediante Swagger y respuestas con `meta.fuentes` |
| 13:30–17:00 | B, con apoyo de A | Dashboard, carga breve, falla de Redis y recuperación. A explica la trazabilidad y el alcance del Hito 12 |
| 17:00–18:00 | A y B | Limitaciones, mejora transversal y cierre |
| 18:00–20:00 | Ambos | Margen para preguntas o demoras |

## Qué problema resuelve cada estructura

| Base | Estructura implementada y acceso | Trade-off y evidencia a mostrar |
| --- | --- | --- |
| MongoDB | Colecciones `equipos` y `jugadores`. Ficha de equipo, plantel filtrado y paginado. IDs e índices únicos y compuestos, validación de documentos | Documento flexible con índices para accesos definidos. Separar jugadores evita crecer el documento del equipo sin límite, pero exige referencias y consultas. Mostrar [índices](../Hito%204/scripts/indexes/03_indexes.js) y `/equipos/EQ-001/jugadores` |
| Neo4j | Nodos Equipo, Jugador, Partido, Estadio y Evento. Relaciones para participación, pertenencia, sede e involucrados. Recorrido de partido y agenda con rival | Las relaciones son explícitas y fáciles de recorrer. Los recorridos profundos pueden expandirse mucho. La API limita eventos y parametriza consultas. Mostrar [adaptador](../Hito%2010/app/adapters/neo4j_partidos.py) y `/partidos/PAR-001` |
| Cassandra | `comentarios_por_partido`, partición `(partido_id, minuto, segmento)`, clustering `creado_en DESC, comentario_id ASC`. Tabla por usuario con partición `(usuario_id, dia)` | Optimiza consultas conocidas y escritura distribuible. Duplica datos y exige mantener tablas. Cuatro segmentos dispersan una ventana, pero la lectura combina particiones. Mostrar [CQL](../Hito%206/scripts/esquema.cql) y cursor paginado |
| Redis | Hashes de sesión con TTL, ficha cacheada y reserva de idempotencia. Prefijo `fixture2030:h10`. `SET NX` y finalización controlan repetición de comentarios | Lecturas rápidas y expiración simple a cambio de memoria limitada y estados temporales. `noeviction` puede rechazar escrituras al alcanzar 64 MiB. La ficha usa cache-aside y permite BYPASS, las sesiones requieren Redis |
| InfluxDB | `estadisticas_equipo`, tags de partido, equipo y estadio, campos numéricos y tiempo. Ventanas acotadas y agregación por intervalos | Retención de siete días limita almacenamiento y elimina historia. Cardinalidad de tags y precisión temporal afectan costo. La API devuelve una lista vacía válida si no queda información. Mostrar [modelo](../Hito%208/docs/modelo_multidimensional.md) y `/partidos/PAR-001/estadisticas` |
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

CAP describe decisiones ante una partición de red entre nodos. No significa elegir dos letras para todo el sistema en cualquier situación. Para actas y transiciones conviene preservar reglas y evitar dos estados oficiales divergentes. Una caché o estadística puede tolerar atraso según el negocio. Esa tolerancia debe definirse por operación. No existe transacción distribuida que vuelva atómica toda la plataforma.

PAR-001 FINALIZADO en el grafo y PENDIENTE en IRIS no es evidencia de consistencia eventual ni de una réplica atrasada. Son muestras independientes, con eventos distintos y sin mecanismo de sincronización. IRIS exige PENDIENTE en su muestra canónica. No cambiar ese estado para hacer coincidir las pantallas. Proponer autoridad y versionado de muestras como mejora de integración.

## Recorridos de la API

Primer recorrido, equipos y caché:

1. Consultar `GET /api/v1/equipos?tamanio=5`, que usa MongoDB.
2. Consultar dos veces `GET /api/v1/equipos/EQ-001`. Mostrar `X-Cache` y `meta.fuentes`. Puede ser HIT desde el primer acceso si la caché ya estaba vigente. No afirmar MISS sin observarlo.
3. Mostrar plantel o agenda desde Swagger si queda tiempo. Relacionar el acceso con documentos o relaciones.

Segundo recorrido, partido y comentarios:

1. Consultar `GET /api/v1/partidos/PAR-001` y explicar las relaciones de Neo4j.
2. Consultar `/api/v1/partidos/PAR-001/comentarios?desde=2030-06-10T18:00:30Z&hasta=2030-06-10T18:02:10Z&limite=3`. Copiar `siguienteCursor` para otra página.
3. Mostrar que la ventana está acotada y que el orden combina timestamp e ID. Un cursor restringe la búsqueda de empates a su minuto y conserva los cuatro segmentos.

Usar `/actas/PAR-001` e InfluxDB como respuestas guardadas si el tiempo es corto. No ejecutar cambios de estado en actas canónicas ni publicar comentarios durante estos recorridos.

## Monitoreo, falla y resultados

Usar el [resultado completo guardado](evidencia/demo-20261116-final/README.md) y abrir Grafana en su rango absoluto. La ejecución duró 6 min 4 s y la exposición reserva 3 min 30 s para explicarla. Mostrar sus seis paneles y una request funcional. Si se decide repetir en vivo, iniciar la carga antes del bloque de monitoreo para acumular dos minutos de muestras. Las esperas acotadas pueden extender el recorrido hasta unos once minutos, más el cierre de requests en curso. No esperar toda la ejecución durante ese bloque.

Con Redis detenido, distinguir el endpoint del exporter que sigue UP de `redis_up=0`. La sesión responde 503 y la ficha puede responder 200 con BYPASS desde MongoDB. Esto muestra por qué HTTP 200 no basta para detectar una degradación de caché. Tras iniciar el mismo contenedor, comprobar sesión, salud y `redis_up=1`. Las tasas usan dos minutos de historia y tardan en bajar, aunque la fuente ya se haya recuperado.

Explicar contador, gauge e histograma mediante una métrica real. Se emitieron 1.405 requests de carga, con 349 respuestas 404 y 102 respuestas 503 deliberadas. No hubo errores inesperados. Las dos alertas llegaron a `firing` y luego se resolvieron. La sesión temporal cerró con 204. P95 es una estimación por buckets y fue de aproximadamente 9 a 10 ms en las observaciones. No aumentó durante esta falla porque el error se respondió rápidamente. Por eso se necesitan las señales de disponibilidad y errores además de latencia. Las alertas tienen condiciones, duración y responsables documentados. No se enviaron notificaciones externas.

Para el Hito 12 mostrar la nueva verificación contra `5054f7f333133228cc23c635ad4c4491a4567974`, su imagen y comparación de archivos, las 2.400 filas verificadas antes y después y la paginación íntegra. Es una ejecución nueva. La comparación histórica no mostró mejora uniforme de P95 y P99. No comparar sus cifras con la nueva corrida como si el entorno fuera idéntico.

## Alternativa si el entorno no responde

Abrir el [resumen de la ejecución](evidencia/demo-20261116-final/README.md), la captura de targets y su `demostracion.json`. Mostrar en orden `fases.antes`, `fases.durante` y `fases.despues`, con sus consultas, respuestas y alertas. La sección `version` identifica el código ejecutado. El dashboard y la captura de alertas están pendientes de guardar según las instrucciones del resumen. Hasta completarlas, no presentarlas como evidencia obtenida. Los JSON permiten explicar los resultados aunque Grafana no responda o sus series hayan vencido.

Para la paginación e integridad usar la evidencia independiente del Hito 12. Explicar que se muestran resultados anteriores identificados, no una prueba en vivo. No improvisar recargas de datos ni recrear bases para salvar una demostración.

## Cierre y preguntas

La solución relaciona cada patrón de acceso con un modelo concreto y permite identificar fallas de fuente sin perder la procedencia de las respuestas. Su límite principal es que integra muestras y servicios locales, no una plataforma mundial validada. La prioridad de mejora es acordar la autoridad del estado del partido y mantener muestras coherentes. Luego medir degradaciones como BYPASS y evaluar distribución con una carga y un objetivo definidos.

Preguntas para ensayar: qué cambia si Redis falla, qué garantiza un target UP, por qué una serie vacía no siempre es error, cómo se identifica la versión medida, qué costo introduce consultar cuatro segmentos y qué evidencia falta antes de prometer alta disponibilidad.
