# Hito 5 · Módulo de Grafos del Fixture 2030

Grupo 13. Módulo local de Neo4j para consultar planteles, enfrentamientos, programación por estadio e incidencias con participantes. La muestra contiene **64 equipos, 1.536 jugadores (24 por equipo), 64 partidos, 8 estadios y 128 eventos sintéticos**: 1.800 nodos y 2.112 relaciones. No representa el fixture oficial.

La ejecución técnica de referencia es `20260910T010744736Z`, realizada con **Neo4j 2026.07.1 Community**, imagen `neo4j:latest`. El módulo funciona sin MongoDB, API, frontend ni extensiones de Neo4j.

## Requisitos previos

- Windows con PowerShell 5.1 o superior.
- Docker Desktop con el motor de contenedores Linux iniciado y Docker Compose disponible.
- Acceso a Internet para descargar la imagen por primera vez.
- Puertos locales 7474 y 7687 libres.

Los comandos siguientes se ejecutan en PowerShell. Desde la raíz de `Fixture`, entrar en la carpeta:

```powershell
Set-Location -LiteralPath '.\Hito 5'
docker version
docker compose version
```

## Estructura de entrega

```text
Hito 5/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
├── queries/
│   ├── 01_constraints.cypher
│   ├── 02_load.cypher
│   ├── 03_crud.cypher
│   ├── 04_graph_queries.cypher
│   ├── 05_analysis.cypher
│   ├── 06_verify.cypher
│   ├── 07_browser.cypher
│   ├── 08_index_plan.cypher
│   └── 09_snapshot.cypher
├── scripts/
│   ├── common.ps1
│   ├── ejecutar.ps1
│   ├── container/
│   │   └── cypher.sh
│   └── verification/
│       ├── generar_evidencias.ps1
│       └── resultados_esperados.json
└── docs/
    ├── modelo_grafo.md
    ├── decisiones.md
    ├── catalogo_consultas.md
    ├── trazabilidad.md
    └── evidencia/
        ├── README.md
        ├── ultima_ejecucion.json
        ├── 20260910T010744736Z/
        ├── 01_browser_carga.png
        ├── 02_browser_subgrafo_general.png
        ├── 03_browser_recorrido_jugador_estadio.png
        └── 04_browser_consulta_rivales.png
```

La carpeta de la ejecución contiene el resumen y las salidas técnicas detalladas en [el README de evidencias](docs/evidencia/README.md). La carga se define en Cypher y no necesita archivos de importación externos.

## Preparar el ambiente

Crear `.env` a partir del ejemplo, conservando una configuración existente:

```powershell
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
docker compose config --quiet
docker compose up -d
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 esperar
docker compose ps
```

`.env.example` define `NEO4J_AUTH=neo4j/fixture2030-g13-local`. Son credenciales del laboratorio; `.env` queda ignorado por Git. Si el volumen ya está inicializado, las credenciales deben coincidir con las guardadas en la base: cambiar `.env` no cambia su contraseña.

El estado del contenedor debe indicar `healthy`. Los datos se guardan en `grupo13-hito5_neo4j_data` y los logs en `grupo13-hito5_neo4j_logs`. Para consultar mensajes del servicio:

```powershell
docker compose logs --tail 40 neo4j
```

## Crear la estructura y cargar datos

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 estructura
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 carga
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 verificar
```

`estructura` crea seis restricciones de unicidad y un índice para las fechas de los partidos. `carga` utiliza `MERGE` y devuelve L01=64 equipos, L02=1536 jugadores, L03=8 estadios, L04=64 partidos y L05=128 eventos.

Para repetir la carga:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 carga
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 verificar
```

Los recuentos deben mantenerse y los 44 controles deben devolver `TRUE`. La ejecución de referencia comprobó que ambas cargas dejaron el mismo contenido, sin duplicados. La recarga restablece las propiedades definidas por el conjunto de prueba; los datos agregados por fuera de la carga requieren una revisión específica.

## CRUD, consultas y análisis

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 crud
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 verificar
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 consultas
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 analisis
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 plan
```

El CRUD crea la incidencia temporal `CRUD-G13-EVT-001`, consulta sus participantes, corrige el minuto, actualiza una propiedad de relación, reasigna al jugador que entra y elimina la incidencia. Al finalizar, el conjunto de prueba queda intacto.

`consultas` ejecuta Q01–Q13: planteles, rivales, partidos por estadio, agenda e incidencias. Incluye filtros, orden, paginación y conteos. Q04 recorre dos relaciones consecutivas y Q08 recorre tres.

`analisis` obtiene un camino mínimo de cuatro relaciones entre EQ-001 y EQ-004 y comprueba que EQ-001 y EQ-005 no están conectados mediante encuentros en esta muestra. `plan` muestra el uso del índice temporal de Q09. Los objetivos y resultados están en [el catálogo de consultas](docs/catalogo_consultas.md).

## Neo4j Browser y evidencia visual

Abrir [Neo4j Browser](http://localhost:7474) y conectarse a `bolt://localhost:7687`, base `neo4j`, con las credenciales de `.env`. Ambos puertos están publicados en `127.0.0.1`.

Las consultas de carga, visualización del subgrafo, recorrido de relaciones y búsqueda de rivales se ejecutaron en Neo4j Browser. Las capturas correspondientes se encuentran en `docs/evidencia/`:

- [Recuentos por etiqueta](docs/evidencia/01_browser_carga.png).
- [Subgrafo general de G01](docs/evidencia/02_browser_subgrafo_general.png).
- [Recorrido jugador → equipo → partido → estadio](docs/evidencia/03_browser_recorrido_jugador_estadio.png).
- [Rivales de EQ-001 y partidos correspondientes](docs/evidencia/04_browser_consulta_rivales.png).

Para repetirlas, ejecutar por separado B01, B02 y B03 de [07_browser.cypher](queries/07_browser.cypher), y Q04 de [04_graph_queries.cypher](queries/04_graph_queries.cypher). Usar la vista Graph para B01/B02 y Table para B03/Q04.

## Persistencia y detención

Para comprobar la persistencia, reiniciar sin repetir la carga:

```powershell
docker compose restart neo4j
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 esperar
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 verificar
docker compose ps
```

La ejecución de referencia confirmó que los nodos, relaciones y propiedades se conservaron después del reinicio.

Para detener el ambiente conservando los volúmenes:

```powershell
docker compose stop neo4j
```

Para volver a iniciarlo:

```powershell
docker compose start neo4j
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 esperar
```

## Alcance y documentación

La muestra representa dos jornadas de 16 grupos ficticios de cuatro equipos. Cada equipo disputa dos partidos y cada estadio recibe ocho. Los eventos son sustituciones; no se almacenan marcadores ni estadísticas acumuladas. La pertenencia al plantel no implica haber jugado un partido.

El ambiente corresponde a un único servicio local. Las restricciones garantizan identificadores únicos y las consultas de integridad comprueban propiedades y relaciones. La imagen `latest` puede cambiar; corresponde verificar la compatibilidad al actualizarla.

- [Modelo de grafo](docs/modelo_grafo.md).
- [Decisiones técnicas y limitaciones](docs/decisiones.md).
- [Catálogo de consultas](docs/catalogo_consultas.md).
- [Trazabilidad de RF1–RF11 y RNF1–RNF8](docs/trazabilidad.md).
- [Evidencia técnica y visual](docs/evidencia/README.md).
