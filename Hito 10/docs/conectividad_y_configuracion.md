# Hito 10 · Conectividad y configuración

Grupo 13 · Ingeniería de Datos II · Fixture Mundial 2030

Cubre los apartados *Conectividad* y *Seguridad* de la sección 8 y la sección 5.13 del enunciado (RF16, RNF6, RNF7, RNF8). Todo lo que sigue sale de `app/config/settings.py`, `.env.example` y los scripts de `scripts/`.

## 1. Entornos: desde dónde corre cada componente

| Componente | Dónde corre en el entorno probado | Cómo se levanta |
|---|---|---|
| API | **Notebook** (Windows 11 + PowerShell), proceso `uvicorn app.main:app` con el Python del entorno virtual `Hito 10/.venv` (Python 3.13). | `.\scripts\iniciar_api.ps1` |
| MongoDB 8 | Contenedor de Docker Desktop, `Hito 4/docker-compose.yml` (servicio `mongodb`). | `docker compose up -d` en `Hito 4/` |
| Neo4j | Contenedor, `Hito 5/docker-compose.yml` (servicio `neo4j`). | ídem en `Hito 5/` |
| Cassandra | Contenedor, `Hito 6/docker-compose.yml` (servicio `cassandra`). | ídem en `Hito 6/` |
| Redis | Contenedor, `Hito 7/docker-compose.yml` (servicio `redis`). | ídem en `Hito 7/` |
| InfluxDB 3 Core | Contenedor, `Hito 8/docker-compose.yml` (servicio `influxdb`). | ídem en `Hito 8/` |
| InterSystems IRIS | Contenedor, `Hito 9/docker-compose.yml` (servicio `iris`). | ídem en `Hito 9/` |
| Pruebas (pytest, scripts de evidencia, curl) | Notebook, contra la API en `127.0.0.1` y contra los puertos publicados de los contenedores. | `.\scripts\ejecutar_pruebas.ps1` |

La API **no** se ejecutó dentro de un contenedor en este hito (no hay `Dockerfile`). La sección 5 explica qué cambiaría.

## 2. Puertos en el host

| Fuente | Host:puerto que usa la API | Puerto dentro del contenedor | Observación |
|---|---|---|---|
| MongoDB | `127.0.0.1:27017` | 27017 | Requiere usuario y contraseña (`MONGO_AUTH_DB=admin`). |
| Neo4j | `bolt://127.0.0.1:7687` | 7687 | El navegador de Neo4j queda en 7474; la API no lo usa. |
| Cassandra | `127.0.0.1:9042` | 9042 | Sin autenticación en el contenedor del Hito 6. Tarda 1–2 min en aceptar conexiones. |
| Redis | `127.0.0.1:16379` | **6379** | El Hito 7 publica el 6379 interno en el **16379** del host. |
| InfluxDB 3 | `http://127.0.0.1:8181` | 8181 | SQL por `POST /api/v3/query_sql` con `Authorization: Bearer`. |
| IRIS | `127.0.0.1:1972` | 1972 | El portal web queda en 52773; la API usa el superserver 1972. |
| API | `http://127.0.0.1:8000` | — | Puerto por defecto de `iniciar_api.ps1` (`-Puerto` para cambiarlo). Los scripts de evidencia usan 8010–8018 para no chocar con una API abierta. |

## 3. Variables de entorno

La API lee `Hito 10/.env` (ignorado por git) y las variables del proceso, con `pydantic-settings`. `.env.example` tiene todas las variables con valores de relleno. Una variable vacía cuenta como no definida (`env_ignore_empty=True`).

**Obligatorias sin valor por defecto** (si falta alguna, la API no arranca y el mensaje nombra la variable, nunca su valor): `MONGO_USER`, `MONGO_PASSWORD`, `NEO4J_USER`, `NEO4J_PASSWORD`, `INFLUX_TOKEN_FILE`, `IRIS_USER`, `IRIS_PASSWORD`. Si `INFLUX_TOKEN_FILE` apunta a un archivo inexistente o vacío, la API tampoco arranca.

| Variable | Default en el código | Uso |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Nivel del logger `app`. |
| `MONGO_HOST`, `MONGO_PORT`, `MONGO_DB`, `MONGO_AUTH_DB` | `127.0.0.1`, `27017`, `fixture2030`, `admin` | Conexión y base del Hito 4. |
| `MONGO_SERVER_SELECTION_TIMEOUT_S`, `MONGO_SOCKET_TIMEOUT_S` | `2`, `3` | Timeouts (también se usa el primero como `connectTimeoutMS`). |
| `NEO4J_URI`, `NEO4J_DATABASE` | `bolt://127.0.0.1:7687`, `neo4j` | Conexión y base del Hito 5. |
| `NEO4J_CONNECTION_TIMEOUT_S`, `NEO4J_TX_TIMEOUT_S` | `2`, `3` | Conexión/adquisición y timeout de cada transacción. |
| `CATALOGO_REFRESCO_S`, `CATALOGO_REINTENTO_S` | `600`, `30` | Catálogo de partidos en memoria (`casos_de_uso.md` §3.2). |
| `CASSANDRA_HOSTS`, `CASSANDRA_PORT`, `CASSANDRA_KEYSPACE`, `CASSANDRA_DC` | `127.0.0.1`, `9042`, `fixture2030_comentarios`, `datacenter1` | `CASSANDRA_HOSTS` admite varios hosts separados por coma. |
| `CASSANDRA_USER`, `CASSANDRA_PASSWORD` | vacíos | Solo si el clúster exige autenticación (el del Hito 6 no). |
| `CASSANDRA_CONNECT_TIMEOUT_S`, `CASSANDRA_REQUEST_TIMEOUT_S` | `2`, `2` | Timeouts de conexión y de cada request. |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PREFIJO` | `127.0.0.1`, `16379`, `0`, `fixture2030:h7:demo:` | Conexión y prefijo de claves del Hito 7. |
| `REDIS_PASSWORD` | vacío | El Redis del Hito 7 no usa contraseña. |
| `REDIS_CONNECT_TIMEOUT_S`, `REDIS_SOCKET_TIMEOUT_S` | `0.5`, `0.5` | Timeouts, sin reintentos automáticos. |
| `INFLUX_URL`, `INFLUX_DATABASE` | `http://127.0.0.1:8181`, `fixture2030_h8` | Conexión y base del Hito 8. |
| `INFLUX_TOKEN_FILE` | — (obligatoria) | **Ruta** al archivo del token (en `.env.example`: `../Hito 8/.local/admin.token`, relativa a `Hito 10/`). Nunca el valor del token. |
| `INFLUX_TIMEOUT_S`, `INFLUX_PASO_S` | `5`, `1` | Timeout HTTP y cadencia de la serie (1 observación por segundo). |
| `IRIS_HOST`, `IRIS_PORT`, `IRIS_NAMESPACE` | `127.0.0.1`, `1972`, `USER` | Conexión y namespace del Hito 9. |
| `IRIS_TIMEOUT_S`, `IRIS_ESPERA_BLOQUEO_S` | `3`, `2` | Timeout del SDK y espera máxima del bloqueo del partido en CU-19. |

### 3.1 Timeouts efectivos (RNF8, RNF9)

| Fuente | Parámetro del cliente | Valor | Reintentos implícitos |
|---|---|---|---|
| MongoDB | `serverSelectionTimeoutMS`, `connectTimeoutMS` / `socketTimeoutMS` | 2 s / 3 s | Los del driver (selección de servidor dentro de los 2 s). |
| Neo4j | `connection_timeout`, `connection_acquisition_timeout` / `Query(timeout=…)` | 2 s / 3 s | — |
| Cassandra | `connect_timeout`, `control_connection_timeout` / `request_timeout` | 2 s / 2 s | Ninguno (`FallthroughRetryPolicy`). |
| Redis | `socket_connect_timeout` / `socket_timeout` | 0,5 s / 0,5 s | Ninguno (`Retry(NoBackoff(), 0)`). |
| InfluxDB | `httpx.Client(timeout=…)` | 5 s | Ninguno. |
| IRIS | `timeout` de `iris.dbapi.connect` / espera del bloqueo | 3 s / 2 s | — |

Observado en la evidencia con cada contenedor detenido (`docs/evidencia/<fuente>_lista_de_control.txt`, columna `tiempo_total_s` de curl): la API respondió 503 en el orden del timeout de conexión configurado; ninguna request quedó esperando indefinidamente. Son tiempos de una sola request, no una medición de rendimiento.

## 4. Verificar la conectividad

1. Levantar los contenedores necesarios (`docker compose up -d` en cada `Hito N/`; ver el [README](../README.md) para cargar las muestras).
2. Levantar la API: `.\scripts\iniciar_api.ps1`.
3. En otra terminal: `.\scripts\verificar_conectividad.ps1`. Consulta `GET /api/v1/salud` (no usa credenciales) y muestra, por dependencia, `disponible`, `no_disponible` o `no_configurada`, más el estado del catálogo de partidos. Para cada falla indica qué hito levantar y el comando. Termina con código 0 si el estado general es `ok` y 1 si está `degradado`.

`/api/v1/salud` hace un `ping()` por adaptador (`SELECT 1`, `PING`, `RETURN 1`, etc. según la fuente) que nunca lanza: una fuente caída aparece como `no_disponible` con HTTP 200 y estado general `degradado`. El catálogo figura `cargado` con 64 partidos cuando Neo4j tiene la muestra del Hito 5.

## 5. Si la API corre en un contenedor (documentado, no probado)

Dentro de un contenedor, `127.0.0.1` es el propio contenedor de la API, no la notebook. Habría que cambiar **solo variables de entorno**, no código:

| Opción | Variables | Ventajas y cuidados |
|---|---|---|
| A. Red de Docker compartida (recomendada) | Conectar el contenedor de la API a la red de cada proyecto (`grupo13-hito5_default`, `grupo13-hito6_default`, …, con `docker network connect` o `networks: external` en un compose) y usar el **nombre del servicio** y el **puerto interno**: `MONGO_HOST=mongodb`, `NEO4J_URI=bolt://neo4j:7687`, `CASSANDRA_HOSTS=cassandra`, `REDIS_HOST=redis` con `REDIS_PORT=6379` (no 16379), `INFLUX_URL=http://influxdb:8181`, `IRIS_HOST=iris`. | No depende de los puertos publicados en el host. Hay que comprobar el nombre real de cada red (`docker network ls`) y que no haya dos servicios con el mismo nombre en redes conectadas. |
| B. Puertos publicados del host | `*_HOST=host.docker.internal` y los mismos puertos de la sección 2 (Redis 16379). | Más simple, pero los contenedores de los hitos publican sus puertos en `127.0.0.1`: hay que verificar que Docker Desktop los reenvía a `host.docker.internal`; si no, publicarlos en otra interfaz. |

En ambos casos:

- `INFLUX_TOKEN_FILE` debe apuntar a un archivo **montado como volumen de solo lectura** (por ejemplo `-v "<repo>/Hito 8/.local/admin.token:/run/secrets/influx_token:ro"` e `INFLUX_TOKEN_FILE=/run/secrets/influx_token`). El token no se copia a la imagen.
- `.env` se pasa con `--env-file` en tiempo de ejecución; no se copia a la imagen.
- `uvicorn` tiene que escuchar en `0.0.0.0` dentro del contenedor y publicar el puerto (`-p 127.0.0.1:8000:8000`).
- Los scripts `.ps1` que usan `docker compose exec` (sesiones de prueba) y las pruebas de integración siguen corriendo en la notebook.

## 6. Secretos (RNF6, RNF7)

| Qué | Dónde vive | Por qué no se versiona |
|---|---|---|
| Usuarios y contraseñas de MongoDB, Neo4j e IRIS | `Hito 10/.env` | `.env` está en `Hito 10/.gitignore`. El código no tiene valores por defecto para ellos (`SecretStr`, no se imprimen). |
| Token de InfluxDB | `Hito 8/.local/admin.token` (generado por el Hito 8) | La API recibe la ruta, no el valor. `*.token` y `.local/` están ignorados. |
| IDs de sesión de prueba | `Hito 10/.local/sesiones_prueba.json` y `.local/postman_entorno_local.json` | Son credenciales: se generan al azar en cada ejecución de `crear_sesiones_prueba.ps1`; `.local/` está ignorado en `Hito 10/.gitignore` y en el `.gitignore` raíz; la colección de Postman versionada solo tiene las variables vacías. |
| Logs de la API | `docs/evidencia/*_api.log`, `.local/*.log` | `*.log` está ignorado. Los logs no contienen secretos, pero no se versionan; lo que hace falta para la evidencia se copia en `.txt` (por ejemplo `api_correlacion_request_id.txt`). |

Controles:

- `.env.example` solo tiene valores de relleno (`completar_localmente`).
- El middleware no registra encabezados ni query strings; los adaptadores no registran consultas, parámetros ni mensajes crudos del driver.
- Los scripts de evidencia enmascaran los IDs de sesión (`SES-PRUEBA-3f9a…`) y fallan si queda uno completo; `evidencia_influx.ps1` y `evidencia_iris.ps1` comprueban que el token y la contraseña no aparezcan en la evidencia ni en `git diff`.
- `scripts/evidencia_api.ps1` busca los valores reales de `.env` y del token en todos los archivos que git versionaría y deja el resultado en `docs/evidencia/api_revision_secretos.txt`.

## 7. Detener sin borrar datos

| Acción | Comando | Efecto sobre los datos |
|---|---|---|
| Detener la API | `Ctrl+C` en la terminal de `iniciar_api.ps1` | Ninguno: la API no guarda estado propio. |
| Detener un contenedor | `docker compose stop` en `Hito N/` | Conserva contenedor y volumen; `docker compose start` lo recupera. Es lo que usan los scripts `-ConDetencion`. |
| Bajar un hito | `docker compose down` en `Hito N/` | Borra el contenedor y conserva los volúmenes nombrados. |
| **No usar** | `docker compose down -v`, `docker volume rm`, `docker system prune --volumes` | Borran los volúmenes y obligan a recargar las muestras de los Hitos 4 a 9. |

Las sesiones de prueba vencen solas a los 30 minutos; el comentario y el acta temporales que crean los scripts se borran al terminar.
