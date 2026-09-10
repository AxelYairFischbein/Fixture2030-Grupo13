# Evidencias del Hito 5

La ejecución técnica final **`20260910T010744736Z`** terminó con estado `OK` el 10/09/2026 a las 01:09:28 UTC, con Neo4j 2026.07.1 Community. El [resumen completo](20260910T010744736Z/00_resumen.json) y [ultima_ejecucion.json](ultima_ejecucion.json) registran sus resultados.

## Archivos principales

Los archivos de esta tabla pertenecen a [20260910T010744736Z/](20260910T010744736Z/).

| Archivos | Qué demuestran |
|---|---|
| `01_compose_config.txt`, `05_version.txt`, `05_imagen.txt`, `05_montajes.txt` | Configuración, versión de Neo4j y volúmenes de datos y logs |
| `06_estructura.txt`, `06_restricciones.txt`, `06_indices.txt` | Seis restricciones de unicidad e índices disponibles |
| `08_primera_carga.txt` a `13_snapshot_segunda.txt` | Dos cargas con los mismos recuentos y contenido |
| `N01_rechazo.txt` a `N06_rechazo.txt` | Rechazo de los seis casos de identificadores o códigos duplicados |
| `14_crud.txt` a `16_snapshot_post_crud.txt` | CRUD completo, sin residuos ni cambios en el conjunto de prueba |
| `Q01.txt` a `Q13.txt`, `A01.txt`, `A02.txt` | Resultados de las consultas y los dos análisis |
| `17_plan_indice.txt` | Uso del índice temporal en el filtro por fecha |
| `18_reinicio.txt` a `21_snapshot_persistencia.txt` | Reinicio y conservación del contenido sin repetir la carga |
| `22_salud_final.txt`, `23_estado_final.txt` | Estado final saludable del contenedor y puertos publicados |
| `24_browser_consultas.txt` | Salida de B01–B03 mediante el cliente de consola |
| `00_resumen.json` | Estado de la ejecución, comandos y comprobaciones |

## Resultados

- **Idempotencia:** ambas cargas dejaron el mismo contenido, sin duplicados: 64 equipos, 1.536 jugadores, 64 partidos, 8 estadios y 128 eventos; en total, 1.800 nodos y 2.112 relaciones.
- **Persistencia:** después del reinicio se conservaron los nodos, relaciones y propiedades. Los 44 controles de integridad fueron correctos.
- **Consultas y análisis:** Q01–Q13 y A01–A02 coincidieron con los resultados esperados. Q04 devuelve EQ-002/PAR-001 y EQ-003/PAR-033. A01 encuentra un camino mínimo de cuatro relaciones entre EQ-001 y EQ-004; A02 devuelve `FALSE` para la conexión entre EQ-001 y EQ-005 mediante encuentros.

## Evidencia visual en Neo4j Browser

Las cuatro consultas se ejecutaron correctamente en Neo4j Browser.

| Captura | Qué demuestra |
|---|---|
| [01_browser_carga.png](01_browser_carga.png) | B03: recuentos por etiqueta de los 1.800 nodos cargados |
| [02_browser_subgrafo_general.png](02_browser_subgrafo_general.png) | B01: subgrafo de G01 con equipos, partidos, estadios, eventos y jugadores involucrados |
| [03_browser_recorrido_jugador_estadio.png](03_browser_recorrido_jugador_estadio.png) | B02: recorrido jugador → equipo → partido → estadio |
| [04_browser_consulta_rivales.png](04_browser_consulta_rivales.png) | Q04: rivales de EQ-001 y sus partidos correspondientes |

## Repetir la verificación

Desde `Hito 5/`, con el ambiente iniciado según el [README principal](../../README.md):

```powershell
docker compose config --quiet
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 verificar
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 consultas
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 analisis
```

Para comprobar las vistas, ejecutar por separado B01–B03 de [07_browser.cypher](../../queries/07_browser.cypher) y Q04 de [04_graph_queries.cypher](../../queries/04_graph_queries.cypher) en [Neo4j Browser](http://localhost:7474).
