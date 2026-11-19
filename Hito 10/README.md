[Repositorio Fixture 2030 - Grupo 13](https://github.com/AxelYairFischbein/Fixture2030-Grupo13)

# Hito 10 - API REST integrada del Fixture 2030

API HTTP (FastAPI) que da acceso controlado a los seis módulos NoSQL de los Hitos 4 a 9, con un adaptador por producto, validación previa a cada consulta, contrato OpenAPI, formato de error común, idempotencia en la escritura, pruebas reproducibles y una **consola web** que consume la misma API.

| Fuente | Hito | Qué expone la API |
| --- | --- | --- |
| MongoDB | 4 | Listado paginado de equipos, ficha y plantel |
| Neo4j | 5 | Partido con equipos, estadio y eventos, y agenda de un equipo |
| Cassandra | 6 | Comentarios por ventana de hasta 5 minutos con cursor y publicación idempotente |
| Redis | 7 | Sesiones con TTL, caché de la ficha de equipo, claves de idempotencia |
| InfluxDB | 8 | Resumen temporal agregado por intervalo |
| IRIS | 9 | Acta del partido (objetos) y transición de estado validada por el dominio |

Todos los datos son sintéticos y provienen de las muestras de los hitos anteriores.

## Estructura

```text
Hito 10/
├── fixture.cmd / fixture.ps1   # un comando para preparar, levantar, probar y detener todo
├── Dockerfile, docker-compose.yml, .dockerignore, .gitattributes   # API en contenedor
├── README.md, requirements.txt, pytest.ini, .env.example, .gitignore
├── app/
│   ├── main.py            # ensamblado, middleware X-Request-ID, logs, manejo de errores, OpenAPI
│   ├── routes.py          # contrato HTTP y validación de entrada (sin acceso a datos)
│   ├── services.py        # casos de uso y reglas (sin HTTP ni drivers)
│   ├── schemas.py         # modelos de request/response (fuente del OpenAPI)
│   ├── errors.py          # jerarquía de errores y formato común
│   ├── contexto.py        # requestId, trazas por fuente y traducción de errores de driver
│   ├── config.py          # configuración por variables de entorno (.env local)
│   └── adapters/          # único lugar que conoce cada driver
│       ├── mongo_equipos.py, neo4j_partidos.py, cassandra_comentarios.py
│       └── redis_kv.py, influx_estadisticas.py, iris_actas.py
├── web/index.html         # consola gráfica (sin dependencias externas)
├── openapi/openapi.yaml   # contrato exportado desde la aplicación
├── postman/fixture2030_collection.json
├── tests/unit/            # sin bases: contrato, validación, errores, idempotencia
├── tests/integration/     # contra las seis fuentes reales
├── scripts/               # iniciar, verificar, probar, exportar, medir, preparar IRIS e InfluxDB
└── docs/                  # análisis del hito y evidencia/
```

## Documentación

- [Casos de uso y mapa de endpoints](docs/casos_de_uso.md)
- [Arquitectura y adaptadores](docs/arquitectura_y_adaptadores.md) (incluye respuestas a las preguntas guía)
- [Contratos, validación, errores e idempotencia](docs/contratos_y_errores.md)
- [Conectividad, configuración y seguridad](docs/conectividad_y_configuracion.md)
- [Pruebas, evidencia y rendimiento](docs/pruebas_y_evidencia.md)
- [Evaluación de conectividad de la API](../Hito%2011/README.md)

## Inicio con datos existentes

Con Docker Desktop iniciado, arrancar los contenedores existentes sin cargar muestras:

```powershell
docker start fixture2030-mongodb grupo13-hito5-neo4j-1 grupo13-hito6-cassandra-1 grupo13-hito7-redis-1 grupo13-hito8-influxdb-1 grupo13-hito9-iris-1
docker compose up -d --build api
Invoke-RestMethod http://127.0.0.1:8000/api/v1/salud
```

Esperar el arranque de Cassandra y repetir salud si aún devuelve 503. `fixture.cmd todo`, `preparar` e `influx` cargan datos. No son necesarios para encender un entorno ya preparado. Un resultado vacío de InfluxDB con HTTP 200 puede indicar que venció su retención de siete días.

## Preparación de un entorno nuevo

Requisitos: **Windows 10/11 y Docker Desktop** iniciado (contenedores Linux). No hace falta instalar Python ni ninguna base. Se recomiendan 16 GB de RAM: Cassandra, IRIS, Neo4j e InfluxDB corren a la vez.

Clonar el repositorio, abrir una terminal (PowerShell o cmd) en `Hito 10` y ejecutar:

```powershell
.\fixture.cmd todo
```

Antes de usar ese comando, configurar las credenciales locales de [MongoDB](../Hito%204/README.md) y [Neo4j](../Hito%205/README.md) en sus respectivos `.env`. Usarlo solo sobre un entorno nuevo o cuya recarga se haya decidido expresamente. La secuencia:

1. Comprueba que Docker responda y que los puertos 27017, 7474, 7687, 9042, 16379, 8181, 1972, 52773 y 8000 no estén ocupados por otro programa.
2. Comprueba las credenciales locales de los Hitos 4 y 5. Prepara las carpetas de InfluxDB e IRIS. Si falta `Hito 10/.env`, lo genera con esas credenciales y una clave IRIS aleatoria
3. Inicia los contenedores de los Hitos 4 a 9 y espera a cada base.
4. Carga las muestras con los scripts de cada hito (MongoDB, Neo4j, Cassandra, clases y demo de IRIS), corrige el `chown` de IRIS si la carpeta es nueva, crea el usuario IRIS de la API y el token y la base de InfluxDB.
5. Construye y levanta la API en un contenedor, agrega 30 minutos de estadísticas recientes y abre <http://127.0.0.1:8000/>.

La primera vez tarda varios minutos (descarga de imágenes y arranque de Cassandra e IRIS). Las siguientes, menos de un minuto.

| Comando | Qué hace |
| --- | --- |
| `.\fixture.cmd todo` | Todo lo anterior |
| `.\fixture.cmd preparar` | Solo bases y datos |
| `.\fixture.cmd api` | Reconstruye y levanta la API |
| `.\fixture.cmd abrir` | Abre la interfaz y Swagger |
| `.\fixture.cmd estado` | Contenedores y salud de la API |
| `.\fixture.cmd verificar` | Conectividad y latencia de cada base |
| `.\fixture.cmd influx` | Estadísticas recientes (si el gráfico sale vacío) |
| `.\fixture.cmd pruebas` / `unitarias` | Pruebas dentro del contenedor |
| `.\fixture.cmd latencia` | Medición de latencia |
| `.\fixture.cmd logs` | Logs de la API |
| `.\fixture.cmd detener` | Detiene API y bases sin borrar datos |

`fixture.cmd` llama a `fixture.ps1` sin depender de la política de ejecución de PowerShell. La API en contenedor llega a las bases por `host.docker.internal` ([docker-compose.yml](docker-compose.yml)).

## Modo sin Docker para la API (opcional)

La API también puede ejecutarse con Python 3.12+ en la notebook. Es una alternativa al contenedor de la API. Detener primero `docker compose stop api` para liberar el puerto 8000. Los pasos siguientes incluyen preparación opcional de datos y no deben repetirse sobre muestras existentes.

## Puesta en marcha manual

Todos los comandos se ejecutan desde `Hito 10/` en PowerShell.

1. **Iniciar las fuentes** (cada una con su Compose, sin `-v`, para no borrar volúmenes):

   ```powershell
   foreach ($h in 'Hito 4','Hito 5','Hito 6','Hito 7','Hito 8','Hito 9') { docker compose -f "..\$h\docker-compose.yml" up -d }
   ```

   Cargar las muestras según cada README si el entorno es nuevo. MongoDB usa scripts 01-03 y `02_seed.js`, Neo4j usa `estructura` y `carga`, Cassandra usa `esquema.cql` y `carga_muestra.cql`, IRIS usa `LoadDir` y `FixtureH9.Demo.Ejecutar()`, e InfluxDB usa `inicializacion.py`.

2. **Configurar secretos locales**:

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   notepad .env   # completar MONGO_PASSWORD, NEO4J_PASSWORD e IRIS_PASSWORD (letras y números, 12+)
   ```

   `.env` está en `.gitignore`. El token de InfluxDB se lee de `..\Hito 8\.local\admin.token` (también ignorado).

3. **Crear el usuario IRIS de la API** (una vez por instancia, con rol mínimo `%DB_USER` + `%Native_ClassExecution` y `SELECT` sobre `FixtureH9`):

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\iris_crear_usuario_api.ps1
   ```

4. **Si la muestra de InfluxDB venció** por retención de siete días, podés preparar cinco minutos de datos sintéticos para la demostración. Desde esta carpeta, con InfluxDB iniciado y el token local configurado, ejecutar:

   ```powershell
   python scripts/cargar_muestra_influx.py --partido 1 --partido 2 --partido 3 --partido 4 --partido 5 --partido 6 --minutos 5 --paso 60
   ```

   En la consola, consultar un partido entre `PAR-001` y `PAR-006` con intervalo `1m` y ambas fechas vacías. El script omite un partido si ya tiene puntos en la ventana de carga. Cada `--partido` identifica un partido de la primera jornada. Sin ese parámetro, el script prepara `PAR-001` y `PAR-002`.

5. **Iniciar la API** (crea `.venv` e instala dependencias la primera vez):

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\iniciar_api.ps1
   ```

6. **Verificar conectividad**: `.\.venv\Scripts\python scripts\verificar_conectividad.py` o `GET http://127.0.0.1:8000/api/v1/salud`.

| Qué | Dónde |
| --- | --- |
| Consola gráfica | <http://127.0.0.1:8000/> |
| Swagger UI | <http://127.0.0.1:8000/docs> |
| OpenAPI en vivo | <http://127.0.0.1:8000/openapi.json> (versionado en `openapi/openapi.yaml`) |

## Consola gráfica

La página `web/index.html` la sirve la propia API, por lo que no requiere CORS ni otra instalación. Usa exclusivamente los endpoints públicos:

- **Equipos**: listado paginado por confederación (MongoDB), ficha con indicador de caché `HIT/MISS/BYPASS` e invalidación (Redis), plantel filtrable y agenda (Neo4j). Un partido de la agenda abre su detalle.
- **Partido**: detalle y eventos (Neo4j), gráfico de posesión y totales por intervalo (InfluxDB), y comentarios paginados por cursor (Cassandra). **Publicar** y **Reintentar el mismo envío** usan la misma clave para el mismo partido, usuario y texto. La API devuelve el comentario original mientras esa clave siga vigente en Redis.
- **Sesiones**: abrir, consultar y cerrar sesiones (Redis). La consola descuenta el TTL y retira las sesiones cerradas o vencidas. Los roles lector y moderador son datos de demostración, sin permisos asociados en este entorno.
- **Actas**: acta del partido con árbitro y eventos (IRIS) y botones de transición. Las inválidas muestran el 409 sin modificar el acta.

La barra inferior muestra en cada llamada el método, el estado HTTP, la duración, el `X-Request-ID` y las operaciones que el servidor ejecutó en cada fuente (`meta.fuentes`), y permite ver el JSON completo.

## Pruebas

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ejecutar_pruebas.ps1                 # unitarias + integración
powershell -ExecutionPolicy Bypass -File .\scripts\ejecutar_pruebas.ps1 -SoloUnitarias  # sin bases de datos
```

Resultado registrado: **36 pruebas aprobadas** ([evidencia](docs/evidencia/02_pruebas.txt)). Detalle en [tests/README.md](tests/README.md).

**Postman**: importar `postman/fixture2030_collection.json` y ejecutar la colección completa en orden con la API iniciada (32 requests con aserciones). Por línea de comandos: `npx newman run postman\fixture2030_collection.json`. La colección publica un comentario real en `PAR-064` en cada corrida (con clave nueva).

## Detener sin perder datos

- API en contenedor: `docker compose stop api`.
- API en Python local: `Ctrl+C` en su consola.
- Fuentes: `docker compose -f "..\Hito N\docker-compose.yml" stop`. **No usar `down -v`**, que elimina volúmenes.

## Limitaciones conocidas

- Entorno local de un nodo por producto, sin autenticación de consumidores ni TLS. La API escucha solo en `127.0.0.1`.
- Las evidencias iniciales registraron un healthcheck de Neo4j afectado por CRLF. El estado depende del checkout y debe verificarse con `docker ps` y una consulta real.
- Las transiciones de un acta IRIS son permanentes. Las pruebas las ejercitan sobre un acta temporal que se borra al terminar.
- `PAR-001` de Neo4j está FINALIZADO y el acta de IRIS está PENDIENTE por el diseño de dos muestras independientes. No hay sincronización entre ellas. El [Hito 13](../Hito%2013/README.md) explica su alcance y el monitoreo de `/metrics`.

## Revisión integrada del 17 de noviembre

El plantel de MongoDB y su contrato HTTP ya no incluyen partidos o goles internacionales. Se conservaron identidad, atributos del jugador y estado del plantel. La interfaz existente muestra esos mismos campos. El adaptador temporal consulta `estadisticas_equipo_v2`, con dos tags. Cassandra usa el volumen nombrado del Hito 6, conservando los keyspaces y la versión del motor.

La API mantiene rutas, errores, límites, sesión, caché e idempotencia. Estos comportamientos participan en las comprobaciones de recuperación y evitan duplicar comentarios al reintentar. La consola y los comandos de preparación son recursos opcionales. La entrada principal para explicar los casos de uso es Swagger, con sus adaptadores y contratos. No se amplió la interfaz ni la orquestación.

La [auditoría integrada](../Hito%2013/evidencia/auditoria-20261117/README.md) identifica la versión nueva, las migraciones, las pruebas reales y las limitaciones. Las mediciones anteriores de este hito conservan su alcance original.
