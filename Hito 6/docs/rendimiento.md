# Rendimiento y evidencia

## Método de medición

La prueba se ejecutó con `scripts/carga_o_prueba.py --cantidad 20000 --cargar --procesos 4`. El script genera un CSV e importa sus filas con `cqlsh COPY FROM`. Usa la biblioteca estándar de Python y el cliente incluido en el contenedor, sin dependencias adicionales.

El cronómetro monotónico comienza antes del primer COPY y termina después del segundo. Incluye el arranque de ambos clientes, lectura del archivo, conversión, envío y confirmaciones. Excluye la generación, las consultas de ambiente y la comprobación posterior de los extremos. Se registra `CONSISTENCY ONE`, cuatro procesos configurados para COPY y tamaño mínimo y máximo de batch igual a una fila. No se agrupan particiones en batches masivos.

Las cantidades exitosas se extraen del resumen final de cada COPY. No se consideran éxitos las filas solamente generadas ni la tasa instantánea impresa durante la importación. Además, se comprueban el primer y último comentario mediante sus claves completas y timestamps en ambas tablas. Si falta una confirmación, hay filas omitidas, errores o falla esa comprobación, el script termina con error y no declara una tasa lógica válida.

`Comentarios lógicos/s = comentarios confirmados en ambas tablas / duración total`. `Escrituras físicas/s = suma de filas confirmadas por las dos tablas / duración total`. En este documento, escritura física significa una mutación de fila en una tabla. No equivale a una operación de disco ni cuenta por separado commit log, réplicas, SSTables o compactaciones.

## Ambiente observado

| Dato | Valor |
|---|---|
| Fecha de la medición válida | 24/09/2026 21:09:12, Argentina, UTC−03 |
| Fecha UTC | 25/09/2026 00:09:12 |
| Host | Windows 11 Home, Intel Core i7-14650HX, 16 núcleos y 24 procesadores lógicos |
| Memoria física visible en Windows | 33.147.576 KiB, aproximadamente 31,61 GiB |
| Recursos disponibles para Docker | 24 CPU y 16.558.764.032 bytes, aproximadamente 15,42 GiB |
| Docker y Compose | Docker Engine/cliente 29.7.2, Compose 5.5.0 |
| Imagen declarada | `cassandra:latest` |
| Versión observada | Cassandra 5.0.9, cqlsh 6.2.0, CQL 3.4.7, protocolo nativo v5 |
| Topología y consistencia | Un nodo, `SimpleStrategy`, RF 1, `ONE` |
| Heap | 2 GB, generación joven configurada en 512 MB |
| Persistencia | Bind mount del directorio personal de Windows, `docker/data/cassandra` |
| Otros servicios | El contenedor Neo4j del Hito 5 estaba activo y no fue modificado |

Los recursos de Docker se comparten con los otros servicios. No se midió el uso máximo de CPU, disco ni memoria. La base ya contenía la muestra y marcas de borrado de una prueba anterior con 20.000 comentarios. No se vació ni se purgó antes de medir. Se verificaron las fechas de los comentarios importados.

## Resultado ejecutado

| Métrica | Resultado observado |
|---|---:|
| Comentarios solicitados | 20.000 |
| Filas confirmadas en la principal | 20.000 |
| Filas confirmadas en la secundaria | 20.000 |
| Comentarios lógicos confirmados en ambas | 20.000 |
| Escrituras de filas confirmadas | 40.000 |
| Errores y filas sin confirmar | 0 |
| Duración de ambas importaciones | 3,107136 s |
| Tasa lógica | 6.436,80 comentarios/s |
| Tasa de escrituras entre las dos tablas | 12.873,59 filas/s |

En esta prueba breve se superaron 10.000 escrituras de filas por segundo, pero no 10.000 comentarios lógicos por segundo. Como cada comentario se guarda en dos tablas, alcanzar esa segunda tasa requeriría al menos 20.000 escrituras de filas/s. No se midieron carga sostenida, lecturas simultáneas ni tolerancia a fallos.

La distribución uniforme del CSV evita un partido extremadamente caliente. La carga contiene textos cortos y particiones pequeñas. El resultado puede cambiar por tamaño de mensaje, cachés, heap, disco, actividad de otros servicios y compactación. El camino de escritura usa commit log y memtables, y el trabajo posterior de SSTables no queda representado completamente por una prueba de tres segundos.

Para evaluar una carga más cercana al uso real, habría que prolongar la prueba y concentrar parte de los comentarios en un partido. También se podría comparar el resultado con distintas cantidades de procesos de COPY.

## Volumen generado frente a volumen cargado

| Conjunto | Qué se ejecutó | Comentarios lógicos | Filas entre las dos tablas |
|---|---|---:|---:|
| Muestra | Cargada dos veces con iguales claves | 12 | 24 |
| CRUD | Un comentario insertado, editado y eliminado | 0 al finalizar | 0 visibles al finalizar |
| Medición válida | Generada, cargada y confirmada | 20.000 | 40.000 |
| Objetivo superior al millón | Generado realmente como CSV, sin cargar ese volumen | 1.000.100 | 2.000.200 previstas al importarlo |

El conjunto final previsto es de 20.012 comentarios, sin contar la segunda carga de la muestra como datos nuevos. Las versiones y marcas de borrado pueden ocupar espacio adicional. Los 1.000.100 comentarios se generaron, pero no se cargó ni se midió ese volumen en Cassandra.

| Distribución calculada desde los archivos generados | Carga de 20.000 | Generación de 1.000.100 |
|---|---:|---:|
| Particiones principales ocupadas | 1.536 | 30.720 |
| Máximo de filas por partición principal | 22 | 63 |
| Particiones de historial ocupadas | 20.000 | 40.000 |
| Máximo de filas por partición de historial | 1 | 26 |
| Tamaño del CSV | 2.895.802 bytes | 146.244.629 bytes |

Con el presupuesto de 500 bytes por fila, los máximos principales representarían aproximadamente 11 KB y 31,5 KB. Los máximos secundarios representarían 0,5 KB y 13 KB. Son estimaciones basadas en filas, no tamaños físicos medidos de particiones. La distribución sintética es mucho menor que los picos analizados en el documento de particionamiento.

El CSV local más reciente corresponde a 20.000 comentarios. El millón se regenera con el comando del README. Una recarga sobre los mismos IDs mide upserts y no agrega otros 20.000 comentarios lógicos.

## Evidencia conservada

| Archivo | Resultado verificable |
|---|---|
| [01_ambiente_esquema.txt](evidencia/01_ambiente_esquema.txt) | Compose, montaje comprobado, nodo UN, versión, replicación, columnas y claves de las dos tablas |
| [02_carga_crud_consultas.txt](evidencia/02_carga_crud_consultas.txt) | 12 filas por tabla antes y después de repetir la carga, altas, ediciones, bajas y Q1–Q3 |
| [03_generacion_millon.json](evidencia/03_generacion_millon.json) | Generación real de 1.000.100 comentarios y su distribución |
| [04_medicion.json](evidencia/04_medicion.json) | Fecha, versión, recursos, duración, confirmaciones, resúmenes de COPY y tasas válidas |
| [05_persistencia.txt](evidencia/05_persistencia.txt) | Un comentario de muestra y otro masivo, en ambas tablas antes y después del reinicio |

Después de la carga se compararon Q1 y Q2 con el conjunto previsto del CSV más la muestra. Coincidieron el top 20 global y el top 50 global, respectivamente. Esto comprueba el límite combinado, además del orden y los extremos temporales observados sobre la muestra.

Las advertencias de agregación en la evidencia de idempotencia corresponden a `COUNT(*)` sobre las 12 filas de la muestra. Esa consulta de comprobación no integra los patrones frecuentes del módulo.

Referencia del método de importación: [documentación de cqlsh y COPY](https://cassandra.apache.org/doc/stable/cassandra/managing/tools/cqlsh.html).
