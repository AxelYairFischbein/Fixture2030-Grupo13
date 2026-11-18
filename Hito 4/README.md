# Hito 4 - Equipos y jugadores en MongoDB

Grupo 13, Fixture 2030. El módulo conserva 64 equipos sintéticos y 1.536 jugadores, con 24 integrantes por plantel. Los documentos describen identidad, nacionalidad, posición, camiseta, altura, pie hábil y estado del plantel. La relación usa `jugadores.equipoId`, con actualización independiente y consultas paginadas.

Los atributos `partidosInternacionales` y `golesInternacionales` se retiraron del modelo, sus validadores y consumidores. No se trasladaron a otro módulo. La API y la interfaz muestran los atributos actuales del jugador. Las [evidencias anteriores](evidencias/README.md) conservan su fecha y el esquema que tenían al ejecutarse.

## Inicio y acceso

Se necesita Docker Desktop con contenedores Linux y el puerto 27017 disponible. Los comandos se ejecutan desde esta carpeta. Antes del primer inicio, copiar `.env.example` a `.env` y configurar credenciales locales. Si ya existe un volumen, usar sus credenciales actuales. Cambiar `.env` no cambia la contraseña almacenada.

```powershell
docker compose config --quiet
docker compose up -d --pull never
docker compose ps
```

`--pull never` conserva la imagen disponible. En una instalación nueva hay que descargar primero la imagen declarada. El volumen `mongodb_data` conserva la base. Para abrir una sesión interactiva sin escribir la contraseña en el comando:

```powershell
docker compose exec mongodb sh -c 'exec mongosh --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin fixture2030'
```

No publicar `.env`, exportaciones, credenciales ni salidas de configuración que las incluyan. La comprobación de Compose usa `--quiet` para evitar mostrarlas.

## Preparación de una base nueva

Solo cuando no haya datos preparados, ejecutar los siguientes archivos en este orden: `init/01_collections.js`, `validations/02_validators.js`, `indexes/03_indexes.js` y `data/02_seed.js`. Para seleccionar cada archivo:

```powershell
$scriptH4 = 'init/01_collections.js'
docker compose exec -T mongodb sh -c 'exec mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin fixture2030 --file "$1"' sh "/workspace/scripts/$scriptH4"
```

La semilla usa identificadores deterministas y reemplazos con `upsert`. Puede restaurar atributos canónicos sobre sus identificadores. No se ejecuta para iniciar un entorno existente ni para migrarlo.

## Consultas, CRUD e integridad

Usar el mismo comando cambiando `$scriptH4` por el archivo correspondiente:

| Archivo bajo `scripts/` | Comprobación |
| --- | --- |
| `verification/07_verify_integrity.js` | Recuentos, identificadores, camisetas, referencias y validadores estrictos |
| `verification/08_test_validation.js` | Rechazo de documentos inválidos y ausencia de residuos |
| `operations/04_demo_crud.js` | Inserción, actualización y eliminación de un equipo y jugador temporales |
| `queries/05_queries.js` | Identificación, filtros, proyección, orden, paginación y agregaciones |
| `performance/06_compare_index.js` | Comparación controlada del índice por nacionalidad y altura |

El CRUD rechaza identificadores temporales preexistentes y solo limpia lo creado por esa ejecución. Actualiza `estadoPlantel` del jugador. Q04 filtra delanteros desde 180 cm, ordena por altura e ID y utiliza `idx_jugadores_posicion_altura`. Q08 agrega cantidad y altura por posición. Q09 resume cantidad y altura del plantel con `$lookup`.

La comparación histórica de P01 examinó 1.536 documentos sin índice y 15 con índice, con los mismos 15 resultados. Ambos tiempos se informaron como 0 ms. Esa evidencia demuestra reducción del trabajo examinado, no una mejora de tiempo medible. No se volvió a medir durante la auditoría.

## Migración de la instalación existente

La revisión del 17 de noviembre respaldó los 1.536 documentos de jugadores, el validador y los índices en `$env:USERPROFILE\docker\backups\fixture-auditoria-20261117\mongodb-jugadores-original.json`. Comprobó la lectura del respaldo y su SHA256 antes de aplicar el cambio. No se recargaron equipos o jugadores.

[migrar_atributos.py](scripts/operations/migrar_atributos.py) usa los drivers y la configuración del contenedor de la API. Sus acciones son `respaldar`, `aplicar` y `restaurar`. Se copia al directorio temporal del contenedor y se ejecuta con `PYTHONPATH=/app`. La secuencia separa respaldo y modificación para permitir conservar una copia en el host:

```powershell
docker cp scripts/operations/migrar_atributos.py grupo13-hito10-api-1:/tmp/migrar_atributos.py
docker exec -e PYTHONPATH=/app grupo13-hito10-api-1 python /tmp/migrar_atributos.py respaldar /tmp/mongodb-jugadores-original.json
$respaldoH4 = Join-Path $env:USERPROFILE 'docker/backups/fixture-auditoria-20261117/mongodb-jugadores-original.json'
# En otra ejecución, elegir un archivo nuevo. No sobrescribir el respaldo conservado.
if (Test-Path $respaldoH4) { throw 'El respaldo de esta ejecución ya existe' }
New-Item -ItemType Directory -Force (Split-Path $respaldoH4)
docker cp grupo13-hito10-api-1:/tmp/mongodb-jugadores-original.json $respaldoH4
Get-FileHash -Algorithm SHA256 $respaldoH4
docker exec grupo13-hito10-api-1 sha256sum /tmp/mongodb-jugadores-original.json
# Continuar solo si ambos SHA256 coinciden.
docker exec -e PYTHONPATH=/app grupo13-hito10-api-1 python /tmp/migrar_atributos.py aplicar /tmp/mongodb-jugadores-original.json
```

La acción `aplicar` instala el validador reducido, retira únicamente los dos campos y sustituye el índice de estadísticas por el de posición y altura. Comprueba que cada otro atributo e identificador coincida con el respaldo. No desactiva la validación de dominio.

Para volver atrás, usar `restaurar` con el mismo respaldo y recuperar también la versión anterior de los consumidores. El script se detiene si encuentra otros atributos modificados después del respaldo. No sobrescribe esos cambios. La tabla de [resultados de la auditoría](../Hito%2013/evidencia/auditoria-20261117/README.md) distingue esta migración de las mediciones anteriores.

## Detención y límites

```powershell
docker compose stop mongodb
docker compose start mongodb
```

El despliegue es una instancia única. Se comprobó integridad documental, pero MongoDB no impone una clave foránea entre colecciones. Los scripts comprueban las referencias y los índices únicos protegen identificadores y camisetas. No se probó un replica set ni sharding.

- [Decisiones documentales](docs/Grupo_13_Hito_4_Decisiones_Documentales_Fixture2030.md)
- [Catálogo de consultas](docs/Catalogo_Consultas.md)
- [Evidencias históricas](evidencias/README.md)
