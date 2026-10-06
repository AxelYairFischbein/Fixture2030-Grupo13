[Repositorio Fixture 2030 — Grupo 13](https://github.com/AxelYairFischbein/Fixture2030-Grupo13)

# Hito 8 — Series temporales de estadísticas

Módulo de Ingeniería de Datos II con InfluxDB 3 Core. Registra estadísticas sintéticas de equipos, recupera ventanas recientes, compara equipos y resume por minuto. Utiliza una base, una tabla y un único servicio. El modelo y sus decisiones se desarrollan en los documentos enlazados al final.

## Requisitos y configuración

Se necesita Windows con PowerShell, Docker Desktop con contenedores Linux y Compose, Python 3.10 o posterior y el puerto local 8181 disponible. No hay dependencias de Python para instalar. La ejecución registrada utilizó Python 3.13.7, Docker 29.7.2 e InfluxDB 3 Core 3.12.0.

El Compose usa `influxdb:3-core`, CLI `influxdb3`, SQL y endpoints v3. La etiqueta puede recibir actualizaciones, por lo que debe comprobarse la versión al repetir la ejecución. El contenedor tiene límites de 2 CPU y 2 GiB de RAM. El puerto se publica solamente en `127.0.0.1` y la autenticación permanece activa.

Los datos se guardan en un **bind mount** desde `$env:USERPROFILE\docker\data\influxdb` hacia `/var/lib/influxdb3/data`. Compose sustituye `${USERPROFILE}` usando la variable de entorno heredada del proceso. No evalúa expresiones de PowerShell ni convierte automáticamente `$HOME` en una variable de Compose. Se conserva el identificador de nodo `grupo13-hito8` para volver a abrir los mismos datos.

## 1. Iniciar y autorizar

Ejecutar desde la raíz del repositorio en PowerShell. Seguir los bloques en orden y detener la ejecución si un comando falla.

```powershell
Set-Location '.\Hito 8'
docker info
python --version
if (-not $env:USERPROFILE) { throw 'Falta la variable de entorno USERPROFILE' }
$rutaH8 = Join-Path $env:USERPROFILE 'docker\data\influxdb'
New-Item -ItemType Directory -Force -Path $rutaH8 | Out-Null
docker compose config --quiet
docker compose up -d influxdb
python -X utf8 scripts/inicializacion.py
docker compose exec -T influxdb influxdb3 --version
docker compose ps
docker inspect grupo13-hito8-influxdb-1 --format '{{json .Mounts}}'
```

`inicializacion.py` espera el arranque de forma acotada, crea la autorización local una sola vez y comprueba la disponibilidad mediante el CLI dentro del contenedor. Crea `fixture2030_h8` con retención de siete días si no existe. Al repetirlo, reutiliza la credencial y comprueba la retención existente. Debe mostrar la base y `retention_period: 7.0000d`.

El montaje debe informar `Type: bind`, el origen bajo la carpeta del usuario y `Destination: /var/lib/influxdb3/data`. Docker Desktop puede mostrar el origen como una ruta Windows o como `/run/desktop/mnt/host/...`.

El token se guarda en `.local/admin.token`, excluido de Git antes de su creación. Se envía al CLI por entrada estándar y a las solicitudes HTTP mediante un encabezado. No se muestra, no aparece en argumentos de procesos ni se guarda en Compose. No copiarlo en capturas o evidencias. Es una credencial administrativa de este nodo local. Un entorno compartido requeriría revisar los permisos y la distribución de credenciales.

Si ya existen datos y falta la credencial, recuperar el token de esa instancia en `.local/admin.token`. El script no regenera tokens ni reinicializa el directorio. Ante problemas de acceso al bind mount, revisar el permiso del usuario sobre esa carpeta y su disponibilidad para Docker Desktop. No cambiar permisos de otras carpetas ni borrar los datos. Para diagnosticar el servicio:

```powershell
docker compose ps
docker compose logs --tail 30 influxdb
```

## 2. Generar, cargar y validar

```powershell
python -X utf8 scripts/generacion_puntos.py
python -X utf8 scripts/carga_lotes.py --lote 1000
python -X utf8 scripts/validacion.py
```

La muestra predeterminada tiene dos partidos, dos equipos por partido, 90 minutos y una observación por segundo. Son **21.600 puntos con tres fields cada uno**, distribuidos en cuatro series de 5.400 puntos. El cargador usa un cliente, 22 lotes y espera confirmación de escritura en el WAL. La validación debe terminar con `validacion: OK` y 21.600 puntos almacenados. También comprueba distribución, extremos temporales, tipos, totales y una muestra de atributos.

El generador escribe secuencialmente `datos/puntos.lp` y conserva los parámetros y el origen temporal en `datos/muestra.json`. Las fechas recientes son una reproducción sintética, no las fechas oficiales de los partidos. La primera ejecución fija el inicio a 90 minutos antes del minuto UTC actual. Las siguientes conservan ese instante.

Para comprobar la repetición, ejecutar nuevamente los mismos tres comandos. Los envíos acumulados aumentan, pero deben seguir existiendo 21.600 puntos lógicos. Se conserva la identidad de cada punto y se escriben los mismos valores.

Antes de la primera generación pueden elegirse `--partidos` de 1 a 32, `--minutos` de 10 a 120 y `--paso` entre 1, 5, 10, 30 o 60 segundos. Por ejemplo:

```powershell
python -X utf8 scripts/generacion_puntos.py --partidos 2 --minutos 90 --paso 1
```

El script rechaza cambiar parámetros sobre una muestra existente. Para iniciar una muestra distinta, mover primero la carpeta `datos` fuera del repositorio y conservarla allí. No se borran puntos de la base. Evitar ventanas superpuestas de muestras diferentes, ya que comparten las mismas identidades. Si la muestra cumplió siete días, dejará de ser visible por retención. Reenviarla con sus timestamps originales no la rejuvenece. En ese caso se necesita una nueva reproducción, manteniendo separadas sus mediciones.

## 3. Consultar y agregar

```powershell
python -X utf8 scripts/consultas_temporales.py
python -X utf8 scripts/agregaciones.py
```

Se imprimen el SQL ejecutado, el resultado y el tiempo observado. Las consultas toman el final de la muestra, no el reloj actual, para que la repetición conserve la misma ventana mientras los datos sigan retenidos. Se espera una lectura de hasta cinco filas, una comparación con dos equipos y diez filas de resumen por minuto. La interpretación está en [patrones de acceso](docs/patrones_de_acceso.md).

## 4. Comprobar persistencia y detener

Comparar el recuento, la distribución y la muestra antes y después del reinicio. No volver a cargar entre ambas validaciones.

```powershell
python -X utf8 scripts/validacion.py
docker compose restart influxdb
python -X utf8 scripts/inicializacion.py
python -X utf8 scripts/validacion.py
```

También puede verificarse la recreación del contenedor con los mismos datos:

```powershell
docker compose up -d --force-recreate influxdb
python -X utf8 scripts/inicializacion.py
python -X utf8 scripts/validacion.py
```

Para detener y volver a iniciar conservando el bind mount y la credencial:

```powershell
docker compose stop influxdb
docker compose start influxdb
python -X utf8 scripts/inicializacion.py
```

No hace falta limpiar la base para repetir la muestra. Los scripts no eliminan datos. Las operaciones de este Compose afectan solamente al servicio del Hito 8.

## Resultados registrados

En la ejecución inicial del 5 de octubre de 2026 se verificaron inicio, autorización, montaje, retención, carga, repetición, consultas y persistencia tras reiniciar y recrear el contenedor. La primera carga confirmó 21.600 puntos en **21,841943 s**, aproximadamente **988,92 puntos/s**. La generación del archivo tomó **0,038803 s**. Son mediciones locales de una ejecución, no una capacidad garantizada. El método, los recursos y los tiempos de consulta se detallan en las evidencias.

La revisión posterior se ejecutó el 5 de octubre de 2026, entre las 21:08 y las 21:09 de Argentina, correspondientes al 6 de octubre entre las 00:08 y las 00:09 UTC. Se mantuvieron InfluxDB 3 Core 3.12.0, los parámetros y los timestamps originales. Dos reenvíos completos tomaron **21,707682 s** y **21,668193 s**, y conservaron 21.600 puntos lógicos. También pasaron las consultas, la agregación y la persistencia tras reiniciar y recrear, sin volver a cargar entre estas últimas comprobaciones. Los cuatro archivos de evidencia distinguen esta revisión de la ejecución inicial. Los tiempos nuevos corresponden a reescrituras de datos existentes.

La retención de siete días está configurada y comprobada. No se esperó su vencimiento. El objetivo de 10M+ se desarrolla como estimación y estrategia futura, sin afirmar que se cargó o midió ese volumen.

## Archivos del módulo

| Archivo | Contenido |
| --- | --- |
| [docker-compose.yml](docker-compose.yml) | Servicio, puerto, recursos y persistencia |
| [scripts/inicializacion.py](scripts/inicializacion.py) | Disponibilidad, token local, base y retención |
| [scripts/generacion_puntos.py](scripts/generacion_puntos.py) | Muestra reproducible y parametrizable |
| [scripts/carga_lotes.py](scripts/carga_lotes.py) | Envío, reintentos limitados y métricas de carga |
| [scripts/consultas_temporales.py](scripts/consultas_temporales.py) | Ventana reciente y comparación de equipos |
| [scripts/agregaciones.py](scripts/agregaciones.py) | Resumen temporal por minuto |
| [scripts/validacion.py](scripts/validacion.py) | Recuento, distribución, tipos y muestra |
| [scripts/comun.py](scripts/comun.py) | Funciones compartidas de conexión, tiempo y datos sintéticos |
| [Patrones de acceso](docs/patrones_de_acceso.md) | Necesidades, consultas e interpretación |
| [Modelo multidimensional](docs/modelo_multidimensional.md) | Identidad, tipos y relación con otros hitos |
| [Cardinalidad y escalabilidad](docs/cardinalidad_y_escalabilidad.md) | Volumen, carga, mediciones y estrategia 10M+ |
| [Retención y granularidad](docs/retencion_y_granularidad.md) | Ciclo de vida y límites de conservación |
| [01 Ambiente y retención](docs/evidencia/01_ambiente_y_retencion.txt) | Versión, recursos, autorización y montaje |
| [02 Carga y repetición](docs/evidencia/02_carga_y_repeticion.txt) | Generación, métricas y distribución real |
| [03 Consultas y agregación](docs/evidencia/03_consultas_y_agregacion.txt) | SQL, resultados y tiempos reales |
| [04 Persistencia](docs/evidencia/04_persistencia.txt) | Recuento y muestra antes y después |
| [05 Entorno](docs/evidencia/05_entorno.png) | Captura del servicio activo y de la versión de InfluxDB |
| [06 Validación](docs/evidencia/06_validacion.png) | Captura de validación correcta, 21.600 puntos y cuatro series de 5.400 |

`.gitignore` excluye credenciales, configuración local, datos generados y cachés de Python. Los scripts y las evidencias breves sí forman parte de la entrega.
