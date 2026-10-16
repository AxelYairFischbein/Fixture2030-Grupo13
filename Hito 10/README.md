[Repositorio Fixture 2030 - Grupo 13](https://github.com/AxelYairFischbein/Fixture2030-Grupo13)

# Hito 10 - API REST integrada del Fixture 2030

API HTTP (FastAPI) que da acceso controlado a los seis módulos NoSQL de los Hitos 4 a 9, con un adaptador por producto, validación previa a cada consulta, contrato OpenAPI, formato de error común, idempotencia en la escritura, pruebas reproducibles y una **consola web** que consume la misma API.

| Fuente | Hito | Qué expone la API |
| --- | --- | --- |
| MongoDB | 4 | Listado paginado de equipos, ficha y plantel |
| Neo4j | 5 | Partido con equipos, estadio y eventos; agenda de un equipo |
| Cassandra | 6 | Comentarios por ventana de hasta 5 minutos con cursor; publicación idempotente |
| Redis | 7 | Sesiones con TTL, caché de la ficha de equipo, claves de idempotencia |
| InfluxDB | 8 | Resumen temporal agregado por intervalo |
| IRIS | 9 | Acta del partido (objetos) y transición de estado validada por el dominio |

Todos los datos son sintéticos y provienen de las muestras de los hitos anteriores.

## Estructura

```text
Hito 10/
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

## Requisitos

- Windows con PowerShell 5.1+, Docker Desktop (contenedores Linux) y Python 3.12 o posterior (probado con 3.14.0).
- Los servicios de los Hitos 4 a 9 iniciados y con sus muestras cargadas, siguiendo el README de cada hito.
- Puerto `8000` libre en la notebook.

## Atajos por terminal

`fixture.ps1` reúne los pasos habituales. Desde `Hito 10/` en PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass   # una vez por terminal
.\fixture.ps1 todo        # inicia las 6 bases, espera que respondan y levanta la API
.\fixture.ps1 abrir       # interfaz y Swagger en el navegador (en otra terminal)
.\fixture.ps1 ayuda       # lista completa: bases, verificar, api, influx, iris-usuario, pruebas, unitarias, latencia, detener
```

La sección siguiente detalla los mismos pasos uno por uno.

## Puesta en marcha

Todos los comandos se ejecutan desde `Hito 10/` en PowerShell.

1. **Iniciar las fuentes** (cada una con su Compose, sin `-v`, para no borrar volúmenes):

   ```powershell
   foreach ($h in 'Hito 4','Hito 5','Hito 6','Hito 7','Hito 8','Hito 9') { docker compose -f "..\$h\docker-compose.yml" up -d }
   ```

   Cargar las muestras según cada README si el entorno es nuevo (MongoDB: scripts 01-03 y `02_seed.js`; Neo4j: `estructura` y `carga`; Cassandra: `esquema.cql` y `carga_muestra.cql`; IRIS: `LoadDir` y `FixtureH9.Demo.Ejecutar()`; InfluxDB: `inicializacion.py`).

2. **Configurar secretos locales**:

   ```powershell
   Copy-Item .env.example .env
   notepad .env   # completar MONGO_PASSWORD, NEO4J_PASSWORD e IRIS_PASSWORD (letras y números, 12+)
   ```

   `.env` está en `.gitignore`. El token de InfluxDB se lee de `..\Hito 8\.local\admin.token` (también ignorado).

3. **Crear el usuario IRIS de la API** (una vez por instancia; rol mínimo `%DB_USER` + `%Native_ClassExecution` y `SELECT` sobre `FixtureH9`):

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\iris_crear_usuario_api.ps1
   ```

4. **Si la muestra de InfluxDB del Hito 8 venció** (retención de 7 días), agregar puntos recientes sin tocar la original:

   ```powershell
   .\.venv\Scripts\python scripts\cargar_muestra_influx.py   # después del paso 5, que crea el .venv
   ```

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
- **Partido**: detalle y eventos (Neo4j), gráfico de posesión y totales por intervalo (InfluxDB), lectura de comentarios por ventana con "Cargar más" por cursor (Cassandra) y publicación con `Idempotency-Key`, con un botón para reintentar el mismo envío y comprobar que no duplica.
- **Sesiones**: abrir, consultar (TTL restante) y cerrar sesiones (Redis).
- **Actas**: acta del partido con árbitro y eventos (IRIS) y botones de transición; las inválidas muestran el 409 sin modificar el acta.

La barra inferior muestra en cada llamada el método, el estado HTTP, la duración, el `X-Request-ID` y las operaciones que el servidor ejecutó en cada fuente (`meta.fuentes`), y permite ver el JSON completo.

## Pruebas

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ejecutar_pruebas.ps1                 # unitarias + integración
powershell -ExecutionPolicy Bypass -File .\scripts\ejecutar_pruebas.ps1 -SoloUnitarias  # sin bases de datos
```

Resultado registrado: **36 pruebas aprobadas** ([evidencia](docs/evidencia/02_pruebas.txt)). Detalle en [tests/README.md](tests/README.md).

**Postman**: importar `postman/fixture2030_collection.json` y ejecutar la colección completa en orden con la API iniciada (32 requests con aserciones). Por línea de comandos: `npx newman run postman\fixture2030_collection.json`. La colección publica un comentario real en `PAR-064` en cada corrida (con clave nueva).

## Detener sin perder datos

- API: `Ctrl+C` en su consola.
- Fuentes: `docker compose -f "..\Hito N\docker-compose.yml" stop`. **No usar `down -v`**, que elimina volúmenes.

## Limitaciones conocidas

- Entorno local de un nodo por producto, sin autenticación de consumidores ni TLS; la API escucha solo en `127.0.0.1`.
- El healthcheck del contenedor Neo4j del Hito 5 figura `unhealthy` en Windows porque `cypher.sh` se descarga con fin de línea CRLF; la base responde normalmente (ver `docs/evidencia/01_conectividad.txt`). No se modificó el Hito 5.
- Las transiciones de un acta IRIS son permanentes; las pruebas las ejercitan sobre un acta temporal que se borra al terminar.
- La carpeta `Hito 10a/` del repositorio es una copia del Hito 9 con la consigna en PDF; esta entrega vive en `Hito 10/`.
