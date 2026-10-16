# Hito 10 · API REST integrada del Fixture 2030

Grupo 13 · Ingeniería de Datos II · datos sintéticos

API HTTP (FastAPI) que expone 20 casos de uso del Fixture Mundial 2030 sobre las seis fuentes NoSQL de los hitos anteriores: MongoDB (Hito 4), Neo4j (Hito 5), Cassandra (Hito 6), Redis (Hito 7), InfluxDB 3 (Hito 8) e InterSystems IRIS (Hito 9). Cada endpoint ejecuta una consulta fija de un adaptador específico; no hay endpoints genéricos.

| Documento | Contenido |
|---|---|
| [`docs/casos_de_uso.md`](docs/casos_de_uso.md) | Contrato acordado: consumidores, fichas CU-01…CU-20, códigos HTTP, idempotencia, decisiones. |
| [`docs/arquitectura_y_adaptadores.md`](docs/arquitectura_y_adaptadores.md) | Capas, diagrama, qué encapsula cada adaptador, integraciones entre fuentes. |
| [`docs/contratos_y_errores.md`](docs/contratos_y_errores.md) | OpenAPI, mapa de endpoints, validación, formato de error, idempotencia. |
| [`docs/conectividad_y_configuracion.md`](docs/conectividad_y_configuracion.md) | Variables, puertos, timeouts, secretos, API en contenedor, cómo detener. |
| [`docs/pruebas_y_evidencia.md`](docs/pruebas_y_evidencia.md) | Cómo se probó, resultados, latencias medidas y **matriz de trazabilidad RF/RNF**. |
| [`openapi/openapi.yaml`](openapi/openapi.yaml) | Contrato OpenAPI versionado. |
| [`postman/fixture2030_collection.json`](postman/fixture2030_collection.json) | Colección de Postman con éxito y errores por CU. |
| [`iris/README.md`](iris/README.md) | Clase envoltorio `FixtureH10.Servicio` para CU-19. |

## 1. Requisitos

- Windows 10/11 con PowerShell 5.1 o superior (los scripts son `.ps1`) y `curl.exe` (incluido en Windows).
- **Python 3.13**, invocable como `python`.
- **Docker Desktop** con los contenedores de los Hitos 4 a 9 creados y con sus muestras cargadas. Cassandra, InfluxDB e IRIS juntos necesitan varios GB de RAM: si la máquina no alcanza, se puede levantar solo lo que se quiera probar (la API arranca igual y responde 503 en lo que falte).
- Opcional: Postman (para importar la colección) o `newman` (`npm install -g newman`) para ejecutarla desde `scripts/ejecutar_pruebas.ps1`.

## 2. Preparar las fuentes (una sola vez)

Cada hito tiene su `docker-compose.yml` y su README con el procedimiento de carga. Desde la raíz del repositorio:

| Hito | Levantar | Cargar la muestra (ver el README del hito) |
|---|---|---|
| 4 · MongoDB | `cd "Hito 4"; docker compose up -d` | Scripts `init`, `validations`, `indexes` y `data/02_seed.js` con `mongosh` dentro del contenedor. |
| 5 · Neo4j | `cd "Hito 5"; docker compose up -d` | `.\scripts\ejecutar.ps1 esperar`, `estructura`, `carga`. |
| 6 · Cassandra | `cd "Hito 6"; docker compose up -d` | `docker compose exec -T cassandra cqlsh -f /scripts/esquema.cql` y `carga_muestra.cql` (esperar 1–2 min a que acepte conexiones). |
| 7 · Redis | `cd "Hito 7"; docker compose up -d --wait` | No hace falta cargar datos para la API: las sesiones de prueba las crea `Hito 10/scripts/crear_sesiones_prueba.ps1` y la caché de CU-01 se llena sola. |
| 8 · InfluxDB 3 | `cd "Hito 8"; docker compose up -d influxdb` | `scripts/inicializacion.py` (crea el token en `Hito 8/.local/admin.token`), `generacion_puntos.py` y `carga_lotes.py`. Los puntos tienen fechas de la carga, no de 2030, y la retención es de 7 días: pasado ese plazo, CU-15/16/17 responden 200 vacío hasta generar una muestra nueva. |
| 9 · IRIS | `cd "Hito 9"; docker compose up -d iris` | Compilar las clases `FixtureH9` y ejecutar la demo según el README. |

Después, cargar en IRIS la clase envoltorio del Hito 10 (necesaria solo para CU-19), con la API ya instalada (paso 3):

```powershell
cd "Hito 10"
.\scripts\cargar_servicio_iris.ps1
```

## 3. Instalar y configurar la API

```powershell
cd "Hito 10"
.\scripts\iniciar_api.ps1 -Instalar      # crea .venv, instala requirements.txt y arranca la API
```

La primera vez va a detenerse pidiendo el archivo `.env`:

```powershell
Copy-Item .env.example .env
notepad .env
```

Completar `MONGO_USER`, `MONGO_PASSWORD`, `NEO4J_USER`, `NEO4J_PASSWORD`, `IRIS_USER` e `IRIS_PASSWORD` con las credenciales **locales** de los contenedores (las de `Hito 5/.env` para Neo4j, etc.). `INFLUX_TOKEN_FILE` ya apunta a `../Hito 8/.local/admin.token`. `.env` está ignorado por git: no se versiona. Si falta una variable, la API no arranca y el mensaje dice cuál. Detalle de cada variable en [`docs/conectividad_y_configuracion.md`](docs/conectividad_y_configuracion.md).

## 4. Orden de ejecución

Todo desde la carpeta `Hito 10`:

1. **Levantar las fuentes** que se van a usar (`docker compose up -d` en cada hito; ver el paso 2).
2. **Levantar la API**: `.\scripts\iniciar_api.ps1` (puerto 8000; `-Puerto N` para cambiarlo, `-Recargar` para desarrollo).
3. **Verificar la conectividad** en otra terminal: `.\scripts\verificar_conectividad.ps1`. Muestra cada dependencia como `disponible`/`no_disponible`/`no_configurada`, el catálogo de partidos (64 con la muestra) y qué levantar si algo falla.
4. **Explorar el contrato**: Swagger UI en <http://127.0.0.1:8000/docs> (ReDoc en `/redoc`).
5. **Crear sesiones de prueba** para las operaciones protegidas: `.\scripts\crear_sesiones_prueba.ps1`. Crea sesiones `lector`, `moderador` y `operador` con IDs aleatorios en el Redis del Hito 7 y los guarda **solo** en `.local/sesiones_prueba.json` y `.local/postman_entorno_local.json` (ignorados por git). Vencen a los 30 minutos: volver a ejecutarlo si hace falta.
6. **Postman**: *Import* → `postman/fixture2030_collection.json` y el entorno `.local/postman_entorno_local.json`; seleccionar el entorno y ejecutar la colección con el *Runner*. La carpeta *Dependencias caídas (manual)* requiere detener un contenedor a mano y no se corre en el Runner normal. Para CU-19 con transiciones reales, la variable `partidoTemporal` debe ser un acta temporal (la crea `ejecutar_pruebas.ps1`).
7. **Pruebas automáticas**: `.\scripts\ejecutar_pruebas.ps1` corre las unitarias, las de integración (las que no encuentran su contenedor se informan como omitidas) y, si `newman` está instalado, la colección. Opciones: `-SinIntegracion`, `-SinNewman`.
8. **Evidencia** (opcional): `.\scripts\evidencia_<fuente>.ps1 [-ConDetencion]` para `mongo`, `redis`, `neo4j`, `cassandra`, `influx`, `iris`, más `evidencia_api.ps1` y `medir_latencia.ps1`. Ver [`docs/pruebas_y_evidencia.md`](docs/pruebas_y_evidencia.md).

Ningún paso imprime contraseñas, el token ni los IDs de sesión completos.

## 5. Cómo se prueba

| Método | Qué cubre | Cómo |
|---|---|---|
| `pytest -m "not integration"` | Unitarias con adaptadores falsos (`tests/falsos.py`), sin Docker: éxito, 400, 404, vacío, 401/403, 409, 503/504 por fuente, `X-Request-Id`, formato de error, OpenAPI = app. | `.venv\Scripts\python.exe -m pytest -m "not integration"` |
| `pytest -m integration` | Contra los contenedores reales (`tests/integracion/`), con los resultados esperados de cada ficha. | `.venv\Scripts\python.exe -m pytest -m integration` |
| Postman / newman | Request exitosa y escenarios de error por CU, con tests de código y estructura. | Paso 6 o `ejecutar_pruebas.ps1`. |
| Scripts de evidencia | `curl.exe -i` contra la API real, incluida la detención de cada contenedor. | Paso 8. |

## 6. Detener sin borrar datos

- **API**: `Ctrl+C` en la terminal donde corre `iniciar_api.ps1`. No guarda estado propio.
- **Fuentes**: `docker compose stop` en cada `Hito N/` (o `docker compose down`, que borra los contenedores pero **conserva los volúmenes**).
- **No usar** `docker compose down -v`, `docker volume rm` ni `docker system prune --volumes`: borran los datos y obligan a recargar las muestras.

## 7. Estructura

```
Hito 10/
├── README.md
├── .env.example                # nombres de variables con valores de relleno (.env no se versiona)
├── requirements.txt            # versiones fijadas
├── pytest.ini                  # marcador "integration"
├── app/
│   ├── main.py                 # create_app: lifespan, middleware, manejadores, routers
│   ├── middleware.py           # X-Request-Id y log de acceso
│   ├── manejadores.py          # formato de error único
│   ├── errors.py               # excepciones de dominio
│   ├── dependencias.py         # adaptadores en app.state → Depends
│   ├── openapi.py              # ajustes y exportación del contrato
│   ├── config/                 # Settings (pydantic-settings) y logging
│   ├── routes/                 # un router por módulo
│   ├── services/               # casos de uso, catálogo de partidos, sesiones
│   ├── adapters/               # mongo_, neo4j_, cassandra_, redis_, influx_, iris_adaptador.py
│   └── schemas/                # modelos Pydantic de request/response y de error
├── iris/                       # FixtureH10.Servicio.cls (envoltorio de CambiarEstado para CU-19)
├── openapi/openapi.yaml
├── postman/fixture2030_collection.json
├── tests/                      # unitarias (test_*.py + falsos.py) e integracion/
├── scripts/                    # iniciar_api, verificar_conectividad, ejecutar_pruebas, evidencia_*, …
└── docs/                       # casos de uso, arquitectura, contratos, conectividad, pruebas, evidencia/
```

## 8. Estado

El estado de cada requisito del enunciado (RF1–RF20, RNF1–RNF18), con su prueba o evidencia y lo que quedó pendiente, está en la [matriz de trazabilidad](docs/pruebas_y_evidencia.md#7-matriz-de-trazabilidad).
