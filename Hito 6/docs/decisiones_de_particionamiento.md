# Decisiones de particionamiento

## Minutos y segmentos

Particionar únicamente por partido haría que un encuentro con un millón de comentarios concentrara aproximadamente 500 MB en una sola partición, con el supuesto de 500 bytes por fila. También dirigiría todas las escrituras del partido al mismo conjunto de réplicas. Por eso se elige `(partido_id, minuto, segmento)`.

El minuto UTC acota el período de cada partición. Los cuatro segmentos, calculados con CRC32 sobre el ID, reparten las escrituras simultáneas del partido. El mismo ID siempre obtiene el mismo segmento, aunque el reparto no es exactamente uniforme. En el nodo único, todas las particiones comparten CPU, memoria y disco.

## Estimaciones por partición

Los cálculos usan MB decimales y 500 bytes por fila como presupuesto aproximado, no como tamaño físico medido.

| Escenario | Filas estimadas por partición principal | Datos por partición | Escrituras de alta por segundo por partición |
|---|---:|---:|---:|
| Pico de diseño, 2.000 comentarios/s en un partido durante 60 s | `2.000 × 60 / 4 = 30.000` | 15 MB | 500 |
| Crecimiento al doble, 4.000 comentarios/s | 60.000 | 30 MB | 1.000 |
| Pico extraordinario, 10.000 comentarios/s durante 60 s | 150.000 | 75 MB | 2.500 |

Estos valores suponen un reparto aproximadamente uniforme y no son límites impuestos por Cassandra. Las 100 ediciones y 10 bajas por segundo podrían agregar unas 27,5 escrituras/s por partición si se distribuyen igual. El espacio real también depende de las versiones, los tombstones y la compactación.

La secundaria particiona por usuario y día. Se estiman hasta 2.000 comentarios diarios por usuario, alrededor de 1 MB por partición. El promedio sería de 0,023 altas/s, con ráfagas de hasta 2/s. Estos valores no se controlan desde el esquema. Una cuenta con mayor actividad podría superar la estimación y concentrar demasiadas escrituras.

Con 10 millones de comentarios, las dos representaciones requieren aproximadamente 10 GB de datos con este presupuesto, antes de otros archivos y espacio temporal de compactación. El siguiente torneo duplicaría la capacidad requerida. El bucket evita crecimiento ilimitado de una sola partición, pero no limita el tamaño total de la base.

## Trade-offs y crecimiento

Q1 consulta cuatro particiones y Q2 hasta 24. El trade-off es hacer más lecturas a cambio de reducir el tamaño de cada partición y repartir las escrituras. Con 10.000 Q1/s se podrían alcanzar 40.000 accesos a particiones/s. La medición realizada evalúa la importación de datos, no esa cantidad de lecturas simultáneas.

Si el volumen supera lo previsto, habría que revisar la duración de cada bucket, los segmentos y la capacidad del cluster. Por ejemplo, ocho segmentos reducirían aproximadamente a la mitad las filas por partición, pero duplicarían los accesos de Q1. Ese cambio requeriría migrar los datos y adaptar las consultas, no solo modificar el cálculo del hash.

El hash de la clave de partición distribuye tokens entre réplicas en un cluster. Los segmentos no asignan un continente, una máquina ni un datacenter. Agregar nodos no divide por sí solo una partición existente.

## Moderación, expiración y borrado

La moderación cambia `estado` sin mover el comentario de partición. Las consultas muestran ese valor, pero no buscan todos los pendientes de la base.

No se utiliza TTL. Q3 necesita conservar el historial y no hay un plazo de retención definido. El efecto es crecimiento acumulado, que deberá resolverse con una política explícita de archivo o retención cuando exista ese requisito.

`DELETE` crea marcas de borrado llamadas tombstones. El dato deja de aparecer en las consultas, pero el espacio no se libera de inmediato. Su eliminación depende de la compactación y del período de gracia. Se conservan los valores predeterminados y el CRUD solo borra un comentario de prueba en ambas tablas. Un borrado masivo podría afectar las lecturas y la compactación.

Si se pidieran reportes analíticos históricos, habría que definir sus preguntas y un proceso de extracción apropiado. No se resolverían agregando filtros globales a estas tablas operativas.
