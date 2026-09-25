# Modelo tabular

## Keyspace y consistencia

`fixture2030_comentarios` usa `SimpleStrategy` con factor de replicación 1. Cada partición tiene una sola réplica. Las operaciones usan `CONSISTENCY ONE`, por lo que requieren la respuesta de esa réplica. Si el nodo falla, el módulo queda sin servicio. El montaje persistente conserva archivos al reiniciar, pero no aporta redundancia ni reemplaza un respaldo.

Esta configuración de un solo nodo no ofrece alta disponibilidad. Un cluster con varios nodos o centros de datos puede distribuir varias réplicas. En ese caso habría que elegir una estrategia como `NetworkTopologyStrategy` y ajustar la consistencia y la recuperación ante fallos.

## Tablas y claves

| Tabla | Consulta que justifica su existencia | Clave primaria completa |
|---|---|---|
| `comentarios_por_partido` | Q1 recientes y Q2 ventana de un partido | `((partido_id, minuto, segmento), creado_en, comentario_id)` |
| `comentarios_por_usuario` | Q3 historial diario por autor | `((usuario_id, dia), creado_en, comentario_id)` |

La tabla principal particiona por `(partido_id, minuto, segmento)` y la secundaria por `(usuario_id, dia)`. Ambas ordenan por `creado_en DESC, comentario_id ASC`. El identificador permite desempatar comentarios del mismo milisegundo y debe conservar siempre su partido, autor y fecha. Cassandra garantiza la unicidad de la clave completa, no del identificador por separado.

## Columnas de ambas representaciones

| Columna | Tipo CQL | Descripción |
|---|---|---|
| `comentario_id` | `text` | Identificador estable, como `MUESTRA-001` o `MASIVO-000000000001` |
| `partido_id` | `text` | Referencia sintética a `PAR-001` ... `PAR-064` |
| `usuario_id` | `text` | Autor, sin almacenar información personal |
| `creado_en` | `timestamp` | Instante UTC con precisión de milisegundos |
| `minuto` | `timestamp` | `creado_en` truncado al inicio del minuto UTC |
| `segmento` | `tinyint` | `CRC32(comentario_id UTF-8) módulo 4`, de 0 a 3 |
| `dia` | `date` | Día UTC de `creado_en` |
| `contenido` | `text` | Mensaje de hasta 280 caracteres, controlado al generar los datos |
| `estado` | `text` | `visible`, `pendiente` u `oculto` |
| `likes` | `int` | Cantidad absoluta no negativa, sin incremento concurrente |

Cada tabla almacena las diez columnas. Las claves de la otra representación se guardan para poder actualizar o borrar ambas después de una lectura. No se necesita una tercera tabla que localice comentarios por ID.

CQL controla los tipos y las claves. Quien carga los datos debe respetar los estados, el límite de texto, el cálculo del minuto y el segmento, y los likes no negativos. El esquema no impone estas reglas mediante `CHECK` ni claves foráneas. Los scripts generan valores válidos, pero otra aplicación también debería validarlos.

## Escrituras y coherencia de las copias

La muestra y el CRUD usan un batch registrado (`BEGIN BATCH`) con dos sentencias por comentario. Su registro permite completar escrituras pendientes ante un fallo recuperable, pero no aísla las lecturas entre particiones. Durante la operación, una consulta puede ver una copia actualizada y la otra todavía no. Si se supera el tiempo de espera, hay que verificar o reintentar con las mismas claves.

La carga masiva usa `COPY` primero en la tabla principal y después en la secundaria. No hay una transacción entre ambas. Mientras se importa no se deben consultar ni editar esos datos. La carga termina cuando las dos tablas confirman todas las filas. Ante un error, se revisan los registros y se repite el mismo CSV para completar las copias mediante upsert.

Una nueva ejecución de muestra o carga restaura sus valores iniciales. La idempotencia demuestra que repetir las mismas claves no duplica filas, no que conserve ediciones posteriores sobre los datos sintéticos. Una importación más pequeña tampoco elimina comentarios de una importación anterior más grande.

El CRUD modifica contenido, estado y likes, sin cambiar las claves. Cambiar autor, partido o fecha requeriría borrar e insertar el comentario en ambas tablas. Las operaciones se ejecutan sin ediciones, borrados ni recargas simultáneas sobre el mismo comentario.

## Operaciones CQL

| Archivo | Propósito |
|---|---|
| `scripts/esquema.cql` | Crear keyspace, principal y secundaria con `IF NOT EXISTS` |
| `scripts/carga_muestra.cql` | Insertar 12 comentarios con claves y valores estables |
| `scripts/crud.cql` | Crear, consultar, editar y borrar solo `PRUEBA-CRUD-001` en ambas tablas |
| `scripts/consultas.cql` | Ejecutar las tres preguntas, incluyendo una ventana entre minutos |
| `scripts/carga_o_prueba.py` | Generar un CSV y ejecutar dos `COPY` medidos, con columnas explícitas |

`IF NOT EXISTS` permite repetir la inicialización, pero no adapta un esquema anterior incompatible. El keyspace está separado de los otros módulos. Las lecturas puntuales del CRUD sirven para comprobar cada operación.

La tabla de historial evita consultar todas las particiones de todos los partidos de un autor. El costo es otra fila y otra escritura por alta, edición o borrado. Se duplican aproximadamente los bytes de datos, además del trabajo de commit log y compactación. No se agregan índices ni vistas materializadas, ya que las tres preguntas se resuelven mediante las claves elegidas.

Referencia técnica: [definición de tablas de Cassandra](https://cassandra.apache.org/doc/stable/cassandra/developing/cql/ddl.html) y [operaciones y batches de CQL](https://cassandra.apache.org/doc/stable/cassandra/developing/cql/dml.html).
