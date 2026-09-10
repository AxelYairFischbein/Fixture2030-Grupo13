# Matriz de trazabilidad

**RF1–RF11 cumplidos. RNF1–RNF8 cumplidos dentro del alcance local documentado.**

La evidencia técnica corresponde a la ejecución `20260910T010744736Z`, con Neo4j 2026.07.1 Community. Las cuatro capturas de Neo4j Browser completan la evidencia visual.

Los comandos abreviados como `ejecutar.ps1 ACCION` se ejecutan desde `Hito 5/` de esta forma:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ejecutar.ps1 ACCION
```

La preparación del ambiente y la secuencia de ejecución están en el [README](../README.md).

## Requisitos funcionales

| Requisito | Implementación y verificación | Evidencia | Estado |
|---|---|---|---|
| **RF1.** Ambiente local de Neo4j con Docker Compose y acceso desde Browser | `docker-compose.yml`; `docker compose config --quiet`, inicio y `ejecutar.ps1 esperar` | [Configuración](evidencia/20260910T010744736Z/01_compose_config.txt), [disponibilidad](evidencia/20260910T010744736Z/03_disponibilidad.txt), [Browser](evidencia/01_browser_carga.png) | Cumplido |
| **RF2.** Modelo de entidades y relaciones deportivas y de programación | [Modelo](modelo_grafo.md), [decisiones](decisiones.md) y `ejecutar.ps1 verificar` | [44 controles de integridad](evidencia/20260910T010744736Z/20_integridad_persistencia.txt) | Cumplido |
| **RF3.** Equipos, jugadores, partidos, eventos y estadios con etiquetas y propiedades justificadas | `02_load.cypher` y [modelo](modelo_grafo.md): 64 equipos, 1.536 jugadores, 64 partidos, 128 eventos y 8 estadios | [Carga](evidencia/20260910T010744736Z/08_primera_carga.txt), [recuentos en Browser](evidencia/01_browser_carga.png) | Cumplido |
| **RF4.** Pertenencia al equipo, participación en partidos, sede e incidencias | Cinco tipos de relación en `02_load.cypher`; roles, extremos y cardinalidades comprobados por `06_verify.cypher` | [Integridad](evidencia/20260910T010744736Z/20_integridad_persistencia.txt) | Cumplido |
| **RF5.** Identificadores de equipos y jugadores consistentes con el Hito 4 | `equipoId`, `jugadorId` y pertenencia conservados; controles de identidad en `06_verify.cypher` | [Integridad](evidencia/20260910T010744736Z/20_integridad_persistencia.txt), [decisiones](decisiones.md) | Cumplido |
| **RF6.** Carga reproducible con 64 equipos, más de 1.000 jugadores y una muestra de partidos, sedes y eventos | `02_load.cypher`: 1.536 jugadores, 24 por equipo, 64 partidos, 8 estadios y 128 eventos | [Carga](evidencia/20260910T010744736Z/08_primera_carga.txt), [integridad](evidencia/20260910T010744736Z/09_integridad_primera.txt) | Cumplido |
| **RF7.** Creación, lectura, actualización y eliminación de nodos o relaciones | C01–C07 en `03_crud.cypher`; `ejecutar.ps1 crud` y `ejecutar.ps1 verificar` | [CRUD](evidencia/20260910T010744736Z/14_crud.txt), [integridad posterior](evidencia/20260910T010744736Z/15_integridad_post_crud.txt) | Cumplido |
| **RF8.** Consultas de grafo, al menos dos con dos o más relaciones consecutivas | Q01–Q13 en `04_graph_queries.cypher`; Q04 recorre dos relaciones y Q08 recorre tres | [Catálogo con las 13 salidas](catalogo_consultas.md), [Q04](evidencia/20260910T010744736Z/Q04.txt), [Q08](evidencia/20260910T010744736Z/Q08.txt) | Cumplido |
| **RF9.** Consulta de camino o análisis de relaciones con interpretación | A01–A02 en `05_analysis.cypher`; `ejecutar.ps1 analisis`: camino mínimo y contraste de conectividad | [A01](evidencia/20260910T010744736Z/A01.txt), [A02](evidencia/20260910T010744736Z/A02.txt), [interpretación](catalogo_consultas.md) | Cumplido |
| **RF10.** Restricciones de integridad e índices | `01_constraints.cypher`: seis restricciones de unicidad e índice temporal; seis rechazos de duplicados y plan de Q09 | [Restricciones](evidencia/20260910T010744736Z/06_restricciones.txt), [índices](evidencia/20260910T010744736Z/06_indices.txt), [pruebas N01–N06](catalogo_consultas.md), [plan](evidencia/20260910T010744736Z/17_plan_indice.txt) | Cumplido |
| **RF11.** Evidencia de carga, consultas y visualización del subgrafo en Neo4j Browser | B01–B03 de `07_browser.cypher` y Q04 de `04_graph_queries.cypher`, ejecutadas correctamente en Neo4j Browser | [Carga](evidencia/01_browser_carga.png), [subgrafo general](evidencia/02_browser_subgrafo_general.png), [recorrido jugador–estadio](evidencia/03_browser_recorrido_jugador_estadio.png), [rivales](evidencia/04_browser_consulta_rivales.png) | Cumplido |

## Requisitos no funcionales

| Requisito | Implementación y verificación | Evidencia | Estado |
|---|---|---|---|
| **RNF1.** El ambiente utiliza la imagen `neo4j:latest` | Imagen declarada en `docker-compose.yml`; versión registrada: 2026.07.1 Community | [Configuración](evidencia/20260910T010744736Z/01_compose_config.txt), [versión](evidencia/20260910T010744736Z/05_version.txt), [imagen](evidencia/20260910T010744736Z/05_imagen.txt) | Cumplido |
| **RNF2.** Conservación de datos y logs en volúmenes nombrados | Volúmenes `neo4j_data` y `neo4j_logs`; contenido conservado tras reiniciar sin recarga | [Montajes](evidencia/20260910T010744736Z/05_montajes.txt), [reinicio](evidencia/20260910T010744736Z/18_reinicio.txt), [contenido posterior](evidencia/20260910T010744736Z/21_snapshot_persistencia.txt) | Cumplido |
| **RNF3.** Inicio y repetición de la carga siguiendo el README por otro integrante | [README](../README.md) con requisitos, configuración y comandos; secuencia técnica comprobada localmente | [Resumen de ejecución](evidencia/20260910T010744736Z/00_resumen.json) | Cumplido dentro del alcance local |
| **RNF4.** Recarga sin duplicados | `MERGE` por identidad y relaciones; segunda carga con los mismos recuentos y contenido | [Segunda carga](evidencia/20260910T010744736Z/11_segunda_carga.txt), [integridad](evidencia/20260910T010744736Z/12_integridad_segunda.txt), [comparación](evidencia/20260910T010744736Z/00_resumen.json) | Cumplido |
| **RNF5.** Cypher organizado, comentado y separado por propósito | Nueve archivos en `queries/`, con bloques identificados y [catálogo](catalogo_consultas.md) | [Consultas](../queries/04_graph_queries.cypher), [análisis](../queries/05_analysis.cypher) y sus salidas en el catálogo | Cumplido |
| **RNF6.** Compatibilidad conceptual con los Hitos anteriores | Identificadores compartidos y separación entre fichas documentales, conexiones deportivas y estadísticas | [Decisiones](decisiones.md), [modelo](modelo_grafo.md), [integridad](evidencia/20260910T010744736Z/20_integridad_persistencia.txt) | Cumplido |
| **RNF7.** Resultados interpretables y verificables | Q01–Q13 y A01–A02 comparadas en todas sus filas y columnas con `resultados_esperados.json`; explicación en el catálogo | [Resumen](evidencia/20260910T010744736Z/00_resumen.json), [catálogo y salidas](catalogo_consultas.md) | Cumplido |
| **RNF8.** Credenciales de desarrollo mediante variables de entorno | `.env.example`, `NEO4J_AUTH` y `.env` ignorado por Git; contraseña de laboratorio | [Configuración con autenticación redactada](evidencia/20260910T010744736Z/01_compose_config.txt), [.gitignore](../.gitignore) | Cumplido |

## Alcance de las comprobaciones

La persistencia se comprobó en el contenedor local y sus volúmenes. RNF3 se respalda en la secuencia de comandos ejecutada y documentada; no incluye una prueba de uso con otro integrante. Los datos son sintéticos y el análisis se limita a los encuentros cargados.
