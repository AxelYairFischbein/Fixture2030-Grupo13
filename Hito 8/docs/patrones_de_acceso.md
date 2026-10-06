# Patrones de acceso

Se necesita observar la evolución de un partido y comparar sus equipos sin recorrer todo el torneo. El productor conceptual es un proveedor de estadísticas. En este módulo lo representa un generador determinista. La actualización cada segundo permite consultar cambios recientes, aunque una medida pueda repetir su valor en varias muestras.

| Patrón | Productor o consumidor y objetivo | Ventana y frecuencia | Dimensiones y medidas | Precisión y respuesta |
| --- | --- | --- | --- | --- |
| P1 Registrar observaciones | Proveedor sintético que actualiza el estado del partido | 90 minutos por partido, una muestra por equipo cada segundo | Partido, equipo y estadio. Posesión estimada, pases acumulados y tiros del intervalo | Timestamp UTC en segundos. Un punto con tres fields. La carga local reproduce la secuencia por lotes |
| P2 Recuperar estado reciente | Consumidor de seguimiento que comprueba cambios y frescura | Último minuto de la muestra, lectura conceptual cada 5 s | Un partido y un equipo, con estadio como contexto. Las tres medidas | Hasta cinco observaciones en orden descendente, conservando sus timestamps |
| P3 Comparar equipos | Analista que compara actividad reciente | Cinco minutos, consulta conceptual cada minuto | Los dos equipos de un partido. Media de posesión, incremento de pases y suma de tiros | Una fila por equipo, cantidad de muestras y marca de intervalos inválidos |
| P4 Resumir evolución | Analista que observa tendencias con menos filas | Cinco minutos agrupados por minuto, consulta bajo demanda | Partido y equipo. Las mismas medidas con agregaciones propias | Un intervalo por equipo, 60 muestras esperadas por minuto con paso de 1 s |

Las frecuencias de lectura son necesidades de diseño. Los scripts se ejecutan una vez por invocación y no implementan consultas periódicas. P1 justifica la escritura ordenada y compacta. P2 y P3 requieren filtrar por partido y equipo. El estadio identifica el contexto de cada serie y permite una futura selección por sede sin copiar su ficha. P4 necesita timestamps uniformes y funciones distintas para cada medida. De estos patrones se deriva una sola tabla, descrita en [modelo multidimensional](modelo_multidimensional.md).

## Ausencias y datos tardíos

En P1, una demora de la fuente conserva el timestamp de observación. No se reemplaza por la hora de recepción. Los reintentos repiten los mismos puntos. Un punto tardío dentro de la retención se puede incorporar al consultar nuevamente. Un punto anterior al límite de retención no vuelve a ser visible por reenviarlo.

En P2, una lista vacía significa que no hay observaciones en la ventana, no que las estadísticas valgan cero. El consumidor debe comparar el último timestamp con la hora esperada de la fuente. Una muestra atrasada se presenta como tal y no como estado actual. La demostración usa la ventana fija de la reproducción.

En P3 y P4, la cantidad de muestras y `intervalos_invalidos` permiten detectar ventanas incompletas, discontinuidades y reinicios del contador. No se rellenan huecos con ceros. Los scripts detienen la validación de estas consultas si faltan equipos o muestras, o si aparece un intervalo inválido. Un agregado incompleto no representa el intervalo entero. Los puntos tardíos obligan a ejecutar de nuevo la consulta antes de considerar definitivo el resultado. No hay resúmenes materializados que queden desactualizados.

Si InfluxDB no responde, la operación informa el error. No se inventan puntos ni resultados. El cargador tiene reintentos limitados para errores transitorios, descritos en [cardinalidad y escalabilidad](cardinalidad_y_escalabilidad.md).

## Consultas e interpretación real

[consultas_temporales.py](../scripts/consultas_temporales.py) implementa P2 y P3. [agregaciones.py](../scripts/agregaciones.py) implementa P4. Todos los rangos tienen límite inferior y superior. El recuento de validación abarca los 90 minutos de la muestra. Ninguna consulta intenta abarcar toda la retención de siete días.

En la ejecución del 2026-10-05, la comparación de PAR-001 produjo:

| Equipo | Muestras | Media de posesión estimada | Pases nuevos | Tiros del intervalo | Intervalos inválidos |
| --- | ---: | ---: | ---: | ---: | ---: |
| EQ-001 | 300 | 49,975 % | 30 | 1 | 0 |
| EQ-002 | 300 | 50,025 % | 25 | 1 | 0 |

La posesión estimada estuvo equilibrada en estas muestras sintéticas. EQ-001 registró cinco pases nuevos más que EQ-002, con 30 frente a 25. Ambos registraron un tiro. Estos resultados describen la reproducción, no un partido real.

El resumen devolvió diez filas, cinco minutos por dos equipos. En cada minuto se observaron seis pases nuevos de EQ-001 y cinco de EQ-002. Las sumas de esos cinco intervalos coinciden con 30 y 25. Los tiros de ambos equipos aparecen en minutos diferentes. El porcentaje se promedia, el contador se diferencia y los eventos del intervalo se suman. El resultado completo está en [la evidencia de consultas](evidencia/03_consultas_y_agregacion.txt).
