# Cardinalidad, carga y escalabilidad

## Series y volumen local

La cardinalidad corresponde a combinaciones válidas de tags. En la muestra hay dos partidos, cada uno con dos equipos y un estadio fijo. Son **2 × 2 = 4 series**. No corresponde multiplicar dos partidos por cuatro equipos por dos estadios, porque la mayoría de esas combinaciones no existe.

El volumen es `2 partidos × 2 equipos × 90 minutos × 60 segundos / paso`. Con paso de un segundo se generan **21.600 puntos**, no 64.800. Cada punto contiene tres fields. Extender el modelo a 127 partidos produciría 254 series y 1.371.600 puntos para 90 minutos a 1 Hz. La cantidad de sedes no multiplica las series porque cada partido tiene una sede asignada. El tiempo aumenta los puntos, no la cardinalidad.

Un tag con UUID por punto haría crecer las series junto con cada observación. Un nombre libre de proveedor podría fragmentar una misma fuente por errores de escritura. Se evitan ambos. Si se agregara una fuente real, tendría un identificador estable y solo se incluiría como dimensión si fuese necesario distinguir sus observaciones.

## Generación y carga implementadas

El generador guarda el origen temporal una vez y escribe line protocol en orden temporal sin conservar toda la muestra en memoria. Los parámetros y el archivo generado quedan en `datos/`. La prueba utiliza lotes de 1.000 puntos y un cliente secuencial. Esta configuración es suficiente para la demostración y sencilla de explicar. El cargador mantiene en memoria solamente el lote actual.

Se utiliza `POST /api/v3/write_lp`, precisión de segundos, `accept_partial=false` y `no_sync=false`. Los datos de un lote inválido no se aceptan parcialmente. Una respuesta exitosa confirma la escritura sincronizada en el WAL, no que ya exista un archivo Parquet final. El recuento posterior comprueba los puntos lógicos consultables.

Los errores HTTP 429, 500, 502, 503 y 504, las interrupciones de conexión y los tiempos de espera admiten hasta tres intentos totales, con esperas de uno y dos segundos. Se reenvían los mismos bytes. Errores de autenticación o datos, como 401 o 400, interrumpen la carga sin reintentos. Si se pierde la respuesta, el lote pudo haberse escrito. No se declara ese resultado como confirmado. La repetición con la misma identidad permite recuperar el proceso sin inventar timestamps nuevos.

El cargador informa por separado:

- Puntos generados según los metadatos de la muestra.
- Puntos enviados, contando los reenvíos.
- Puntos de lotes con respuesta exitosa, contados una vez por lote confirmado.
- Puntos almacenados, obtenidos mediante una consulta de recuento en la ventana.

El archivo se genera ordenado. Un envío tardío conserva su timestamp y puede modificar una consulta anterior mientras esté retenido. Ante un error no se continúa con los lotes siguientes. Se corrige la causa y se repite el archivo completo. La validación comprueba cantidad por combinación de tags, límites temporales, tipos, valores extremos, totales y una muestra. No equivale a comparar cada field de todos los puntos.

## Medición inicial

El 2026-10-05 se midieron 21.600 puntos, cuatro series, 3.105.560 bytes de line protocol y lotes de 1.000, con un único cliente. El entorno usó InfluxDB 3 Core 3.12.0 y Python 3.13.7 sobre Windows. El equipo tiene un Intel Core i7-14650HX, 24 procesadores lógicos y unos 31,6 GiB de RAM. Docker dispone de unos 15,4 GiB y el contenedor está limitado a 2 CPU y 2 GiB. Otros contenedores siguieron activos.

| Operación | Resultado observado |
| --- | --- |
| Generación inicial del archivo | 0,038803 s |
| Primera carga, 22 peticiones sin reintentos | 21,841943 s, 988,92 puntos confirmados/s |
| Repetición, 22 peticiones sin reintentos | 21,335979 s, 1.012,37 puntos confirmados/s |
| Puntos consultables tras cada carga | 21.600, con 5.400 por serie |
| Lectura de ventana, hasta cinco filas | 0,023206 s |
| Comparación de dos equipos | 0,007233 s |
| Resumen por minuto, diez filas | 0,035030 s |

La generación incluye la escritura del line protocol. La carga incluye lectura del archivo, solicitudes HTTP y espera de confirmación del WAL, pero excluye generación, inicio de Docker, arranque del cliente y consulta final de recuento. Las consultas incluyen HTTP y decodificación JSON. Se ejecutaron después de cargar y de realizar comprobaciones previas, por lo que no representan una medición de caché fría. Son tiempos de ejecuciones individuales, no percentiles ni una prueba de capacidad sostenida. Los recursos y registros están en [ambiente](evidencia/01_ambiente_y_retencion.txt), [carga](evidencia/02_carga_y_repeticion.txt) y [consultas](evidencia/03_consultas_y_agregacion.txt).

## Revisión posterior

El 2026-10-06 entre las 00:08 y las 00:09 UTC, correspondientes al 2026-10-05 entre las 21:08 y las 21:09 de Argentina, se repitieron las pruebas con la muestra existente. Se conservaron las cuatro series, los 21.600 puntos, los parámetros y los timestamps originales. La generación produjo un archivo idéntico byte a byte. Se comprobaron nuevamente la versión 3.12.0, los recursos del equipo y los límites de 2 CPU y 2 GiB del contenedor.

| Operación de esta revisión | Resultado observado |
| --- | --- |
| Regeneración del archivo existente | 0,032639 s |
| Primer reenvío, 22 peticiones sin reintentos | 21,707682 s, 995,04 puntos confirmados/s |
| Segundo reenvío, 22 peticiones sin reintentos | 21,668193 s, 996,85 puntos confirmados/s |
| Puntos consultables antes y después de cada reenvío | 21.600, con 5.400 por serie |
| Lectura de ventana, cinco filas | 0,026523 s |
| Comparación de dos equipos | 0,023450 s |
| Resumen por minuto, diez filas | 0,029133 s |

Ambos envíos son reescrituras de puntos existentes. Se utilizó el mismo método de medición descrito para la ejecución inicial, con lotes de 1.000 y un cliente. No se combinan los tiempos de ambas ejecuciones ni se interpretan como una prueba de capacidad sostenida. Los bloques de revisión posterior en las evidencias conservan sus fechas, método, recursos y resultados. La estimación de 10M+ sigue siendo una propuesta sin medición a ese volumen.

## Estrategia para 10M+ puntos

El modelo actual por equipo no produce por sí solo diez millones de puntos en un torneo de 127 partidos. No se aumenta artificialmente la frecuencia de posesión ni se cuentan los fields como puntos para alcanzar ese número.

Un escenario futuro sería incorporar observaciones de actividad de los jugadores en cancha a 1 Hz para analizar su evolución durante el partido. Esa frecuencia permitiría seguimiento por segundo, aunque no análisis de movimientos de precisión subsegundo. Con 22 fuentes activas durante 90 minutos y 127 partidos, la estimación es:

`22 × 90 × 60 × 127 = 15.087.600 puntos`

Es una estimación con presencia constante de 22 jugadores, sin tiempo adicional ni expulsiones. Los cambios sustituyen fuentes activas y no agregan jugadores simultáneos. Esta ampliación requeriría definir medidas por jugador y otra tabla coherente con ese patrón. No está implementada ni medida en este módulo. Si solo se requieren estadísticas por equipo, se mantiene el volumen menor justificado por ese dominio.

Para estimar series en esa evolución, con hasta 16 jugadores participantes por equipo y partido habría como máximo `127 × 2 × 16 = 4.064` combinaciones partido-jugador. No se multiplica por todos los equipos y estadios, que dependen de cada participación. Esta cota es una hipótesis de planificación, no una cantidad observada de jugadores del torneo.

La estrategia de carga conservaría generación secuencial, timestamps de observación y lotes. Se empezaría con lotes de 1.000 y un cliente. Solo después de medir se ensayarían dos clientes asignando series distintas a cada uno, conservando orden dentro de cada serie. Cada lote tendría hasta tres intentos y contenido estable. Los recuentos se verificarían por partido y ventanas pequeñas, sin una consulta histórica única. La memoria del cliente dependería de los lotes concurrentes y no de los quince millones de puntos.

No se extrapola el tiempo local como una promesa para ese volumen. El almacenamiento columnar, los archivos que intervienen en cada consulta, el WAL, la memoria y el disco pueden cambiar el comportamiento. Antes de aumentar fuentes habría que medir una muestra mayor y los puntos realmente guardados. En una evolución posterior tendría sentido observar retraso de la fuente, errores, duración por lote, memoria y disco. Distribuir la carga entre escritores no convierte este único nodo en un clúster ni aporta alta disponibilidad. No se incorporan servicios adicionales en la entrega.
