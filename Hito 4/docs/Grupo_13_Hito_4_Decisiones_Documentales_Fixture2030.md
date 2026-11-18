# Grupo 13 - Hito 4: Decisiones Documentales del Fixture 2030

## Alcance del módulo

El módulo implementa exclusivamente la persistencia documental de equipos y jugadores. El diseño responde a los requisitos técnicos del Hito 4 y mantiene continuidad con las decisiones de modelado y arquitectura establecidas en los Hitos 2 y 3.

El entorno ejecutado es MongoDB Community Server 8.0 en un único contenedor local. La solución no incorpora API, frontend, Mongo Express, Mongoose, microservicios ni otros motores.

## Ambiente de ejecución

El ambiente utiliza un servicio `mongodb`, basado en MongoDB Community Server 8.0 UBI, con la base `fixture2030`, el puerto 27017 y el volumen persistente `mongodb_data`. La configuración admite valores locales de puerto y credenciales, monta `scripts/` en modo sólo lectura e incorpora un healthcheck con `mongosh`, período de gracia y política `unless-stopped`. Esta combinación ofrece una ejecución reproducible, control de disponibilidad y reinicio automático ante fallos no solicitados.

## Relación con el Hito 2

La matriz del Hito 2 asignó **equipos y jugadores** al modelo documental/MongoDB con 4,35/5. Los criterios decisivos fueron consultas de perfiles como unidad, predominio de lectura, flexibilidad de atributos deportivos y escalabilidad. Este hito materializa esa selección mediante documentos validados, consultas por identificador y atributos de negocio, índices secundarios y una carga de 64 equipos y 1.536 jugadores.

MongoDB no se utiliza para recorridos deportivos complejos. En este módulo se modela la pertenencia inmediata equipo-jugador. Las relaciones partido-jugador-equipo y los eventos permanecen fuera de su responsabilidad.

## Relación con el Hito 3

El Hito 3 definió una arquitectura políglota y separó responsabilidades. Este módulo respeta ese límite:

- MongoDB: núcleo documental estable de equipos y jugadores.
- Neo4j: relaciones de partidos, equipos, jugadores y eventos.
- Redis: sesiones, puntaje y ranking activos.
- Cassandra: comentarios, interacciones, auditoría e históricos de alto volumen.
- InfluxDB: estadísticas temporales en vivo.

La topología multirregional del Hito 3 es conceptual. Este Hito 4 sólo necesita un ambiente local funcional y por eso no instala replica set, sharding ni múltiples nodos. Una futura distribución deberá validar latencia, carga y políticas de consistencia antes de configurar esos componentes.

## Criterios de consistencia para MongoDB

Las decisiones de consistencia se expresan mediante conceptos propios de MongoDB, como réplica set, nodo primario y nodos secundarios, confirmación de escritura por mayoría y preferencias o concerns de lectura acordes con la última versión confirmada.

El ambiente actual se ejecuta como un nodo standalone, sin alta disponibilidad. En una eventual implementación distribuida, una operación oficial podría requerir la confirmación de la mayoría de las réplicas. Durante una partición, las escrituras sin mayoría deberían limitarse si se prioriza la consistencia. Estas políticas y sus métricas permanecen como decisiones pendientes.

## Alternativas de modelado

### Jugadores embebidos en equipos

Con 24 jugadores por selección, un documento de equipo seguiría lejos del límite de 16 MB y permitiría recuperar el plantel en una sola lectura. También ofrecería atomicidad de un solo documento para cambios conjuntos del equipo y su plantel.

Se descartó porque los jugadores se consultan y actualizan de forma independiente, la búsqueda global por jugador requeriría índices multikey y actualizaciones posicionales, la paginación entre jugadores sería menos natural y el crecimiento del array quedaría acoplado al documento de equipo. Embebido tampoco elimina la necesidad de mantener identificadores de jugador.

### Colecciones separadas con referencias

Cada equipo y cada jugador se representa como un documento independiente. El campo `jugadores.equipoId` establece una referencia lógica con `equipos.equipoId`. Esta estructura permite buscar y paginar jugadores directamente, actualizar sus fichas sin reescribir el documento completo del equipo y acompañar el crecimiento de los planteles. Como MongoDB no implementa claves foráneas, la integridad de la relación debe controlarse durante las escrituras y verificarse mediante `$lookup`.

### Estrategia híbrida

Se evaluó guardar jugadores separados y, además, un resumen o snapshot del plantel en el equipo. Puede acelerar pantallas de resumen, pero duplica datos y obliga a sincronizar dos representaciones en cada alta, baja o actualización. Con sólo 1.536 jugadores y consultas cubiertas por índice, no existe evidencia que justifique esa complejidad.

### Decisión

Se eligieron **colecciones separadas con referencias**. Los subdocumentos se usan sólo donde existe propiedad y ciclo de vida conjunto, por ejemplo, `sedeBase` dentro de un equipo, no para duplicar jugadores.

## Colecciones y validaciones

Ambas colecciones utilizan `$jsonSchema`, `validationLevel: strict`, `validationAction: error` y `additionalProperties: false`. La flexibilidad se mantiene dentro de un contrato explícito.

### `equipos`

Campos críticos: `_id`, `equipoId`, `codigo`, `nombre`, `confederacion`, `region`, `rankingReferencia`, `sedeBase`, `anioFundacion`, `participacionesMundiales`, `titulosMundiales`, `estado`, procedencia sintética y fechas de control.

- `confederacion`: AFC, CAF, CONCACAF, CONMEBOL, OFC o UEFA.
- `region`: África, Américas, Asia-Pacífico o Europa mediante constantes sin espacios.
- `rankingReferencia`: entero entre 1 y 250.
- `anioFundacion`: entero entre 1800 y 2030.
- participaciones y títulos: enteros no negativos con máximos razonables.
- `estado`: preseleccionado, confirmado o retirado.
- `sedeBase`: subdocumento obligatorio con ciudad y país.

### `jugadores`

Campos críticos: `_id`, `jugadorId`, `equipoId`, nombre, apellido, fecha de nacimiento, nacionalidad, posición, camiseta, pie hábil, altura y estado del plantel, procedencia sintética y fechas de control.

- `posicion`: arquero, defensor, mediocampista o delantero.
- camiseta: entero entre 1 y 99.
- altura: entero entre 150 y 220 cm.
- `estadoPlantel`: convocado, reserva, lesionado o suspendido.

Las pruebas negativas insertan documentos con campos ausentes/ranking fuera de rango y posición inválida. MongoDB los rechazó con código 121 y no quedaron residuos.

## Estrategia de identificadores

- `_id` técnico es una cadena determinista: `equipo:EQ-001` o `jugador:JUG-0001`. No cambia al recargar datos y MongoDB ya lo protege con el índice `_id_`.
- `equipoId` y `jugadorId` son identificadores de negocio legibles, estables y protegidos por índices únicos.
- `codigo` identifica de manera abreviada al equipo y también es único.
- `(equipoId, numeroCamiseta)` es único para impedir camisetas repetidas dentro del mismo plantel.

Los datos temporales usan rangos reservados (`EQ-900`, `JUG-9000`) y un `origen` específico para permitir una limpieza precisa.

## Carga y actualización

`02_seed.js` genera siempre las mismas 64 selecciones y 24 jugadores por equipo, en total 1.536. Ejecuta reemplazos con `upsert` sobre `_id`, de modo que una recarga restaura la forma canónica sin multiplicar documentos ni conservar campos accidentales. Equipos se cargan antes que jugadores y al finalizar se verifican recuentos y huérfanos.

La primera ejecución registrada produjo 64 y 1.536 `upserted`. La segunda encontró 64 y 1.536 documentos, modificó 0 y mantuvo los recuentos. Las operaciones CRUD temporales se ejecutan con filtros únicos y se limpian en `finally`.

## Consistencia e integridad

MongoDB garantiza atomicidad a nivel de documento para las actualizaciones usadas. La relación entre colecciones no tiene una restricción de clave foránea nativa. Para compensarlo:

1. El alta de jugador de demostración comprueba que el equipo exista.
2. La carga crea equipos antes de jugadores.
3. Los índices únicos evitan identificadores y camisetas duplicadas.
4. `07_verify_integrity.js` cruza las colecciones con `$lookup` y exige cero huérfanos.
5. El mismo verificador exige 24 jugadores por equipo y campos críticos presentes.
6. Al borrar datos temporales se elimina primero el jugador y luego el equipo.

El standalone local no permite demostrar confirmaciones entre réplicas. La persistencia que sí corresponde al hito se verifica reiniciando el contenedor sin quitar el volumen y repitiendo todos los controles.

## Índices y costos

| Índice | Consulta asociada y orden | Beneficio esperado | Costo aceptado |
|---|---|---|---|
| `uq_equipos_equipoId {equipoId: 1}` | Q01 y referencias `$lookup`. Igualdad por ID. | Unicidad y acceso directo. | Una clave por equipo y validación en escritura. |
| `uq_equipos_codigo {codigo: 1}` | Identificación abreviada y control de duplicados. | Código inequívoco. | Una clave por equipo. |
| `idx_equipos_confederacion_ranking {confederacion: 1, rankingReferencia: 1, equipoId: 1}` | Q03/Q09: igualdad, luego rango/orden, finalmente desempate. | Evita ordenar fuera del índice y estabiliza páginas. | Espacio y actualización ante cambios de ranking. |
| `uq_jugadores_jugadorId {jugadorId: 1}` | Q02 y CRUD por ID. | Unicidad y acceso directo. | Una clave por jugador. |
| `uq_jugadores_equipo_camiseta {equipoId: 1, numeroCamiseta: 1}` | Integridad del plantel. | Impide duplicar camisetas dentro de un equipo. | Control adicional en altas/cambios. |
| `idx_jugadores_equipo_nombre {equipoId: 1, apellido: 1, nombre: 1, jugadorId: 1}` | Q06/Q07 y `$lookup`: equipo por igualdad y orden estable del plantel. | Filtra, ordena y pagina sin scan global. | Índice compuesto más ancho. Afecta cambios de equipo/nombre. |
| `idx_jugadores_posicion_altura {posicion: 1, alturaCm: -1, jugadorId: 1}` | Q04: igualdad, rango/orden descendente y desempate. | Jugadores ordenados por altura y posición sin ordenamiento global. | Se actualiza al corregir la altura. |
| `idx_jugadores_nacionalidad_altura {nacionalidadCodigo: 1, alturaCm: -1, jugadorId: 1}` | P01: igualdad, rango/orden y desempate. | Reduce documentos examinados y elimina `COLLSCAN`. | Es un índice no esencial compuesto por tres campos que incrementa el costo de las escrituras. Puede eliminarse si la consulta P01 no se ejecuta con frecuencia. |

No se creó índice para `esDatoSintetico`: todos los documentos canónicos comparten ese valor, por lo que es poco selectivo.

### Resultado real de rendimiento

P01 devolvió 15 documentos antes y después:

- antes: etapa raíz `SORT`. Plan con `COLLSCAN`. 1.536 documentos y 0 claves examinados.
- después: etapa raíz `PROJECTION_SIMPLE`. Plan con `FETCH` e `IXSCAN`. 15 documentos y 15 claves examinados.
- reducción: 1.521 documentos examinados.
- tiempo informado: 0 ms en ambos casos.

No se atribuye una mejora de tiempo porque MongoDB redondeó ambas ejecuciones a 0 ms. La mejora demostrada es de trabajo examinado y plan de acceso.

## Tabla de decisiones solicitada

| Decisión | Alternativas consideradas | Elección | Justificación | Impacto esperado |
|---|---|---|---|---|
| Relación equipo-jugador | Embedding, referencias, híbrida. | Referencia `jugadores.equipoId`. | Actualización independiente, consulta global, orden y paginación de 1.536 jugadores. | Mantiene documentos de tamaño acotado y exige verificar explícitamente que no existan jugadores huérfanos. |
| Validación documental | Sin esquema, validación parcial, `$jsonSchema` estricto. | `$jsonSchema` estricto y rechazo de errores. | Evita tipos inválidos, campos críticos ausentes y valores fuera de dominio. | Datos más confiables. Cambios de esquema deben planificarse. |
| Estrategia de identificadores | Sólo ObjectId, IDs de negocio, ambos. | `_id` técnico determinista más IDs de negocio únicos. | Estabilidad entre recargas e integración legible. | Upserts idempotentes y búsquedas inequívocas. Leve redundancia. |
| Índices principales | Sólo `_id`, índices simples, índices compuestos por patrón. | Únicos de identidad más compuestos Q03/Q04/Q06/Q07/P01. | Igualdad primero, rango/orden después y desempate final. | Menos scans/sorts. Mayor almacenamiento y costo de escritura. |
| Carga y actualización | `insertMany` ciego, init de una sola vez, `upsert` manual repetible. | Reemplazos deterministas con `upsert`. | Puede ejecutarse con volumen nuevo o existente sin duplicar. | La recarga restaura el conjunto de datos canónico y reemplaza los cambios manuales realizados sobre sus identificadores. |

## Trade-offs

- Referenciar facilita independencia y paginación, pero obliga a controlar integridad fuera del validador de una colección.
- `additionalProperties: false` protege calidad, pero exige cambiar el validador antes de agregar atributos.
- Los índices compuestos aceleran lecturas alineadas, a cambio de almacenamiento y trabajo extra en escrituras.
- El reemplazo idempotente hace reproducible el dataset, pero una recarga intencionalmente revierte modificaciones manuales de entidades canónicas.
- El dataset sintético permite probar volumen y distribución, pero no valida calidad ni disponibilidad de información deportiva oficial.

## Limitaciones y decisiones pendientes

- Sustituir los datos sintéticos sólo cuando exista una fuente oficial y acordada de participantes/planteles 2030.
- Definir una política para gestionar los cambios de plantel y conservar su historial. El alcance de este hito contempla únicamente el estado actual.
- Decidir si una interfaz futura usará paginación por cursor en lugar de `skip/limit` para volúmenes mucho mayores.
- Medir carga real antes de conservar o quitar el índice P01.
- El diseño y las pruebas de réplica set, concerns de lectura y escritura, y un eventual sharding quedan reservados para un hito que requiera esas capacidades. Estos componentes no forman parte del alcance actual.
- Coordinar con Neo4j el identificador estable compartido sin trasladar al documento las relaciones complejas de partidos y eventos.

## Matriz de trazabilidad

Los comandos se ejecutan desde `Hito 4/`. `MONGO` representa la invocación autenticada de `mongosh` indicada en el [README](../README.md), que toma las credenciales del entorno del contenedor. Sustituir únicamente la ruta del archivo para cada operación.

| Requisito | Archivo que lo implementa | Comando que lo verifica | Evidencia generada | Estado |
|---|---|---|---|---|
| RF1 | `docker-compose.yml` | `docker compose config --quiet` y `docker compose up -d` | `01_docker_compose_config.txt`, `02_inicio_y_estado_contenedor.txt` | Cumplido |
| RF2 | `docker-compose.yml` (volumen `mongodb_data`) | `docker compose restart mongodb` + verificador | `13_persistencia_despues_reinicio.txt` | Cumplido |
| RF3 | `scripts/init/01_collections.js` | `MONGO /workspace/scripts/init/01_collections.js` | `04_inicializacion_e_indices.txt` | Cumplido |
| RF4 | `scripts/data/02_seed.js` | `MONGO /workspace/scripts/data/02_seed.js` | `05_carga_inicial.txt` | Cumplido: 64 |
| RF5 | `scripts/data/02_seed.js` | `MONGO /workspace/scripts/verification/07_verify_integrity.js` | `07_integridad_validadores_indices.txt` | Cumplido: 1.536 |
| RF6 | Este documento y `jugadores.equipoId` | Q10/Q11 en `05_queries.js` | `10_consultas_y_agregaciones.txt` | Cumplido |
| RF7 | `scripts/validations/02_validators.js` | `MONGO /workspace/scripts/verification/08_test_validation.js` | `08_rechazo_datos_invalidos.txt` | Cumplido |
| RF8 | `scripts/data/02_seed.js` | Ejecutar seed dos veces | `05_carga_inicial.txt`, `06_segunda_carga_idempotente.txt` | Cumplido |
| RF9 | `scripts/operations/04_demo_crud.js` | `MONGO /workspace/scripts/operations/04_demo_crud.js` | `09_operaciones_crud_controladas.txt` | Cumplido |
| RF10 | `scripts/queries/05_queries.js` Q01-Q07 | `MONGO /workspace/scripts/queries/05_queries.js` | `10_consultas_y_agregaciones.txt` | Cumplido |
| RF11 | `scripts/queries/05_queries.js` Q08-Q12 | Mismo comando de consultas | `10_consultas_y_agregaciones.txt` | Cumplido |
| RF12 | `scripts/indexes/03_indexes.js`, `scripts/performance/06_compare_index.js` | `MONGO /workspace/scripts/performance/06_compare_index.js` | `11_comparacion_rendimiento_indice.txt` | Cumplido |
| RF13 | `scripts/verification/generar_evidencias.ps1` y `.sh` | `./scripts/verification/generar_evidencias.ps1` | `evidencias/00...14_*.txt` | Cumplido |

### Matriz de trazabilidad - requisitos no funcionales

| Requisito | Archivo que lo implementa | Comando que lo verifica | Evidencia generada | Estado |
|---|---|---|---|---|
| RNF1 | `README.md`, generadores de evidencia | Seguir “Inicio desde cero” o ejecutar generador | `00_resumen_ejecucion.txt` | Cumplido |
| RNF2 | `scripts/data/02_seed.js` | Verificador integral | `12_integridad_canonica_final.txt` | Cumplido: 64/1.536 |
| RNF3 | Validadores, índices únicos y verificador | Verificador integral | `07_integridad_validadores_indices.txt`, `12_integridad_canonica_final.txt` | Cumplido: ceros |
| RNF4 | Índices y `explain("executionStats")` | Comparador P01 | `11_comparacion_rendimiento_indice.txt` | Cumplido |
| RNF5 | Este documento | Revisión de trazabilidad con los Hitos 2 y 3 | Documento versionado | Cumplido |
| RNF6 | Separación `init/validations/data/indexes/operations/queries/performance/verification/docs/evidencias` | `tree`/listado del directorio | Árbol en `README.md` | Cumplido |
| RNF7 | Compose, volumen nombrado y scripts `mongosh` en contenedor | `docker compose config` | `01_docker_compose_config.txt` | Cumplido dentro de hosts compatibles con Docker |
| RNF8 | Generador determinista y ejecución automatizada | Generador integral de evidencias | `00_resumen_ejecucion.txt` | Cumplido por automatización. No requiere carga manual |

## Resultados de verificación

Las pruebas de ejecución verificaron la disponibilidad de MongoDB, la persistencia posterior al reinicio y la integridad del conjunto de datos: 64 equipos, 1.536 jugadores, sin identificadores duplicados, jugadores huérfanos, planteles con una cantidad distinta de 24 jugadores ni campos críticos ausentes. Los resultados detallados se encuentran registrados en los archivos de evidencia del proyecto.
