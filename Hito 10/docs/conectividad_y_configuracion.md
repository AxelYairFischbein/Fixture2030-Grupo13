# Conectividad, configuración y seguridad

## Dónde corre cada componente

| Componente | Entorno | Escucha en |
| --- | --- | --- |
| API y consola web | Contenedor Python 3.12 o notebook con Python 3.12+ | `127.0.0.1:8000` |
| MongoDB (Hito 4) | Contenedor `fixture2030-mongodb` | `27017` |
| Neo4j (Hito 5) | Contenedor `grupo13-hito5-neo4j-1` | `127.0.0.1:7687` (bolt), `7474` |
| Cassandra (Hito 6) | Contenedor `grupo13-hito6-cassandra-1` | `127.0.0.1:9042` |
| Redis (Hito 7) | Contenedor `grupo13-hito7-redis-1` | `127.0.0.1:16379` → 6379 interno |
| InfluxDB 3 Core (Hito 8) | Contenedor `grupo13-hito8-influxdb-1` | `127.0.0.1:8181` |
| IRIS (Hito 9) | Contenedor `grupo13-hito9-iris-1` | `127.0.0.1:1972` (superserver) |

**Notebook y contenedor**: desde Python local se usan los puertos publicados en `127.0.0.1`. El Compose de la API configura `host.docker.internal` para acceder a esos mismos puertos desde Docker Desktop. Por ejemplo, Redis usa el puerto publicado 16379. El token de InfluxDB se monta en `/run/influx/admin.token`. Las variables de `environment` del Compose prevalecen sobre `.env`. No iniciar las dos variantes de la API en el puerto 8000 al mismo tiempo.

## Variables de entorno

Se leen del entorno del proceso y, si faltan, de `.env` (ignorado por Git). [.env.example](../.env.example) documenta todas sin secretos.

| Variable | Valor para Python local | Uso |
| --- | --- | --- |
| `DEP_TIMEOUT_SEGUNDOS` | `3` | Límite por operación de red en los seis clientes |
| `MONGO_HOST`, `MONGO_PORT`, `MONGO_DB`, `MONGO_USER`, `MONGO_PASSWORD` | `127.0.0.1`, `27017`, `fixture2030`, `admin`, *secreto* | `authSource=admin` |
| `NEO4J_URI`, `NEO4J_DATABASE`, `NEO4J_USER`, `NEO4J_PASSWORD` | `bolt://127.0.0.1:7687`, `neo4j`, `neo4j`, *secreto* | |
| `CASSANDRA_HOSTS`, `CASSANDRA_PORT`, `CASSANDRA_KEYSPACE` | `127.0.0.1`, `9042`, `fixture2030_comentarios` | Sin autenticación en el entorno local |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_PREFIX` | `127.0.0.1`, `16379`, vacío, `fixture2030:h10` | Prefijo propio: no pisa las claves de la demo del Hito 7 |
| `SESION_TTL_SEGUNDOS`, `CACHE_EQUIPO_TTL_SEGUNDOS`, `IDEMPOTENCIA_TTL_SEGUNDOS` | `1800`, `300`, `86400` | Mismos TTL que el Hito 7 para sesión y ficha |
| `INFLUX_URL`, `INFLUX_DB`, `INFLUX_TOKEN` / `INFLUX_TOKEN_FILE` | `http://127.0.0.1:8181`, `fixture2030_h8`, `../Hito 8/.local/admin.token` | El token viaja solo en el encabezado `Authorization` |
| `IRIS_HOST`, `IRIS_PORT`, `IRIS_NAMESPACE`, `IRIS_USER`, `IRIS_PASSWORD` | `127.0.0.1`, `1972`, `USER`, `fixture_api`, *secreto* | Usuario creado por `scripts/iris_crear_usuario_api.ps1` |

## Timeouts

| Cliente | Configuración |
| --- | --- |
| MongoDB | `serverSelectionTimeoutMS`, `connectTimeoutMS`, `socketTimeoutMS` = timeout |
| Neo4j | `connection_timeout`, `connection_acquisition_timeout`, `max_transaction_retry_time` y timeout de transacción por consulta |
| Cassandra | `connect_timeout`, `control_connection_timeout`, `default_timeout` de la sesión |
| Redis | `socket_timeout` y `socket_connect_timeout`, con reintentos internos desactivados (con los reintentos por defecto la espera llegaba a ~15 s) |
| InfluxDB | `httpx` con timeout total |
| IRIS | `timeout` de `iris.connect` |

La [medición inicial](evidencia/04_dependencia_detenida.txt) registró respuestas 503 en 1,2 a 3,2 s con timeout de 1 s. Con Redis detenido registró 2,05 s con timeout de 3 s. La API distingue `DEPENDENCIA_NO_DISPONIBLE` (503) de `DEPENDENCIA_TIMEOUT` (504). Una conexión a un destino inaccesible puede producir cualquiera de esos resultados según el error del cliente. Las pruebas actuales comprueban la correspondencia entre estado HTTP, código, dependencia y tiempo acotado.

## Verificar las dependencias

```powershell
.\.venv\Scripts\python scripts\verificar_conectividad.py      # sin iniciar la API; sale con 1 si alguna falla
Invoke-RestMethod http://127.0.0.1:8000/api/v1/salud          # con la API iniciada; 503 con detalle si alguna falla
```

En contenedor: `docker compose exec -T api python scripts/verificar_conectividad.py`.

Equivalentes por producto: `mongosh ... --eval "db.adminCommand({ping:1})"`, `cypher-shell "RETURN 1"`, `cqlsh -e "SHOW VERSION"`, `redis-cli PING`, `influxdb3 show databases`, `iris session IRIS -U USER`.

## Seguridad

- Secretos solo en `.env` y en `../Hito 8/.local/admin.token`, ambos ignorados por Git. El repositorio contiene `.env.example` sin valores secretos.
- La contraseña IRIS se pasa por stdin al Terminal del contenedor. PowerShell se configura sin BOM para que el script ObjectScript se interprete correctamente.
- Usuario IRIS propio (`fixture_api`) con rol `fixture_api_rol`: `%DB_USER` (datos de `USER`) y `%Native_ClassExecution` (invocar `CambiarEstado()`), más `GRANT SELECT ON SCHEMA FixtureH9`. No usa `_SYSTEM`.
- Los logs registran tipo de excepción, nunca su mensaje (que podría incluir host o URI). Se verificó que `api.log` no contiene `password` ni `Bearer`.
- Las respuestas de error no exponen consultas, trazas ni nombres internos. El detalle queda en el log por `requestId`.
- La consola escapa todo dato antes de insertarlo en el HTML (los comentarios son texto de usuarios).
- La API solo escucha en `127.0.0.1` y no implementa autenticación de consumidores: no debe exponerse a otra red tal como está.

## Datos que la API agrega a las fuentes

- **Redis**: sesiones (TTL 1800 s), fichas en caché (TTL 300 s) y claves de idempotencia (TTL 24 h), todas bajo `fixture2030:h10:`.
- **Cassandra**: los comentarios publicados (prefijo `API-`). Las pruebas de integración borran los suyos. La colección Postman y la evidencia cURL dejan los propios en `PAR-064`.
- **InfluxDB**: `scripts/cargar_muestra_influx.py` agrega puntos recientes de PAR-001 y PAR-002 cuando venció la muestra del Hito 8.
- **IRIS**: usuario y rol de la API. Las pruebas crean y borran el acta `H10-TEMPORAL`. `PAR-001` no se modifica.
