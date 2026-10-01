# Hito 7 - Caché de usuarios y sesiones del Fixture 2030

Grupo 13. Un servicio Redis administra sesiones, una copia temporal de la ficha de un equipo y un ranking de partidos consultados. La muestra es sintética. No se conectan los servicios de los otros hitos.

## Preparación e inicio

Requisitos: Windows con PowerShell, Docker Desktop iniciado en modo Linux, Docker Compose y Python 3.10 o superior. Python usa solamente la biblioteca estándar. El acceso a Redis se realiza con `redis-cli` dentro del contenedor. El puerto `127.0.0.1:16379` debe estar libre. Se usa ese puerto para permitir la convivencia con otro Redis local en 6379. Dentro del contenedor Redis escucha en 6379.

Desde la raíz del repositorio:

```powershell
Set-Location -LiteralPath '.\Hito 7'
docker version
docker compose version
docker compose config --quiet
docker compose up -d --wait
docker compose ps
docker compose exec -T redis redis-cli PING
```

Se espera `healthy` y `PONG`. Si el motor no responde, abrir Docker Desktop y esperar su inicio. Si Redis no está disponible, revisar `docker compose logs --tail 40 redis` y resolver el error antes de ejecutar la muestra.

El proyecto Compose se llama `grupo13-hito7`. Publica el puerto solo en localhost, sin contraseñas ni tokens. Es un entorno local de un nodo y no implementa autenticación para otros equipos de la red. El contenedor tiene un límite de 256 MiB y una CPU. Redis usa `maxmemory 64mb` y `noeviction`.

La imagen declarada es `redis:latest`. Para descargarla nuevamente en otra fecha se puede ejecutar `docker compose pull redis` antes del inicio. Registrar la versión observada porque esa etiqueta cambia.

## Montaje y configuración efectiva

`redis_data` está declarado en la sección `volumes` y su nombre real es `grupo13_hito7_redis_data`. Docker lo monta en `/data`. Los scripts se montan en `/scripts` como solo lectura. Los volúmenes sobreviven a la eliminación del contenedor.

```powershell
$contenedorH7 = docker compose ps -q redis
$inspeccionH7 = docker inspect $contenedorH7 | ConvertFrom-Json
$montajeH7 = $inspeccionH7[0].Mounts | Where-Object { $_.Destination -eq '/data' }
$montajeH7 | Select-Object Type, Name, Destination
if ($montajeH7.Type -ne 'volume' -or $montajeH7.Name -ne 'grupo13_hito7_redis_data') {
    throw 'El montaje de datos no coincide con el volumen declarado'
}
python -X utf8 .\scripts\demo.py archivo inicializacion.redis
```

Se espera `appendonly yes`, `appendfsync everysec`, `save` vacío, `dir /data`, `maxmemory 67108864` y `maxmemory-policy noeviction`. La persistencia AOF y el volumen resuelven problemas diferentes. La justificación y el trade-off están en [memoria y escalabilidad](docs/memoria_y_escalabilidad.md).

## Orden de ejecución

Ejecutar una sola demostración completa a la vez. La limpieza afecta exclusivamente cinco claves conocidas bajo `fixture2030:h7:demo:`. Cada prueba vuelve a preparar sus datos, por lo que puede repetirse. No hay borrado global.

```powershell
python -X utf8 .\scripts\demo.py sesiones
if ($LASTEXITCODE -ne 0) { throw 'Fallo en sesiones' }
python -X utf8 .\scripts\demo.py cache
if ($LASTEXITCODE -ne 0) { throw 'Fallo en cache' }
python -X utf8 .\scripts\demo.py concurrencia
if ($LASTEXITCODE -ne 0) { throw 'Fallo en concurrencia' }
```

Resultados esperados:

- Sesiones carga dos sesiones normales, actualiza y renueva una, cierra otra y espera el vencimiento de una sesión de prueba de 3 segundos. Las sesiones cerrada y vencida devuelven `TTL -2`. Intentar renovarlas devuelve 0 y no las reconstruye.
- Caché parte sin clave, consulta una fuente simulada en el proceso Python, guarda con TTL de 300 segundos y obtiene un hit. Después cambia el origen, invalida y recupera el dato nuevo. Las tres lecturas del flujo producen dos misses y un hit.
- Concurrencia ejecuta 100 visitas desde cada uno de cuatro clientes, compara 400 con el puntaje final de `PAR-001` y verifica la intercalación. El Top 3 queda en `PAR-001:400`, `PAR-002:2`, `PAR-003:1`. También consulta memoria, contadores y persistencia mediante `INFO`.

Al terminar quedan una sesión normal, una ficha en caché y un ranking, mientras sus TTL sigan vigentes. La fuente simulada se reinicia con cada ejecución de `cache`. Es un diccionario pequeño fuera de Redis que representa el dato de origen, no una consulta a MongoDB.

## Archivos y ejecución individual

| Archivo | Propósito |
| --- | --- |
| `scripts/inicializacion.redis` | Disponibilidad, versión y configuración |
| `scripts/carga_muestra.redis` | Limpieza acotada y creación de dos sesiones de muestra |
| `scripts/sesiones.redis` | Lectura, actividad, cierre y sesión de TTL corto |
| `scripts/cache.redis` | Inspección de la ficha y su TTL, antes y después del flujo |
| `scripts/concurrencia.redis` | Operación atómica de visita, Top 3 y TTL |
| `scripts/metricas.redis` | INFO y primera página de SCAN |
| `scripts/demo.py` | Único auxiliar, ejecuta archivos, espera vencimientos, simula el origen y coordina cuatro clientes |
| `docs/patrones_de_acceso.md` | Tráfico, consultas y relación con otros hitos |
| `docs/modelo_clave_valor.md` | Claves, estructuras y muestra |
| `docs/ciclo_de_vida_e_invalidacion.md` | Sesiones, cache-aside y atomicidad |
| `docs/memoria_y_escalabilidad.md` | Memoria, persistencia, medición y límites |
| `docs/evidencia/` | Cinco registros de ejecuciones reales |

Para estudiar un archivo por separado:

```powershell
python -X utf8 .\scripts\demo.py archivo carga_muestra.redis
python -X utf8 .\scripts\demo.py archivo sesiones.redis
python -X utf8 .\scripts\demo.py archivo cache.redis
python -X utf8 .\scripts\demo.py archivo concurrencia.redis
python -X utf8 .\scripts\demo.py archivo metricas.redis
```

La ejecución individual de `sesiones.redis` no espera el vencimiento y la de `cache.redis` solo inspecciona. Usar las acciones completas anteriores para demostrar esos flujos.

El auxiliar quita líneas vacías y comentarios de línea completa que empiezan con `#` antes de enviar los comandos a la entrada estándar de `redis-cli`. No se admiten comentarios al final de un comando. Cada sentencia ocupa una línea, incluso `EVAL`. Se verificó una respuesta por sentencia en los archivos sin `INFO`. `INFO` se imprime como texto. La opción `-e` detecta errores del servidor. No se utiliza `--pipe`, que espera protocolo Redis, para enviar estos archivos de texto.

Para usar el cliente interactivo:

```powershell
docker compose exec redis redis-cli
```

Salir con `QUIT`. Para inspeccionar claves desde PowerShell:

```powershell
docker compose exec -T redis redis-cli SCAN 0 MATCH 'fixture2030:h7:demo:*' COUNT 10
```

Si el primer valor devuelto es distinto de 0, usarlo como cursor en la siguiente llamada. Repetir hasta recibir 0, aunque una página esté vacía. El auxiliar recorre el cursor completo después de la prueba concurrente.

## Detención y persistencia

```powershell
docker compose stop
docker compose start --wait
docker compose exec -T redis redis-cli PING
```

También se puede reiniciar con `docker compose restart redis`. Para verificar que una sesión todavía vigente conserva sus atributos y su vencimiento, ejecutar el siguiente bloque después de la muestra. No ejecutar otra carga entre ambas lecturas.

```powershell
$claveH7 = 'fixture2030:h7:demo:sesion:SES-DEMO-01'
$antesH7 = docker compose exec -T redis redis-cli --json HGETALL $claveH7
$ttlAntesH7 = [int](docker compose exec -T redis redis-cli TTL $claveH7)
if ($ttlAntesH7 -lt 60) { throw 'Repetir la muestra para disponer de una sesion vigente' }
docker compose restart redis
docker compose up -d --wait
$despuesH7 = docker compose exec -T redis redis-cli --json HGETALL $claveH7
$ttlDespuesH7 = [int](docker compose exec -T redis redis-cli TTL $claveH7)
$antesH7
$despuesH7
"TTL antes=$ttlAntesH7 despues=$ttlDespuesH7"
if ($antesH7 -ne $despuesH7 -or $ttlDespuesH7 -le 0 -or $ttlDespuesH7 -gt $ttlAntesH7) {
    throw 'Fallo en recuperacion de la sesion'
}
docker compose exec -T redis redis-cli INFO persistence
```

El TTL sigue transcurriendo durante la detención. Una sesión vencida no debe recuperarse como válida. `docker compose down` seguido de `docker compose up -d --wait` también conserva el volumen. No agregar la opción `-v` ni borrar el volumen.

## Evidencia y revisión

Los registros agrupan ambiente y montaje, sesiones, caché, concurrencia con métricas y persistencia. Los resultados y las limitaciones se interpretan en [memoria y escalabilidad](docs/memoria_y_escalabilidad.md). Para actualizar los registros de los flujos en PowerShell:

```powershell
python -X utf8 .\scripts\demo.py sesiones | Out-File -Encoding utf8 .\docs\evidencia\02_sesiones.txt
if ($LASTEXITCODE -ne 0) { throw 'Fallo en sesiones' }
python -X utf8 .\scripts\demo.py cache | Out-File -Encoding utf8 .\docs\evidencia\03_cache.txt
if ($LASTEXITCODE -ne 0) { throw 'Fallo en cache' }
python -X utf8 .\scripts\demo.py concurrencia | Out-File -Encoding utf8 .\docs\evidencia\04_concurrencia_metricas.txt
if ($LASTEXITCODE -ne 0) { throw 'Fallo en concurrencia' }
```

La entrega es mediante enlace de GitHub. Antes de publicar, revisar los cambios locales, los cinco registros y que las cifras documentadas correspondan a la misma ejecución.
