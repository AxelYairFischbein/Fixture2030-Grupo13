# Memoria, persistencia y escalabilidad

## Límite y política

Se configura `maxmemory 64mb` con `noeviction`. Sesiones, caché y ranking comparten la instancia. Esta política evita descartar sesiones activas para hacer espacio a una ficha o a más visitas. El trade-off es rechazar escrituras que requieren memoria cuando se alcanza el límite. Una política `volatile-*` también podría desalojar sesiones porque todas tienen TTL.

Expiración y evicción son distintas. La expiración responde al tiempo de vida definido por el módulo. La evicción elimina claves antes de su vencimiento por presión de memoria. Con `noeviction` se esperan cero claves desalojadas. Las expiraciones siguen funcionando.

Ante una respuesta OOM no se debe informar éxito. La creación o renovación de sesión falla sin conceder un nuevo acceso. La caché puede omitirse y devolver el dato del origen. Una visita no confirmada no se contabiliza como aceptada. Se debe revisar memoria y carga antes de reintentar, sin borrar datos ajenos ni entrar en un bucle de reintentos. El auxiliar detecta errores mediante `redis-cli -e` y detiene las pruebas que requieren confirmar escrituras.

El contenedor tiene 256 MiB para dejar margen sobre los 64 MiB de Redis. `maxmemory` no es un límite exacto de RAM del proceso: hay buffers, fragmentación y trabajo de persistencia. Una operación puede superar temporalmente el umbral y un script que ya empezó a escribir tiene reglas especiales para completarse. El límite Docker protege el entorno, pero quedarse sin memoria a ese nivel puede terminar el proceso. La muestra no busca saturar ninguno de los dos límites.

Como estimación de diseño, 10.000 sesiones de 1 KiB ocuparían unos 10 MiB antes de considerar estructuras internas y otros datos. No es una medición ni una promesa de capacidad. `INFO memory` permite observar el uso real y revisar la estimación.

## Persistencia y almacenamiento

El volumen nombrado `grupo13_hito7_redis_data` conserva los archivos de `/data` al detener o recrear el contenedor. Es una decisión de almacenamiento. Por separado se elige AOF con `appendonly yes` y `appendfsync everysec`. Se desactivan snapshots periódicos con `save ""`.

AOF registra cambios y los recupera al iniciar. Sincronizar cada segundo evita una escritura sincronizada por visita, con el riesgo de perder aproximadamente el último segundo ante una caída abrupta. Se prefiere aquí a snapshots periódicos porque las sesiones cambian con frecuencia. RDB guarda instantáneas y puede perder los cambios posteriores a la última. RDB permite comandos individuales y no obliga a trabajar por lotes. AOF puede usar una base en formato RDB durante su reescritura, aunque los snapshots periódicos estén desactivados.

La prueba usa una sesión normal todavía vigente, compara atributos y TTL antes y después del reinicio y consulta `INFO persistence`. También recrea el contenedor sin eliminar el volumen. Es recuperación local tras detención controlada. No demuestra tolerancia a cortes eléctricos, pérdida del disco ni disponibilidad continua. Los TTL conservan su vencimiento absoluto, por lo que siguen avanzando durante la detención.

## Medición y evidencia

La prueba concurrente usa cuatro procesos `redis-cli`, cada uno con 100 visitas y una pausa de 10 ms entre operaciones. Se comprueba el puntaje final, todas las respuestas del 1 al 400 y rangos de puntajes superpuestos entre clientes. Las tres visitas de preparación pertenecen a otros partidos y quedan fuera del intervalo medido.

El tiempo de pared incluye inicio de clientes, llamadas a Docker, pausas y recepción de respuestas. La tasa calculada es de visitas completas del flujo local. Cada visita contiene `ZINCRBY` y `EXPIRE` dentro de `EVAL`. No es la capacidad máxima del servidor ni una medición aislada de latencia Redis. `docker stats` se consulta después de la prueba y representa una observación posterior, no un pico durante la carga.

Los cinco registros conservan fecha, versión y resultados. `01_ambiente.txt` contiene Compose, montaje efectivo, imagen y recursos. `02_sesiones.txt` muestra renovación, cierre y expiración. `03_cache.txt` muestra las tres lecturas cache-aside. `04_concurrencia_metricas.txt` contiene la medición, Top 3, `INFO` y recorrido SCAN. `05_persistencia.txt` compara el dato vigente después de reiniciar y recrear el contenedor.

La tasa de hit se calcula solo sobre las tres llamadas a la función de lectura: un hit y dos misses, 33,33 %. Las consultas de inspección no entran en ese denominador. Los contadores `keyspace_hits`, `keyspace_misses`, `expired_keys` y `evicted_keys` de `INFO stats` son acumulados de la instancia, incluyen otras operaciones y no se presentan como la tasa de esta caché. Se consultan además `used_memory`, `used_memory_rss`, `maxmemory`, `INFO commandstats` y el estado de AOF.

### Resultados registrados el 30 de septiembre de 2026

Se utilizó Redis 8.10.2, Docker Engine 29.7.2, Compose v5.5.0 y Python 3.13.7 en Windows 11. El host tiene un Intel Core i7-14650HX con 24 procesadores lógicos y aproximadamente 31,6 GiB de RAM visible. El motor Docker informa 24 CPU y 15,42 GiB disponibles. Se aplicaron los límites de una CPU y 256 MiB al contenedor.

| Prueba | Resultado observado | Registro |
| --- | --- | --- |
| Ambiente | `PONG`, configuración AOF efectiva y `/data` de tipo `volume` con el nombre declarado | [01_ambiente.txt](evidencia/01_ambiente.txt) |
| Sesiones | TTL renovado de 1798 a 1800. Sesiones vencida y cerrada ausentes, sin recreación | [02_sesiones.txt](evidencia/02_sesiones.txt) |
| Caché | Dos misses y un hit. El nombre actualizado se recuperó del origen tras invalidar | [03_cache.txt](evidencia/03_cache.txt) |
| Concurrencia | 400 de 400 visitas, cuatro clientes intercalados, 1,358341 segundos y 294,48 visitas/s con el método descrito | [04_concurrencia_metricas.txt](evidencia/04_concurrencia_metricas.txt) |
| Persistencia | Mismos atributos con TTL 1723 antes, 1716 después del reinicio y 1707 después de recrear. Las sesiones eliminadas siguieron ausentes | [05_persistencia.txt](evidencia/05_persistencia.txt) |

En la lectura de métricas posterior a la carga, `used_memory` fue 1.854.344 bytes y `used_memory_rss` fue 25.899.008 bytes. Los contadores acumulados mostraron 46 hits, 32 misses, 2 expiraciones y 0 evicciones. Incluyen una ejecución previa para comprobar reproducibilidad. `aof_last_write_status` fue `ok`. Los logs de recuperación muestran la carga de la base y del archivo incremental AOF.

No se realizaron pruebas de saturación de RAM, caída abrupta del host, indisponibilidad del origen ni failover. El comportamiento ante esos errores está documentado, pero no se presenta como evidencia ejecutada. No quedan comprobaciones de infraestructura pendientes para el alcance local.

## Alcance del nodo local

Hay un único Redis, sin réplicas ni conmutación automática. El volumen y AOF permiten recuperar archivos, pero no eliminan el punto único de falla. Ante crecimiento se revisarían memoria por clave, frecuencia de actualización y separación de cargas. Réplicas permitirían copias para lectura con posible atraso. Sentinel coordinaría failover y Redis Cluster distribuiría claves entre nodos. Esas topologías no están implementadas ni probadas en este módulo.
