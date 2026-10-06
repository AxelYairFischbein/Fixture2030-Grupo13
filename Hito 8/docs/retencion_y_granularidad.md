# Retención y granularidad

## Política implementada

La base `fixture2030_h8` se crea con retención de **siete días** mediante `influxdb3 create database --retention-period 7d`. Se conserva el detalle por segundo durante esa ventana para revisar partidos recientes y aceptar demoras o ajustes de la fuente. El límite se calcula con el timestamp de observación, no con la fecha de carga.

`inicializacion.py` reutiliza una base existente y verifica su retención con `influxdb3 show retention`. Si la configuración difiere, se detiene y no la reemplaza ni borra datos. La [evidencia del ambiente](evidencia/01_ambiente_y_retencion.txt) registra `7.0000d` en InfluxDB 3 Core 3.12.0. Se comprobó la configuración, no una expiración que todavía no ocurrió.

Al superar el límite de retención, los puntos dejan de ser consultables. La liberación física de archivos se realiza en segundo plano y no tiene por qué coincidir con ese instante. Un timestamp demasiado antiguo no se vuelve reciente por reenviarlo. Una validación de la muestra después de siete días puede devolver menos puntos por vencimiento legítimo.

La persistencia es una decisión diferente. El bind mount conserva el catálogo, la autorización y los datos del nodo al detener, reiniciar o recrear el contenedor. La retención sigue limitando la antigüedad visible. En [la prueba de persistencia](evidencia/04_persistencia.txt) se conservaron 21.600 puntos, la distribución, los tipos y una muestra después de reiniciar y recrear, sin volver a cargar. Ese resultado no representa una prueba de recuperación ante pérdida del disco ni de alta disponibilidad.

## Resumen implementado

[agregaciones.py](../scripts/agregaciones.py) calcula cinco intervalos de un minuto por equipo. Promedia el indicador de posesión, suma incrementos de pases calculados con una muestra previa y suma tiros de intervalos consecutivos. Incluye la cantidad de observaciones y una comprobación de continuidad. El resumen se calcula bajo demanda, no se almacena en otra tabla y no prolonga la retención original.

Con cadencia de un segundo, un minuto pasa de 60 observaciones a una fila por equipo. Se pierde el orden de los cambios dentro del minuto, los instantes exactos de los tiros y las fluctuaciones del porcentaje. Los conteos del minuto se preservan si la cobertura es completa. Para volver a resumir porcentajes de minutos con distinta cobertura habría que conservar suma y cantidad o ponderar adecuadamente, no promediar sin más las medias de cada minuto.

## Evolución propuesta

Para análisis del torneo completo podría conservarse un resumen por minuto durante un año y mantener los siete días de detalle. Sería necesario materializarlo antes de que expire el detalle, registrar cobertura y reprocesar intervalos que reciban datos tardíos. El año es una propuesta para comparar el torneo con análisis posteriores, no una política configurada. La entrega no agrega tareas programadas ni un sistema automático de downsampling.

El trade-off consiste en reducir almacenamiento y filas de consulta a cambio de perder detalle. Las ventanas de seguimiento requieren datos recientes y completos. Los análisis históricos admiten mayor granularidad, pero ya no pueden reconstruir cada segundo. Guardar más días no elimina los límites de consulta del motor.

## Límites del motor

InfluxDB 3 Core limita los archivos Parquet que puede consultar por operación. La referencia habitual de unas 72 horas depende del límite de archivos y de cómo se escribieron los datos, no es una garantía para cualquier carga. Se mantienen los valores predeterminados y se consultan como máximo las dos horas permitidas por el generador. La retención de siete días no implica poder consultarlos todos juntos. Para una evolución histórica se planificarían ventanas pequeñas y resúmenes con un costo medido.

Las opciones se contrastaron con la ayuda del CLI de la versión ejecutada. La documentación oficial describe la [retención](https://docs.influxdata.com/influxdb3/core/reference/internals/data-retention/) y los [límites de configuración](https://docs.influxdata.com/influxdb3/core/reference/config-options/). Las consultas, la configuración efectiva y el montaje se verificaron en el entorno local.
