# Catálogo de consultas

Este catálogo resume las consultas, el CRUD y el análisis del grafo.
Los resultados corresponden a la ejecución `20260910T010744736Z`,
realizada con Neo4j 2026.07.1 Community.
Las salidas enlazadas permiten consultar los resultados completos.

## Consultas Q01 a Q13

Las consultas están en [04_graph_queries.cypher](../queries/04_graph_queries.cypher).
Cada bloque tiene su identificador y sus filtros, por lo que puede ejecutarse por separado.

| Consulta | Objetivo | Recorrido o filtro | Resultado | Evidencia |
|---|---|---|---|---|
| Q01 | Listar el plantel de EQ-001 | Jugador → PERTENECE_A → Equipo, orden por camiseta y jugador | 24 jugadores, de JUG-0001 a JUG-0024, con camisetas 1 a 24 | [Q01](evidencia/20260910T010744736Z/Q01.txt) |
| Q02 | Buscar equipos con partidos en EST-01 | Equipo → DISPUTA → Partido → SE_JUEGA_EN → Estadio, sin repetir equipos | 12 equipos: EQ-001, EQ-002, EQ-003, EQ-017, EQ-018, EQ-019, EQ-033, EQ-034, EQ-035, EQ-049, EQ-050 y EQ-051 | [Q02](evidencia/20260910T010744736Z/Q02.txt) |
| Q03 | Consultar los planteles vinculados a PAR-001 | Jugador → PERTENECE_A → Equipo → DISPUTA → Partido | 48 jugadores: JUG-0001 a JUG-0024 de EQ-001 y JUG-0025 a JUG-0048 de EQ-002 | [Q03](evidencia/20260910T010744736Z/Q03.txt) |
| Q04 | Obtener los rivales de EQ-001 | Equipo → DISPUTA → Partido ← DISPUTA ← rival, excluyendo al equipo de origen | 2 filas: EQ-002/PAR-001 y EQ-003/PAR-033 | [Q04](evidencia/20260910T010744736Z/Q04.txt) |
| Q05 | Ubicar una incidencia en su partido | EventoDeportivo → OCURRE_EN → Partido, evento EVT-PAR-001-LOCAL | 1 fila: sustitución del minuto 60 en PAR-001 | [Q05](evidencia/20260910T010744736Z/Q05.txt) |
| Q06 | Consultar la agenda de EQ-001 | Equipo → DISPUTA → Partido → SE_JUEGA_EN → Estadio, orden por fecha | PAR-001 el 10/06/2030 y PAR-033 el 14/06/2030, ambos a las 18:00 UTC, con rol LOCAL en EST-01 | [Q06](evidencia/20260910T010744736Z/Q06.txt) |
| Q07 | Consultar las incidencias y los participantes de PAR-001 | Partido ← OCURRE_EN ← EventoDeportivo → INVOLUCRA → Jugador → PERTENECE_A → Equipo → DISPUTA → Partido | 4 filas: en EQ-001 sale JUG-0020 y entra JUG-0021 al minuto 60. En EQ-002 sale JUG-0044 y entra JUG-0045 al minuto 65 | [Q07](evidencia/20260910T010744736Z/Q07.txt) |
| Q08 | Ver la programación desde JUG-0001 | Jugador → PERTENECE_A → Equipo → DISPUTA → Partido → SE_JUEGA_EN → Estadio | 2 filas: JUG-0001/EQ-001/PAR-001/EST-01 y JUG-0001/EQ-001/PAR-033/EST-01 | [Q08](evidencia/20260910T010744736Z/Q08.txt) |
| Q09 | Buscar los partidos del primer día | Partido → SE_JUEGA_EN → Estadio, desde el 10/06/2030 a las 00:00 UTC hasta antes del 11/06/2030 a las 00:00 UTC | 8 partidos, PAR-001 a PAR-008, en EST-01 a EST-08, el 10/06/2030 a las 18:00 UTC | [Q09](evidencia/20260910T010744736Z/Q09.txt) |
| Q10 | Obtener la segunda página del plantel de EQ-001 | Jugador → PERTENECE_A → Equipo, orden por jugador, `SKIP 5 LIMIT 5` | 5 jugadores: JUG-0006 a JUG-0010 | [Q10](evidencia/20260910T010744736Z/Q10.txt) |
| Q11 | Contar partidos por estadio | Partido → SE_JUEGA_EN → Estadio, agrupación por estadio | 8 filas: EST-01 a EST-08, con 8 partidos cada uno | [Q11](evidencia/20260910T010744736Z/Q11.txt) |
| Q12 | Listar cinco equipos de UEFA | Equipo con `confederacion=UEFA`, orden por identificador y límite de 5 | EQ-006, EQ-012, EQ-018, EQ-024 y EQ-030, con códigos F06, F12, F18, F24 y F30 | [Q12](evidencia/20260910T010744736Z/Q12.txt) |
| Q13 | Consultar el plantel de un equipo inexistente | Jugador → PERTENECE_A → Equipo, con `equipoId=EQ-999` | 1 fila con `jugadores=0` | [Q13](evidencia/20260910T010744736Z/Q13.txt) |

Q04 recorre dos relaciones consecutivas para encontrar rivales.
Q08 usa tres relaciones para llegar desde un jugador hasta los estadios de su equipo.
Q03 y Q08 se basan en la pertenencia al plantel, por lo que no prueban que el jugador
haya ingresado a la cancha.

Los ejemplos también muestran filtros, orden, paginación y conteos.
En Q02, `DISTINCT` evita repetir equipos que visitan la misma sede.
Q10 ordena los jugadores antes de elegir una página y Q13 devuelve cero
cuando el identificador del equipo no existe.

## Resumen del CRUD

El archivo [03_crud.cypher](../queries/03_crud.cypher) realiza las cuatro operaciones
sobre la incidencia temporal `CRUD-G13-EVT-001`.
La [salida del CRUD](evidencia/20260910T010744736Z/14_crud.txt) registra estos resultados.

### Creación

Se crea una sustitución en el minuto 70 de PAR-001.
El evento se conecta con el partido y con dos jugadores de EQ-001:
JUG-0020 con rol SALE y JUG-0021 con rol ENTRA.

### Lectura

Se consulta la incidencia con sus participantes.
El resultado contiene dos filas, una por jugador, ambas con el minuto 70.

### Actualización

Se cambia el minuto de 70 a 72 y se agrega el motivo `CORRECCION_DE_PLANILLA`
a la relación del jugador que entra.
Luego se reemplaza esa relación para que apunte a JUG-0022 en lugar de JUG-0021.

### Eliminación

Se elimina la incidencia temporal junto con sus tres relaciones.
La consulta final devuelve cero eventos con ese identificador.
Los nodos del partido y de los jugadores, así como los datos de prueba, se conservan.

## Análisis A01 y A02

Ambos análisis están en [05_analysis.cypher](../queries/05_analysis.cypher).
Recorren únicamente `DISPUTA`, en ambos sentidos, con un máximo de seis relaciones.

### A01 · Camino mínimo entre equipos

**Objetivo:** encontrar la cadena más corta de encuentros entre EQ-001 y EQ-004.

**Resultado:** un camino de cuatro relaciones:
EQ-001 → PAR-001 → EQ-002 → PAR-034 → EQ-004.
La [salida de A01](evidencia/20260910T010744736Z/A01.txt) devuelve `saltos=4`.

**Interpretación:** EQ-001 y EQ-004 no se enfrentan directamente en la muestra,
pero se conectan a través de EQ-002 y dos partidos.
Existe otro camino mínimo por EQ-003. El orden de los identificadores permite
elegir uno de manera estable.

### A02 · Equipos sin conexión por encuentros

**Objetivo:** comprobar si EQ-001 y EQ-005 están conectados a través de partidos.

**Resultado:** la [salida de A02](evidencia/20260910T010744736Z/A02.txt)
devuelve `conectado=FALSE`.

**Interpretación:** los equipos pertenecen a grupos distintos.
Los 16 grupos de esta muestra no tienen encuentros entre sí.
Compartir estadio no forma parte del recorrido, y el resultado no describe
lo que podría ocurrir en un torneo completo.

## Restricciones e índice temporal

[01_constraints.cypher](../queries/01_constraints.cypher) crea seis restricciones
de unicidad: `uq_equipo_id`, `uq_equipo_codigo`, `uq_jugador_id`,
`uq_partido_id`, `uq_estadio_id` y `uq_evento_id`.
Protegen los cinco identificadores y el código de equipo.
Las propiedades requeridas y la cardinalidad de las relaciones se revisan
con [06_verify.cypher](../queries/06_verify.cypher).

El índice `idx_partido_inicio` permite buscar partidos por fecha.
Q09 lo utiliza para consultar los ocho encuentros del primer día.
Las [restricciones](evidencia/20260910T010744736Z/06_restricciones.txt)
y los [índices](evidencia/20260910T010744736Z/06_indices.txt) quedaron disponibles.

## Consultas mostradas en Neo4j Browser

Las capturas muestran los recuentos de carga, el subgrafo de G01,
un recorrido de tres relaciones y la consulta de rivales.

| Consulta | Vista y resultado | Captura |
|---|---|---|
| B03 | Table: 64 equipos, 8 estadios, 128 eventos, 1.536 jugadores y 64 partidos | [Recuentos de carga](evidencia/01_browser_carga.png) |
| B01 | Graph: subgrafo de G01 con 26 nodos y 36 relaciones distintas | [Subgrafo general](evidencia/02_browser_subgrafo_general.png) |
| B02 | Graph: dos caminos desde JUG-0001, con 5 nodos y 5 relaciones distintas en total | [Jugador → equipo → partido → estadio](evidencia/03_browser_recorrido_jugador_estadio.png) |
| Q04 | Table: EQ-002/PAR-001 y EQ-003/PAR-033 como rivales y partidos de EQ-001 | [Consulta de rivales](evidencia/04_browser_consulta_rivales.png) |

Para repetir las vistas, abrir [Neo4j Browser](http://localhost:7474)
y ejecutar por separado B01, B02 y B03 de
[07_browser.cypher](../queries/07_browser.cypher), y Q04 de
[04_graph_queries.cypher](../queries/04_graph_queries.cypher).
