# Evidencias del Hito 5

La ejecución final `20260910T010744736Z` terminó correctamente el 10/09/2026 con Neo4j 2026.07.1 Community. Las salidas técnicas se conservan en la [carpeta de esa ejecución](20260910T010744736Z/).

## Carga e idempotencia

La carga dejó **64 equipos, 1.536 jugadores, 64 partidos, 8 estadios y 128 eventos**, con un total de **1.800 nodos y 2.112 relaciones**. Cada equipo tiene 24 jugadores.

La segunda carga conservó los mismos datos sin generar nodos ni relaciones duplicados.

## CRUD

Se creó y consultó la incidencia temporal `CRUD-G13-EVT-001` en `PAR-001`. Luego se cambió el minuto de 70 a 72, se actualizó una propiedad de la relación `INVOLUCRA` y se reemplazó a `JUG-0021` por `JUG-0022` como participante que entra. Al finalizar se eliminaron la incidencia temporal y sus tres relaciones, manteniendo los datos de prueba.

## Consultas, análisis y persistencia

Q01 a Q13 y A01 a A02 se ejecutaron correctamente. Q04 devolvió los rivales EQ-002 y EQ-003, asociados a PAR-001 y PAR-033. A01 encontró un camino mínimo de cuatro relaciones entre EQ-001 y EQ-004. A02 devolvió `FALSE` para la conexión entre EQ-001 y EQ-005 mediante encuentros.

Después del reinicio se conservaron los nodos, las relaciones y sus propiedades sin repetir la carga. La verificación de integridad siguió siendo correcta.

## Capturas de Neo4j Browser

| Captura | Qué muestra |
|---|---|
| [Recuentos por etiqueta](01_browser_carga.png) | B03: los 1.800 nodos de la carga |
| [Subgrafo general de G01](02_browser_subgrafo_general.png) | B01: equipos, partidos, estadios, eventos y jugadores involucrados |
| [Recorrido jugador → equipo → partido → estadio](03_browser_recorrido_jugador_estadio.png) | B02: la programación del equipo de JUG-0001 |
| [Rivales de EQ-001](04_browser_consulta_rivales.png) | Q04: EQ-002/PAR-001 y EQ-003/PAR-033 |

## Repetir la verificación

Desde `Hito 5/`, con `.env` preparado según el [README principal](../../README.md):

```powershell
docker compose config --quiet
docker compose up -d
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 esperar
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 verificar
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 consultas
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 analisis
docker compose restart neo4j
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 esperar
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 verificar
docker compose ps
```

Para repetir las capturas, ejecutar por separado B01 a B03 de [07_browser.cypher](../../queries/07_browser.cypher) y Q04 de [04_graph_queries.cypher](../../queries/04_graph_queries.cypher) en [Neo4j Browser](http://localhost:7474).
