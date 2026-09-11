# Hito 5 · Módulo de Grafos del Fixture 2030

En este hito usamos Neo4j para consultar planteles, rivales, partidos por estadio e incidencias con sus participantes. La muestra contiene **64 equipos, 1.536 jugadores, 64 partidos, 8 estadios y 128 eventos**, con un total de **1.800 nodos y 2.112 relaciones**.

Los datos son ficticios y representan dos jornadas de 16 grupos de cuatro equipos. El módulo funciona de forma local e independiente de MongoDB, sin API, frontend ni extensiones de Neo4j.

## Requisitos previos

- Windows con PowerShell 5.1 o superior.
- Docker Desktop iniciado con contenedores Linux y Docker Compose disponible.
- Acceso a Internet para descargar la imagen por primera vez.
- Puertos locales 7474 y 7687 libres.

Desde la raíz de `Fixture`, entrar en la carpeta del hito:

```powershell
Set-Location -LiteralPath '.\Hito 5'
```

## Preparar el ambiente

Crear `.env` a partir del ejemplo si todavía no existe, iniciar el servicio y esperar a Neo4j:

```powershell
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
docker compose config --quiet
docker compose up -d
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 esperar
docker compose ps
```

El contenedor debe mostrar el estado `healthy`. El ejemplo usa `NEO4J_AUTH=neo4j/fixture2030-g13-local` y `.env` queda ignorado por Git. Si la base ya existe, hay que usar sus credenciales, porque cambiar `.env` no modifica la contraseña guardada.

## Crear la estructura, cargar y verificar

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 estructura
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 carga
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 verificar
```

La estructura incluye seis restricciones de unicidad y un índice temporal. La carga usa `MERGE` y puede repetirse con los mismos comandos sin generar duplicados. La verificación comprueba las cantidades y la integridad del grafo.

## CRUD, consultas y análisis

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 crud
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 verificar
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 consultas
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 analisis
```

El CRUD crea, lee, actualiza y elimina la incidencia temporal `CRUD-G13-EVT-001`. Q01 a Q13 consultan planteles, rivales, agenda e incidencias. A01 y A02 analizan caminos entre equipos a través de sus partidos.

## Neo4j Browser

Abrir [Neo4j Browser](http://localhost:7474) y conectarse a `bolt://localhost:7687`, base `neo4j`, con el usuario y la contraseña de `.env`.

Las cuatro capturas muestran las consultas ejecutadas:

- [Recuentos por etiqueta](docs/evidencia/01_browser_carga.png).
- [Subgrafo general de G01](docs/evidencia/02_browser_subgrafo_general.png).
- [Recorrido jugador → equipo → partido → estadio](docs/evidencia/03_browser_recorrido_jugador_estadio.png).
- [Rivales de EQ-001 y sus partidos](docs/evidencia/04_browser_consulta_rivales.png).

Para repetirlas, ejecutar por separado B01, B02 y B03 de [07_browser.cypher](queries/07_browser.cypher) y Q04 de [04_graph_queries.cypher](queries/04_graph_queries.cypher). Usar la vista Graph para B01 y B02, y Table para B03 y Q04.

## Comprobar la persistencia

Reiniciar Neo4j sin volver a cargar los datos:

```powershell
docker compose restart neo4j
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 esperar
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 verificar
docker compose ps
```

La verificación debe seguir siendo correcta. En la prueba realizada se conservaron los nodos, las relaciones y sus propiedades después del reinicio.

## Detener y volver a iniciar

Los volúmenes `grupo13-hito5_neo4j_data` y `grupo13-hito5_neo4j_logs` conservan los datos y los logs. Para detener el servicio:

```powershell
docker compose stop neo4j
```

Para volver a iniciarlo:

```powershell
docker compose start neo4j
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 esperar
```

## Documentación

- [Modelo de grafo](docs/modelo_grafo.md).
- [Decisiones de diseño](docs/decisiones.md).
- [Catálogo de consultas](docs/catalogo_consultas.md).
- [Evidencias](docs/evidencia/README.md).
