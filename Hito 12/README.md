[Repositorio Fixture 2030 - Grupo 13](https://github.com/AxelYairFischbein/Fixture2030-Grupo13)

# Hito 12: carga y optimización de comentarios

El módulo mide una sola operación de la [API del Hito 10](../Hito%2010/README.md): la lectura paginada de comentarios en Cassandra. Se eligió porque permite observar concurrencia, particiones y cursores con un resultado verificable. La preparación genera datos aislados, mientras que la carga HTTP es **100 % lectura**. No se ejecutan otras rutas ni se cambia el contrato público.

La [propuesta de Data Mart y alternativa relacional](analisis.md) complementa la prueba operacional. No se implementa infraestructura analítica.

## Entorno y preparación

Se requiere PowerShell, Python 3.10 o posterior, Git y Docker Desktop con contenedores Linux. El generador HTTP utiliza la biblioteca estándar de Python. Los drivers se reutilizan dentro de la imagen construida con el Dockerfile y las dependencias del Hito 10.

El Compose inicia **solo otra instancia de la API existente**, en `127.0.0.1:8012`, con 2 CPU y 512 MiB. No copia la aplicación ni inicia otra Cassandra. Reutiliza `grupo13-hito6-cassandra-1` por `host.docker.internal:9042`. El puerto interno de la API es 8000. El keyspace `fixture2030_h12` evita consultar o sobrescribir los comentarios anteriores. No necesita credenciales de los otros productos y no llama a `/api/v1/salud`, que consultaría las seis dependencias.

Antes de una medición, coordinar el uso de Cassandra y evitar otras cargas sobre el equipo. No detener otros servicios para mejorar las cifras. Cassandra conserva su configuración existente, con heap de 2 GiB y sin límite adicional de CPU o memoria por contenedor. Los límites de la API no limitan el servidor compartido.

Desde la raíz del repositorio:

```powershell
Set-Location '.\Hito 12'
docker version
docker inspect --format '{{.State.Status}}' grupo13-hito6-cassandra-1
# Solo si está detenido y corresponde a la instancia existente del Hito 6:
docker start grupo13-hito6-cassandra-1
docker compose config --quiet
docker compose up -d --build api
```

Esperar el arranque HTTP con un plazo acotado. Este bloque también debe ejecutarse después de cambiar entre la versión base y la optimizada:

```powershell
$plazoH12 = [Diagnostics.Stopwatch]::StartNew()
$disponibleH12 = $false
do {
    try {
        $respuestaH12 = Invoke-WebRequest 'http://127.0.0.1:8012/openapi.json' -UseBasicParsing -TimeoutSec 2
        $disponibleH12 = $respuestaH12.StatusCode -eq 200
    } catch {
        Start-Sleep -Milliseconds 500
    }
} while (-not $disponibleH12 -and $plazoH12.Elapsed.TotalSeconds -lt 30)
if (-not $disponibleH12) { throw 'La API no respondió dentro del plazo' }
```

Un OpenAPI accesible no acredita Cassandra. La preparación y el medidor verifican después la fuente y sus datos. Si Cassandra todavía está iniciando, esperar su disponibilidad antes de continuar. No borrar datos ni recrearla para resolver un error de conexión.

```powershell
docker compose exec -T api python /h12/datos.py preparar
if ($LASTEXITCODE -ne 0) { throw 'Revisar la preparación antes de medir' }
docker compose exec -T api python /h12/datos.py validar
```

`preparar` crea el keyspace únicamente cuando no existe. Reutiliza el esquema CQL del Hito 6 en modo de lectura, sustituyendo solo el nombre del keyspace. La tabla secundaria por usuario queda vacía, porque el adaptador prepara su sentencia al conectar y este escenario no utiliza esa escritura. Si la muestra ya existe, compara sus atributos y no vuelve a escribir. Una diferencia interrumpe el procedimiento sin sobrescribirla. `validar` nunca carga datos.

La muestra de esta ejecución ya existía y se conservó. Su origen temporal es fijo, `2030-06-10T18:00:00Z`. Es información sintética, no comentarios reales del torneo. No se usa la hora de ejecución para regenerar timestamps.

## Datos y escenario

| Elemento | Definición |
| --- | --- |
| Endpoint | `GET /api/v1/partidos/{partidoId}/comentarios` |
| Parámetros | `desde=2030-06-10T18:00:00Z`, `hasta=2030-06-10T18:05:00Z`, `limite=50`, cursor desde la segunda página |
| Dataset | 2.400 comentarios, 1.200 por `PAR-001` y `PAR-002`. Cinco minutos y cuatro segmentos por partido, 40 particiones de 60 filas |
| Generación | IDs `H12-PAR-xxx-nnnnn`, 100 identificadores sintéticos de usuario, contenido determinista, tres comentarios por timestamp. CRC32 del ID módulo 4, igual que el adaptador |
| Respuesta correcta | HTTP 200, `X-Request-ID` conservado, 50 filas por página, todos los atributos esperados, orden `creado_en DESC, comentario_id ASC` y cursor correcto |
| Carga | Ciclo fijo de 16 solicitudes. Doce a `PAR-001` y cuatro a `PAR-002`, distribuidas por igual entre sus primeras cuatro páginas. La fracción final de un ciclo puede quedar incompleta |
| Escrituras medidas | Cero. La preparación está separada de la prueba HTTP |
| Prueba mínima | Un cliente durante 2 s, además de las validaciones |
| Calentamiento | Un cliente durante 5 s, excluido del resumen de sostenimiento |
| Rampa | 1 cliente durante 3 s, luego 4 clientes durante 3 s |
| Sostenimiento | 8 clientes durante 15 s, conexiones HTTP reutilizadas, sin pausas artificiales ni reintentos |
| Límites | Timeout del cliente de 5 s por operación de socket, driver de 3 s. Máximo 10.000 solicitudes por fase, 10 errores, o un fallo de integridad |
| Interrupción | Se deja de emitir carga al alcanzar un límite, fallar el muestreo o observar memoria del contenedor al 90 % de su límite informado. Se espera la finalización de las solicitudes en curso |

La ventana es `[desde, hasta)`. La validación completa recorre las 24 páginas de cada partido antes y después, incluyendo los empates que cruzan páginas. La carga concentra consultas en las primeras cuatro, como una lectura de comentarios recientes. No representa todos los accesos del proyecto ni escrituras simultáneas.

El tiempo programado de emisión es 26 s por ejecución completa. Hay pausas entre fases para cerrar el muestreo. El drenaje de requests, las validaciones y los comandos Docker agregan tiempo. No es una prueba indefinida. Los percentiles describen este modelo de clientes cerrados, donde cada cliente espera su respuesta antes de emitir otra solicitud. No representan una tasa de llegada externa fija.

## Ejecución base y optimizada

[config.ejemplo.json](config.ejemplo.json) contiene parámetros no sensibles. `--config .\config.local.json` permite una copia local. El mismo objeto de configuración se envía por entrada estándar a la validación de Cassandra, incluso cuando el archivo está fuera del montaje. No se debe cambiar la cantidad o los timestamps de una muestra existente para hacerla coincidir con otra prueba.

La línea base corresponde al adaptador del commit `1e3cd9fbf6e300afb201cd9d7f45d18270307123`. Para reproducirla sin descartar cambios de trabajo, extraer solamente ese archivo a `.local`:

```powershell
@'
from pathlib import Path
import subprocess
p = Path('.local/cassandra_comentarios_base.py')
p.parent.mkdir(exist_ok=True)
contenido = subprocess.check_output(['git', 'show', '1e3cd9fbf6e300afb201cd9d7f45d18270307123:Hito 10/app/adapters/cassandra_comentarios.py'])
if p.exists() and p.read_bytes() != contenido:
    raise SystemExit('Existe una copia diferente. Se conserva sin sobrescribirla')
if not p.exists():
    p.write_bytes(contenido)
'@ | python -X utf8 -
docker compose -f docker-compose.yml -f docker-compose.base.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.base.yml up -d --no-build api
```

Repetir el bloque de disponibilidad HTTP anterior. El archivo base se monta como solo lectura sobre el adaptador de la imagen. No se altera el checkout ni se copian las bases. Después ejecutar:

```powershell
$marcaH12 = Get-Date -Format 'yyyyMMdd-HHmmss'
python -X utf8 .\medir.py --variante base --humo --salida ".\evidencia\humo-$marcaH12.json"
if ($LASTEXITCODE -ne 0) { throw 'Resolver la prueba mínima antes de aumentar la carga' }
python -X utf8 .\medir.py --variante base --salida ".\evidencia\base-1-$marcaH12.json"
if ($LASTEXITCODE -ne 0) { throw 'Conservar y revisar la ejecución incompleta' }
python -X utf8 .\medir.py --variante base --salida ".\evidencia\base-2-$marcaH12.json"
```

Para utilizar el adaptador optimizado del árbol de trabajo, recrear **solo la API del Hito 12** sin la superposición base:

```powershell
docker compose -f docker-compose.yml up -d --build api
# Repetir el bloque de disponibilidad HTTP antes de medir.
python -X utf8 .\medir.py --variante optimizada --salida ".\evidencia\optimizada-1-$marcaH12.json"
if ($LASTEXITCODE -ne 0) { throw 'Conservar y revisar la ejecución incompleta' }
python -X utf8 .\medir.py --variante optimizada --salida ".\evidencia\optimizada-2-$marcaH12.json"
```

`--variante` etiqueta el registro, no cambia el código ejecutado. La variante real depende del montaje anterior. Mantener la misma imagen de dependencias, datos y configuración en ambas pruebas. Los resultados registran las versiones e identidad de la imagen para detectar diferencias. Conservar todas las repeticiones comparables.

El archivo de salida debe ser nuevo. Se reserva antes de evaluar el entorno y se actualiza después de cada etapa. Si falla una etapa, quedan las mediciones anteriores, el tipo seguro del error y `completa: false`, con salida 2. Un registro interrumpido no entra en una comparación exitosa. La primera prueba mínima detectó un error de tipos en la consulta de memoria de Windows y se conserva como incompleta. Se corrigió antes de las mediciones comparables.

## Hipótesis y cambio aplicado

Las dos líneas base se ejecutaron antes de editar el adaptador. En sostenimiento, el promedio registrado por el adaptador fue de 24,076 y 30,610 ms, frente a 34,979 y 40,049 ms del cliente. El cursor hacía una búsqueda de empates del mismo timestamp sobre los cinco minutos y los cuatro segmentos, seguida por la consulta de registros anteriores.

**Hipótesis:** consultar los 20 buckets para un timestamp que pertenece a un único minuto agrega trabajo innecesario. Acotar esa búsqueda a sus cuatro segmentos puede reducir el costo de las páginas con cursor.

El único cambio funcional está en [cassandra_comentarios.py](../Hito%2010/app/adapters/cassandra_comentarios.py). Para `Q_EMPATE` se envía el minuto UTC del cursor, conservando los cuatro segmentos. La primera página y la consulta de registros anteriores siguen iguales. No hay caché, nuevo endpoint ni reducción de campos o filas de la respuesta.

El trade-off es depender explícitamente de la invariancia `minuto = truncar(creado_en al minuto UTC)`, que utiliza la escritura del adaptador y se verifica en la muestra. Un registro mal ubicado por una escritura externa no se encontraría mediante esa búsqueda acotada. Corresponde corregir la ingesta inconsistente, no afirmar que esta prueba cubre cualquier dato externo. No se midió el comportamiento bajo escrituras concurrentes.

## Resultados registrados

Mediciones del **29 de octubre de 2026, UTC−03:00**, sobre el commit base indicado y cambios locales de los Hitos 11 y 12. La variante optimizada agrega el cambio del adaptador y su prueba. Equipo Intel Core i7-14650HX, 24 procesadores lógicos y 31,61 GiB de RAM visible en Windows. Docker Engine 29.7.2 dispone de 24 CPU y 15,42 GiB. API 1.0.0, Python 3.12.16, FastAPI 0.143.2, Uvicorn 0.54.0, cassandra-driver 3.30.1, Cassandra 5.0.9. Generador Python 3.13.7 en Windows 11.

En los cuatro JSON comparables, `cambios_locales` quedó vacío porque la consulta de Git resolvía las rutas desde `Hito 12`. Ese valor no acredita que el árbol de trabajo estuviera limpio. Los registros se conservan sin modificar. El medidor consulta ahora la versión y los cambios relevantes desde la raíz del repositorio, resuelta a partir de su archivo, independientemente de la carpeta de ejecución.

Solo el sostenimiento de 15 s con 8 clientes entra en esta tabla. Calentamiento y rampas permanecen separados en los JSON. Todas las latencias están en milisegundos.

| Ejecución, hora local de inicio | Solicitudes | Mín. | Promedio | P50 | P95 | P99 | OK/s | Fallos / timeouts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base 1, 23:05:24 | 3.429 | 13,758 | 34,979 | 33,745 | 53,875 | 74,172 | 228,188 | 0 / 0 |
| Base 2, 23:05:59 | 2.997 | 13,452 | 40,049 | 33,201 | 87,605 | 135,758 | 199,282 | 0 / 0 |
| Optimizada 1, 23:09:55 | 3.469 | 14,051 | 34,590 | 31,127 | 57,108 | 82,797 | 230,905 | 0 / 0 |
| Optimizada 2, 23:10:30 | 3.577 | 13,340 | 33,549 | 30,313 | 55,946 | 92,733 | 238,017 | 0 / 0 |

| Ejecución | CPU API media / máx. % | Memoria API máx. MiB | CPU Cassandra media / máx. % | Memoria Cassandra máx. GiB | CPU generador % / memoria final MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base 1 | 86,49 / 104,68 | 131,30 | 209,96 / 288,48 | 3,054 | 15,81 / 30,91 |
| Base 2 | 65,67 / 100,31 | 132,50 | 145,84 / 223,03 | 3,037 | 14,23 / 30,61 |
| Optimizada 1 | 74,31 / 105,90 | 97,26 | 146,20 / 214,85 | 3,035 | 18,41 / 30,83 |
| Optimizada 2 | 76,67 / 104,04 | 97,77 | 147,43 / 216,12 | 3,040 | 17,16 / 30,88 |

La tasa de error fue 0 % en las cuatro ejecuciones. Las 13.472 solicitudes de sostenimiento pasaron la comparación de contenido y cursor. Las verificaciones completas antes y después encontraron los mismos 2.400 comentarios, sin faltantes, duplicados ni atributos alterados en las particiones previstas. No hubo escrituras durante estas mediciones.

Las dos ejecuciones optimizadas tuvieron mayor throughput y menor P50. Sin embargo, sus P95 y P99 fueron mayores que los de Base 1. Base 2 presentó más variabilidad. Por eso no se concluye una mejora garantizada de las colas de latencia. La menor memoria observada tampoco se atribuye únicamente al cambio, porque el proceso de la API fue recreado y su estado de memoria varía. Se conservan las cuatro repeticiones, sin seleccionar solo la mejor ni promediar percentiles como si fueran un percentil conjunto.

### Método y límites de interpretación

- Cliente: `perf_counter`, desde la emisión hasta leer, decodificar y validar la respuesta. Incluye errores y solicitudes lentas. Percentiles por rango más próximo, posición `ceil(p × N)`, sobre todas las solicitudes finalizadas de la fase.
- Throughput: respuestas correctas divididas por la duración real de la fase, incluido el drenaje de solicitudes. Se registran intentadas, exitosas, fallidas y timeouts. El porcentaje de error utiliza todas las finalizadas. Una solicitud asignada sin resultado queda explícita e invalida la ejecución completa.
- API: tiempos del log HTTP correlacionado por `X-Request-ID`. Adaptador: duración informada en `meta.fuentes`, que incluye driver, red y espera. No es el tiempo interno exacto de Cassandra. Se exigió correlación HTTP y dependencia para todas las solicitudes medidas.
- Recursos: `docker stats --no-stream` de API y Cassandra, con separación objetivo de 2 s y fechas de inicio de cada muestreo. Hubo ocho muestras por componente en cada sostenimiento. La obtención tarda aproximadamente dos segundos y puede solaparse con el cierre de la fase. La memoria del CLI excluye caché de archivos según Docker. CPU 100 % equivale aproximadamente a un procesador lógico, por lo que Cassandra puede superar 100 %.
- Generador: `process_time` dividido por duración, sobre un procesador lógico, y working set al finalizar cada fase mediante Windows. No incluye CPU de los procesos auxiliares de Docker. El generador, la API, Cassandra y otros contenedores comparten el equipo. No se midió tiempo interno del motor, saturación de disco ni capacidad productiva.

Estos resultados son locales y breves. La distribución, los datos calientes, el generador y el sistema operativo condicionan las cifras. No equivalen a millones de usuarios ni permiten una extrapolación lineal de capacidad.

## Evidencias y comprobaciones

| Archivo | Contenido |
| --- | --- |
| [01_humo.json](evidencia/01_humo.json) | Primer intento real incompleto por la consulta de memoria de Windows, conservado y excluido de la comparación |
| [02_humo.json](evidencia/02_humo.json) | Prueba mínima corregida, 195 lecturas correctas e integridad verificada |
| [03_base_1.json](evidencia/03_base_1.json), [04_base_2.json](evidencia/04_base_2.json) | Línea base completa, dos repeticiones, fases, recursos e integridad |
| [05_optimizada_1.json](evidencia/05_optimizada_1.json), [06_optimizada_2.json](evidencia/06_optimizada_2.json) | Mismo escenario con el cursor acotado, dos repeticiones |
| [07_validacion.txt](evidencia/07_validacion.txt) | Resumen de comprobaciones y alcance de la corrección del diagnóstico |
| [08_comparacion.png](evidencia/08_comparacion.png) | Captura de la comparación de las cuatro ejecuciones, con percentiles, throughput y errores |
| [09_integridad.png](evidencia/09_integridad.png) | Captura del resumen de validación, con conteos, integridad, pruebas y limitaciones |
| [datos.py](datos.py), [medir.py](medir.py), [test_medicion.py](test_medicion.py) | Preparación y validación, carga y comparación, pruebas unitarias |
| [docker-compose.yml](docker-compose.yml), [docker-compose.base.yml](docker-compose.base.yml) | API acotada y superposición del adaptador base |

Comandos para revisar resultados y repetir únicamente las pruebas unitarias:

```powershell
python -X utf8 .\medir.py --comparar .\evidencia\03_base_1.json .\evidencia\04_base_2.json .\evidencia\05_optimizada_1.json .\evidencia\06_optimizada_2.json
python -X utf8 -m unittest discover -s . -p 'test_*.py' -v
python -X utf8 -m unittest discover -s '..\Hito 11\tests' -v
docker compose exec -T api python -m pytest tests/unit -q -p no:cacheprovider
```

Las pruebas con dobles verifican el cálculo de percentiles, la configuración efectiva, la conservación de resultados parciales, el oráculo y la acotación del cursor. No reemplazan las conexiones reales. OpenAPI sigue coincidiendo con la aplicación. El [diagnóstico del Hito 11](../Hito%2011/README.md) separa ahora identidad, permisos y disponibilidad. Sus evidencias históricas se conservan con su alcance y fechas, sin reclasificar sus resultados antiguos.

Las dos capturas representan las ejecuciones registradas del 29 de octubre de 2026, no pruebas nuevas. La primera muestra la comparación y la segunda, el resumen de integridad. El registro de validación conserva su estado original y una nota fechada de cierre de las capturas.

## Detención y datos

```powershell
docker compose stop api
# Para volver a usar la variante optimizada con la configuración actual:
docker compose -f docker-compose.yml up -d --no-build api
```

No se detiene Cassandra ni otros módulos. `.local`, configuración local, secretos y cachés están excluidos por [.gitignore](.gitignore). Las evidencias contienen solo resultados y parámetros no sensibles.

La limpieza es opcional y no se ejecutó. Una vez terminada la revisión, si se decide retirar **exclusivamente** esta muestra, comprobar primero el keyspace `fixture2030_h12` y eliminar solo ese keyspace mediante el cliente CQL. No borrar carpetas persistentes, volúmenes ni usar una limpieza general. Mientras se conserve, permite repetir la validación sin cargar nuevamente.
