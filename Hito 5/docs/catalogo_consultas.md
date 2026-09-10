# Catálogo de operaciones y consultas

Resultados de la ejecución `20260910T010744736Z`, con Neo4j 2026.07.1 Community. Todas las filas y columnas de Q01–Q13 y A01–A02 coincidieron con los resultados esperados de `scripts/verification/resultados_esperados.json`. Las salidas enlazadas conservan los resultados completos.

Los filtros se definen en `WITH` dentro de cada bloque o como valores explícitos en la consulta.

## Q01 — Plantel por equipo

**Objetivo:** Identificar los 24 integrantes de EQ-001 con su camiseta y posición.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q01`.
**Patrón:** Jugador → PERTENECE_A → Equipo.
**Parámetros y filtros:** equipoId=EQ-001; ORDER BY camiseta,jugador.
**Campos devueltos:** `jugador`, `nombre`, `apellido`, `posicion`, `camiseta`.
**Índice/restricción:** uq_equipo_id; uq_jugador_id como identidad.
**Resultado esperado:** 24 filas: JUG-0001..JUG-0024; camisetas 1..24; 3 arqueros, 8 defensores, 8 mediocampistas y 5 delanteros.
**Resultado real comprobado:** 24 filas; todas las columnas coincidieron con lo esperado. [Salida completa Q01](evidencia/20260910T010744736Z/Q01.txt).

**Interpretación:** La pertenencia actual permite recuperar el plantel sin duplicar un array en el equipo.
**Requisito:** RF8, RNF7.

## Q02 — Equipos por estadio

**Objetivo:** Obtener todos los equipos con encuentros en EST-01.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q02`.
**Patrón:** Equipo → DISPUTA → Partido → SE_JUEGA_EN → Estadio.
**Parámetros y filtros:** estadioId=EST-01; DISTINCT; ORDER BY equipo.
**Campos devueltos:** `equipo`, `nombre`.
**Índice/restricción:** uq_estadio_id.
**Resultado esperado:** 12 equipos: EQ-001/002/003, 017/018/019, 033/034/035 y 049/050/051.
**Resultado real comprobado:** 12 filas; todas las columnas coincidieron con lo esperado. [Salida completa Q02](evidencia/20260910T010744736Z/Q02.txt).

**Interpretación:** DISTINCT evita repetir una selección que visita el mismo estadio en dos jornadas.
**Requisito:** RF8, RNF7.

## Q03 — Planteles vinculados a partidos

**Objetivo:** Listar jugadores cuyos equipos disputan los partidos seleccionados.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q03`.
**Patrón:** Jugador → PERTENECE_A → Equipo → DISPUTA → Partido.
**Parámetros y filtros:** partidos=[PAR-001]; orden partido,equipo,jugador.
**Campos devueltos:** `partido`, `equipo`, `jugador`.
**Índice/restricción:** uq_partido_id.
**Resultado esperado:** 48 filas: EQ-001 con JUG-0001..0024; EQ-002 con JUG-0025..0048.
**Resultado real comprobado:** 48 filas; todas las columnas coincidieron con lo esperado. [Salida completa Q03](evidencia/20260910T010744736Z/Q03.txt).

**Interpretación:** Es pertenencia al plantel del participante, no una alineación ni prueba de ingreso al campo.
**Requisito:** RF8, RNF7.

## Q04 — Rivales por encuentros compartidos

**Objetivo:** Recuperar los rivales de EQ-001 sin guardar relaciones derivadas.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q04`.
**Patrón:** Equipo → DISPUTA → Partido ← DISPUTA ← Equipo.
**Parámetros y filtros:** equipoId=EQ-001; rival distinto del origen; orden partido,rival.
**Campos devueltos:** `rival`, `partido`.
**Índice/restricción:** uq_equipo_id.
**Resultado esperado:** 2 filas: EQ-002/PAR-001 y EQ-003/PAR-033.
**Resultado real comprobado:** 2 filas: EQ-002/PAR-001 y EQ-003/PAR-033. [Salida completa Q04](evidencia/20260910T010744736Z/Q04.txt). La consulta también se ejecutó correctamente en Neo4j Browser: [captura de rivales](evidencia/04_browser_consulta_rivales.png).

**Interpretación:** Dos relaciones consecutivas permiten derivar el rival de cada encuentro.
**Requisito:** RF8, RF11, RNF7.

## Q05 — Partido de una incidencia

**Objetivo:** Situar un evento identificado dentro del fixture.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q05`.
**Patrón:** EventoDeportivo → OCURRE_EN → Partido.
**Parámetros y filtros:** eventoId=EVT-PAR-001-LOCAL.
**Campos devueltos:** `evento`, `tipo`, `minuto`, `partido`.
**Índice/restricción:** uq_evento_id.
**Resultado esperado:** Una fila: sustitución del minuto 60 en PAR-001.
**Resultado real comprobado:** 1 fila; todas las columnas coincidieron con lo esperado. [Salida completa Q05](evidencia/20260910T010744736Z/Q05.txt).

**Interpretación:** Una incidencia tiene identidad propia y se contextualiza en un único partido.
**Requisito:** RF8, RNF7.

## Q06 — Agenda de un equipo

**Objetivo:** Recuperar partido, fecha, rol y estadio para EQ-001.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q06`.
**Patrón:** Equipo → DISPUTA → Partido → SE_JUEGA_EN → Estadio.
**Parámetros y filtros:** equipoId=EQ-001; orden inicio,partido.
**Campos devueltos:** `partido`, `inicio`, `rol`, `estadio`.
**Índice/restricción:** uq_equipo_id.
**Resultado esperado:** PAR-001 el 10/06/2030 y PAR-033 el 14/06/2030, ambos 18:00 UTC, LOCAL y EST-01.
**Resultado real comprobado:** 2 filas; todas las columnas coincidieron con lo esperado. [Salida completa Q06](evidencia/20260910T010744736Z/Q06.txt).

**Interpretación:** La programación se recupera desde el equipo sin repetir la sede en sus atributos.
**Requisito:** RF8, RNF7.

## Q07 — Incidencias y participantes válidos

**Objetivo:** Consultar los eventos del partido y el equipo de cada participante.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q07`.
**Patrón:** Partido ← OCURRE_EN ← EventoDeportivo → INVOLUCRA → Jugador → PERTENECE_A → Equipo → DISPUTA → Partido.
**Parámetros y filtros:** partidoId=PAR-001; orden minuto,evento,rol.
**Campos devueltos:** `evento`, `minuto`, `rol`, `jugador`, `equipo`.
**Índice/restricción:** uq_partido_id.
**Resultado esperado:** 4 filas: LOCAL minuto 60, ENTRA JUG-0021/SALE JUG-0020 (EQ-001); VISITANTE minuto 65, ENTRA JUG-0045/SALE JUG-0044 (EQ-002).
**Resultado real comprobado:** 4 filas; todas las columnas coincidieron con lo esperado. [Salida completa Q07](evidencia/20260910T010744736Z/Q07.txt).

**Interpretación:** El patrón cerrado solo recupera participantes de equipos que disputan ese partido.
**Requisito:** RF8, RNF7.

## Q08 — Programación desde un jugador

**Objetivo:** Localizar estadios y partidos del equipo de JUG-0001.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q08`.
**Patrón:** Jugador → PERTENECE_A → Equipo → DISPUTA → Partido → SE_JUEGA_EN → Estadio.
**Parámetros y filtros:** jugadorId=JUG-0001; orden partido.
**Campos devueltos:** `jugador`, `equipo`, `partido`, `estadio`.
**Índice/restricción:** uq_jugador_id.
**Resultado esperado:** 2 filas: JUG-0001/EQ-001/PAR-001/EST-01 y JUG-0001/EQ-001/PAR-033/EST-01.
**Resultado real comprobado:** 2 filas; todas las columnas coincidieron con lo esperado. [Salida completa Q08](evidencia/20260910T010744736Z/Q08.txt).

**Interpretación:** Tres relaciones consecutivas enlazan identidad deportiva y programación; no infieren minutos jugados.
**Requisito:** RF8, RNF7.

## Q09 — Agenda en un intervalo

**Objetivo:** Recuperar los encuentros del primer día con un rango temporal.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q09`.
**Patrón:** Partido → SE_JUEGA_EN → Estadio.
**Parámetros y filtros:** inicio >= 2030-06-10T00:00Z e inicio < 2030-06-11T00:00Z; orden inicio,partido.
**Campos devueltos:** `partido`, `inicio`, `estadio`.
**Índice/restricción:** idx_partido_inicio (ver P01).
**Resultado esperado:** 8 filas: PAR-001..008, EST-01..08, 10/06/2030 18:00 UTC.
**Resultado real comprobado:** 8 filas; todas las columnas coincidieron con lo esperado. [Salida completa Q09](evidencia/20260910T010744736Z/Q09.txt).

**Interpretación:** El intervalo semiabierto permite concatenar días sin duplicar el límite superior.
**Requisito:** RF8, RNF7.

## Q10 — Segunda página del plantel

**Objetivo:** Paginar jugadores con un orden estable.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q10`.
**Patrón:** Jugador → PERTENECE_A → Equipo.
**Parámetros y filtros:** equipoId=EQ-001; ORDER BY jugador; SKIP 5 LIMIT 5.
**Campos devueltos:** `jugador`.
**Índice/restricción:** uq_equipo_id.
**Resultado esperado:** 5 filas: JUG-0006..JUG-0010.
**Resultado real comprobado:** 5 filas; todas las columnas coincidieron con lo esperado. [Salida completa Q10](evidencia/20260910T010744736Z/Q10.txt).

**Interpretación:** El desempate por ID evita que una misma carga produzca páginas ambiguas.
**Requisito:** RF8, RNF7.

## Q11 — Partidos por estadio

**Objetivo:** Contar relaciones de programación en cada sede.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q11`.
**Patrón:** Partido → SE_JUEGA_EN → Estadio.
**Parámetros y filtros:** Agrupación por estadio; count(p); ORDER BY estadio.
**Campos devueltos:** `estadio`, `partidos`.
**Índice/restricción:** Ninguno adicional; recorrido de las relaciones SE_JUEGA_EN.
**Resultado esperado:** 8 filas, EST-01..08 con 8 partidos cada uno.
**Resultado real comprobado:** 8 filas; todas las columnas coincidieron con lo esperado. [Salida completa Q11](evidencia/20260910T010744736Z/Q11.txt).

**Interpretación:** Es un conteo de relaciones de programación, no una estadística de rendimiento deportivo.
**Requisito:** RF8, RNF7.

## Q12 — Equipos filtrados por confederación

**Objetivo:** Obtener una lista acotada de equipos de UEFA.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q12`.
**Patrón:** Nodos Equipo filtrados por propiedad propia.
**Parámetros y filtros:** confederacion=UEFA; ORDER BY equipo; LIMIT 5.
**Campos devueltos:** `equipo`, `codigo`, `confederacion`.
**Índice/restricción:** Sin índice adicional: 64 nodos y filtro de baja selectividad.
**Resultado esperado:** 5 filas: EQ-006/012/018/024/030, códigos F06/F12/F18/F24/F30.
**Resultado real comprobado:** 5 filas; todas las columnas coincidieron con lo esperado. [Salida completa Q12](evidencia/20260910T010744736Z/Q12.txt).

**Interpretación:** Demuestra filtro, orden y límite sin usar rankings estadísticos.
**Requisito:** RF8, RNF7.

## Q13 — Equipo inexistente

**Objetivo:** Comprobar el comportamiento de un filtro sin correspondencias.
**Archivo:** [queries/04_graph_queries.cypher](../queries/04_graph_queries.cypher), bloque `Q13`.
**Patrón:** Jugador → PERTENECE_A → Equipo.
**Parámetros y filtros:** equipoId=EQ-999; count(j).
**Campos devueltos:** `jugadores`.
**Índice/restricción:** uq_equipo_id.
**Resultado esperado:** Una fila con jugadores=0.
**Resultado real comprobado:** 1 fila; todas las columnas coincidieron con lo esperado. [Salida completa Q13](evidencia/20260910T010744736Z/Q13.txt).

**Interpretación:** La falta de una entidad se distingue de un error de ejecución.
**Requisito:** RF8, RNF7.

## A01 — Camino mínimo de encuentros

**Objetivo:** Encontrar una cadena mínima que vincule EQ-001 con EQ-004.
**Archivo:** [queries/05_analysis.cypher](../queries/05_analysis.cypher), bloque `A01`.
**Patrón:** Equipo — DISPUTA — Partido — DISPUTA — Equipo, repetido.
**Parámetros y filtros:** Origen EQ-001, destino EQ-004; 1..6 relaciones; allShortestPaths; desempate lexicográfico; LIMIT 1.
**Campos devueltos:** `saltos`, `entidades`.
**Índice/restricción:** uq_equipo_id.
**Resultado esperado:** 4 relaciones: EQ-001 → PAR-001 → EQ-002 → PAR-034 → EQ-004.
**Resultado real comprobado:** 1 fila; todas las columnas coincidieron con lo esperado. [Salida completa A01](evidencia/20260910T010744736Z/A01.txt).

**Interpretación:** EQ-001 y EQ-004 no se enfrentan directamente; quedan conectados mediante EQ-002 y dos partidos. Hay otra cadena de igual longitud por EQ-003; se elige una de forma estable.
**Requisito:** RF9, RNF7.

**Consulta ejecutada:**

```cypher
// Camino minimo de encuentros entre EQ-001 y EQ-004, hasta 6 relaciones.
// Solo DISPUTA: compartir estadio no equivale a competir entre si.
MATCH (a:Equipo {equipoId:'EQ-001'}),(b:Equipo {equipoId:'EQ-004'})
MATCH camino=allShortestPaths((a)-[:DISPUTA*1..6]-(b))
WITH camino,[n IN nodes(camino)|coalesce(n.equipoId,n.partidoId)] AS entidades
WITH camino,entidades ORDER BY entidades LIMIT 1
RETURN length(camino) AS saltos,
       reduce(texto='',id IN entidades|texto+CASE WHEN texto='' THEN '' ELSE ' -> ' END+id) AS entidades;
```

## A02 — Conectividad entre grupos

**Objetivo:** Contrastar el camino con un par perteneciente a otro grupo.
**Archivo:** [queries/05_analysis.cypher](../queries/05_analysis.cypher), bloque `A02`.
**Patrón:** Solo relaciones DISPUTA, ignorando dirección.
**Parámetros y filtros:** Origen EQ-001, destino EQ-005; shortestPath con 1..6 relaciones; OPTIONAL MATCH.
**Campos devueltos:** `origen`, `destino`, `conectado`.
**Índice/restricción:** uq_equipo_id.
**Resultado esperado:** Una fila con conectado=FALSE.
**Resultado real comprobado:** 1 fila; todas las columnas coincidieron con lo esperado. [Salida completa A02](evidencia/20260910T010744736Z/A02.txt).

**Interpretación:** No hay conexión bajo DISPUTA en la muestra: G01 y G02 están separados. Compartir un estadio no crea un enfrentamiento.
**Requisito:** RF9, RNF7.

**Consulta ejecutada:**

```cypher
// Control de conectividad entre grupos distintos, en la misma proyeccion y cota.
MATCH (a:Equipo {equipoId:'EQ-001'}),(b:Equipo {equipoId:'EQ-005'})
OPTIONAL MATCH camino=shortestPath((a)-[:DISPUTA*1..6]-(b))
RETURN a.equipoId AS origen,b.equipoId AS destino,camino IS NOT NULL AS conectado;
```

### Limitaciones del análisis

A01/A02 analizan conectividad topológica exclusivamente mediante DISPUTA, con un máximo de seis relaciones. No miden influencia, fortaleza, resultados ni distancias de viaje. La ausencia de camino no demuestra que dos selecciones nunca se enfrentarán en el torneo completo. En esta muestra los 16 grupos están desconectados por construcción; compartir estadio queda excluido del análisis.

## Operaciones de estructura, carga, CRUD y verificación

Las operaciones siguientes se ejecutaron mediante los archivos indicados. El patrón, filtros, campos, expectativa y resultado real quedan registrados por operación.

### S01 — Restricciones únicas

**Objetivo:** Evitar identidades ambiguas.
**Archivo:** [queries/01_constraints.cypher](../queries/01_constraints.cypher).
**Patrón:** Cada etiqueta por su ID; Equipo también por código.
**Parámetros, filtros e índice/restricción:** IF NOT EXISTS; seis nombres uq_*.
**Campos devueltos:** name,type,labelsOrTypes,properties.
**Esperado:** Seis restricciones de unicidad.
**Resultado real:** Seis restricciones presentes; N01–N06 rechazaron duplicados. [Evidencia](evidencia/20260910T010744736Z/06_restricciones.txt).
**Interpretación:** Las identidades protegidas no pueden duplicarse; la cardinalidad se controla por separado.
**Requisitos:** RF10, RNF4.

### S02 — Índice de agenda

**Objetivo:** Proveer un acceso por fecha.
**Archivo:** [queries/01_constraints.cypher](../queries/01_constraints.cypher).
**Patrón:** Partido(inicio).
**Parámetros, filtros e índice/restricción:** idx_partido_inicio; IF NOT EXISTS; awaitIndexes(120).
**Campos devueltos:** name,state,type.
**Esperado:** Índice ONLINE, más índices de respaldo y LOOKUP.
**Resultado real:** Nueve índices ONLINE: seis de unicidad, uno de rango y dos LOOKUP. [Evidencia](evidencia/20260910T010744736Z/06_indices.txt).
**Interpretación:** Hay un acceso temporal asociado a Q09, sin afirmar una mejora no medida.
**Requisitos:** RF10.

### L01 — Cargar equipos

**Objetivo:** Preservar identidad documental.
**Archivo:** [queries/02_load.cypher](../queries/02_load.cypher).
**Patrón:** (Equipo {equipoId}).
**Parámetros, filtros e índice/restricción:** range(1,64); confederaciones cíclicas; uq_equipo_id/uq_equipo_codigo.
**Campos devueltos:** codigo,equipos.
**Esperado:** 64 equipos.
**Resultado real:** L01=64; carga sobre el conjunto existente, sin crear nuevos nodos. [Evidencia](evidencia/20260910T010744736Z/08_primera_carga.txt).
**Interpretación:** Preservar identidad documental.
**Requisitos:** RF3, RF5, RF6, RNF4.

### L02 — Cargar jugadores y pertenencia

**Objetivo:** Representar 24 miembros por selección.
**Archivo:** [queries/02_load.cypher](../queries/02_load.cypher).
**Patrón:** Jugador → PERTENECE_A → Equipo.
**Parámetros, filtros e índice/restricción:** range(1,24) por equipo; uq_jugador_id/uq_equipo_id.
**Campos devueltos:** codigo,jugadores.
**Esperado:** 1.536 jugadores y pertenencias.
**Resultado real:** L02=1536; planteles de 24 comprobados. [Evidencia](evidencia/20260910T010744736Z/08_primera_carga.txt).
**Interpretación:** Representar 24 miembros por selección.
**Requisitos:** RF4, RF5, RF6, RNF4.

### L03 — Cargar estadios

**Objetivo:** Identificar sedes de programación.
**Archivo:** [queries/02_load.cypher](../queries/02_load.cypher).
**Patrón:** (Estadio {estadioId}).
**Parámetros, filtros e índice/restricción:** range(1,8); uq_estadio_id.
**Campos devueltos:** codigo,estadios.
**Esperado:** 8 estadios.
**Resultado real:** L03=8. [Evidencia](evidencia/20260910T010744736Z/08_primera_carga.txt).
**Interpretación:** Identificar sedes de programación.
**Requisitos:** RF3, RF6.

### L04 — Cargar partidos y participantes

**Objetivo:** Materializar la programación de muestra.
**Archivo:** [queries/02_load.cypher](../queries/02_load.cypher).
**Patrón:** Equipo → DISPUTA → Partido → SE_JUEGA_EN → Estadio.
**Parámetros, filtros e índice/restricción:** 64 encuentros, 16 grupos, dos jornadas; uq_partido_id.
**Campos devueltos:** codigo,partidos.
**Esperado:** 64 partidos, 128 DISPUTA y 64 SE_JUEGA_EN.
**Resultado real:** L04=64; sin roles ni sedes inválidos. [Evidencia](evidencia/20260910T010744736Z/08_primera_carga.txt).
**Interpretación:** Materializar la programación de muestra.
**Requisitos:** RF3, RF4, RF6.

### L05 — Cargar incidencias

**Objetivo:** Vincular sustituciones y sus participantes.
**Archivo:** [queries/02_load.cypher](../queries/02_load.cypher).
**Patrón:** EventoDeportivo → OCURRE_EN → Partido; EventoDeportivo → INVOLUCRA → Jugador.
**Parámetros, filtros e índice/restricción:** Una por rol del equipo; camisetas 20/21; uq_evento_id.
**Campos devueltos:** codigo,eventos.
**Esperado:** 128 eventos, 128 OCURRE_EN, 256 INVOLUCRA.
**Resultado real:** L05=128; participantes válidos del mismo equipo. [Evidencia](evidencia/20260910T010744736Z/08_primera_carga.txt).
**Interpretación:** Vincular sustituciones y sus participantes.
**Requisitos:** RF3, RF4, RF6.

### C01 — Precondición CRUD

**Objetivo:** Comprobar el ID reservado.
**Archivo:** [queries/03_crud.cypher](../queries/03_crud.cypher).
**Patrón:** EventoDeportivo por eventoId.
**Parámetros, filtros e índice/restricción:** CRUD-G13-EVT-001; uq_evento_id.
**Campos devueltos:** codigo,actual,esperado.
**Esperado:** 0 nodos preexistentes.
**Resultado real:** C01_preexistentes=0. [Evidencia](evidencia/20260910T010744736Z/14_crud.txt).
**Interpretación:** Comprobar el ID reservado.
**Requisitos:** RF7.

### C02 — Crear incidencia

**Objetivo:** Demostrar alta de nodo y tres relaciones.
**Archivo:** [queries/03_crud.cypher](../queries/03_crud.cypher).
**Patrón:** Evento → Partido; Evento → dos Jugadores.
**Parámetros, filtros e índice/restricción:** ID CRUD-G13-EVT-001; PAR-001; JUG-0020/0021; origen exclusivo.
**Campos devueltos:** codigo,actual,esperado.
**Esperado:** 1 evento temporal.
**Resultado real:** C02_creado=1. [Evidencia](evidencia/20260910T010744736Z/14_crud.txt).
**Interpretación:** Demostrar alta de nodo y tres relaciones.
**Requisitos:** RF7.

### C03 — Leer incidencia

**Objetivo:** Consultar los participantes recién creados.
**Archivo:** [queries/03_crud.cypher](../queries/03_crud.cypher).
**Patrón:** Evento → INVOLUCRA → Jugador.
**Parámetros, filtros e índice/restricción:** ID reservado y origen crud-controlado-grupo13.
**Campos devueltos:** codigo,evento,minuto,rol,jugador.
**Esperado:** 2 filas, minuto 70, SALE 0020/ENTRA 0021.
**Resultado real:** Dos filas exactas en la evidencia. [Evidencia](evidencia/20260910T010744736Z/14_crud.txt).
**Interpretación:** Consultar los participantes recién creados.
**Requisitos:** RF7.

### C04 — Actualizar propiedades

**Objetivo:** Corregir minuto y anotar motivo en la relación.
**Archivo:** [queries/03_crud.cypher](../queries/03_crud.cypher).
**Patrón:** Evento → INVOLUCRA {rol:ENTRA} → JUG-0021.
**Parámetros, filtros e índice/restricción:** ID y origen; SET minuto=72 y motivo=CORRECCION_DE_PLANILLA.
**Campos devueltos:** codigo,actual,esperado,motivo.
**Esperado:** Minuto 72 y motivo de corrección.
**Resultado real:** C04_actualizado=72; motivo guardado. [Evidencia](evidencia/20260910T010744736Z/14_crud.txt).
**Interpretación:** Corregir minuto y anotar motivo en la relación.
**Requisitos:** RF7.

### C05 — Reasignar participante

**Objetivo:** Demostrar modificación estructural de una relación.
**Archivo:** [queries/03_crud.cypher](../queries/03_crud.cypher).
**Patrón:** Evento → INVOLUCRA → Jugador.
**Parámetros, filtros e índice/restricción:** DELETE relación ENTRA a JUG-0021; CREATE a JUG-0022; uq_jugador_id.
**Campos devueltos:** codigo,actual,esperado.
**Esperado:** Nuevo extremo JUG-0022.
**Resultado real:** C05_reasignado=JUG-0022; extremo anterior eliminado. [Evidencia](evidencia/20260910T010744736Z/14_crud.txt).
**Interpretación:** Demostrar modificación estructural de una relación.
**Requisitos:** RF7.

### C06 — Previsualizar baja

**Objetivo:** Identificar exactamente lo que se eliminará.
**Archivo:** [queries/03_crud.cypher](../queries/03_crud.cypher).
**Patrón:** Evento reservado → destinos.
**Parámetros, filtros e índice/restricción:** ID y origen; ORDER BY relación,destino.
**Campos devueltos:** codigo,evento,relacion,destino.
**Esperado:** 3 relaciones: un partido y dos jugadores.
**Resultado real:** OCURRE_EN/PAR-001; INVOLUCRA/JUG-0020 y JUG-0022. [Evidencia](evidencia/20260910T010744736Z/14_crud.txt).
**Interpretación:** Identificar exactamente lo que se eliminará.
**Requisitos:** RF7.

### C07 — Eliminar incidencia temporal

**Objetivo:** Restituir el conjunto canónico.
**Archivo:** [queries/03_crud.cypher](../queries/03_crud.cypher).
**Patrón:** Evento por ID y origen exclusivos.
**Parámetros, filtros e índice/restricción:** DETACH DELETE solo CRUD-G13-EVT-001.
**Campos devueltos:** codigo,actual,esperado.
**Esperado:** 1 nodo eliminado y 0 residuos.
**Resultado real:** C07_eliminado=1; C07_residuos=0; snapshot posterior idéntico. [Evidencia](evidencia/20260910T010744736Z/14_crud.txt).
**Interpretación:** Restituir el conjunto canónico.
**Requisitos:** RF7, RNF4.

### V01 — Integridad del grafo

**Objetivo:** Controlar recuentos, duplicados y cardinalidades.
**Archivo:** [queries/06_verify.cypher](../queries/06_verify.cypher).
**Patrón:** Etiquetas y cinco tipos de relación.
**Parámetros, filtros e índice/restricción:** Expectativas 64/1536/64/8/128; relaciones y ceros de anomalías.
**Campos devueltos:** control,actual,esperado,ok.
**Esperado:** Todos los controles TRUE.
**Resultado real:** 44 controles TRUE después de carga, recarga, CRUD y reinicio. [Evidencia](evidencia/20260910T010744736Z/20_integridad_persistencia.txt).
**Interpretación:** Controlar recuentos, duplicados y cardinalidades.
**Requisitos:** RF4, RF5, RF6, RF10, RNF7.

### V02 — Snapshot integral

**Objetivo:** Comparar contenido, no solo recuentos.
**Archivo:** [queries/09_snapshot.cypher](../queries/09_snapshot.cypher).
**Patrón:** Todos los nodos y extremos de relaciones, solo lectura.
**Parámetros, filtros e índice/restricción:** Propiedades ordenadas por clave; filas por tipo/identidad.
**Campos devueltos:** tipo,identidad,propiedades.
**Esperado:** Snapshots idénticos entre cargas, tras CRUD y reinicio.
**Resultado real:** Contenido idéntico entre cargas, tras el CRUD y después del reinicio. [Evidencia](evidencia/20260910T010744736Z/21_snapshot_persistencia.txt).
**Interpretación:** La comparación incluye valores de propiedades y extremos, evitando confundir igualdad de cantidades con igualdad de contenido.
**Requisitos:** RNF2, RNF4.

### P01 — Plan real del rango

**Objetivo:** Inspeccionar el acceso usado para la agenda Q09.
**Archivo:** [queries/08_index_plan.cypher](../queries/08_index_plan.cypher).
**Patrón:** Partido → SE_JUEGA_EN → Estadio.
**Parámetros, filtros e índice/restricción:** PROFILE; inicio entre 10/06 y 11/06 de 2030; idx_partido_inicio.
**Campos devueltos:** partido,inicio,estadio y plan.
**Esperado:** Ocho encuentros; observar el plan efectivo.
**Resultado real:** 8 filas; NodeIndexSeekByRange usa idx_partido_inicio; 83 DB hits en esta ejecución. [Evidencia](evidencia/20260910T010744736Z/17_plan_indice.txt).
**Interpretación:** Se confirma el índice utilizado, no una ganancia de tiempo frente a otra implementación.
**Requisitos:** RF10, RNF7.

### B01 — Subgrafo general en Browser

**Objetivo:** Visualizar los cinco tipos de entidad en el subgrafo de G01.
**Archivo:** [queries/07_browser.cypher](../queries/07_browser.cypher).
**Patrón:** Grupo G01 con equipos, estadios, eventos y participantes.
**Parámetros, filtros e índice/restricción:** grupo=G01; UNION ALL de tres patrones; IDs únicos de las etiquetas.
**Campos devueltos:** camino.
**Esperado:** 26 nodos y 36 relaciones distintas en los caminos.
**Resultado real:** Consulta ejecutada correctamente en Neo4j Browser. [Captura del subgrafo de G01](evidencia/02_browser_subgrafo_general.png) y [salida de los caminos](evidencia/20260910T010744736Z/24_browser_consultas.txt).
**Interpretación:** Visualizar los cinco tipos de entidad en el subgrafo de G01.
**Requisitos:** RF11.

### B02 — Vista de tres saltos

**Objetivo:** Mostrar la agenda desde un jugador.
**Archivo:** [queries/07_browser.cypher](../queries/07_browser.cypher).
**Patrón:** Jugador → Equipo → Partido → Estadio.
**Parámetros, filtros e índice/restricción:** jugadorId=JUG-0001; uq_jugador_id.
**Campos devueltos:** camino.
**Esperado:** Dos caminos de tres saltos; unión de 5 nodos y 5 relaciones.
**Resultado real:** Consulta ejecutada correctamente en Neo4j Browser: dos caminos de tres saltos. [Captura del recorrido jugador–estadio](evidencia/03_browser_recorrido_jugador_estadio.png) y [salida de los caminos](evidencia/20260910T010744736Z/24_browser_consultas.txt).
**Interpretación:** Mostrar la agenda desde un jugador.
**Requisitos:** RF8, RF11.

### B03 — Recuentos para Browser

**Objetivo:** Mostrar evidencia visual de la carga.
**Archivo:** [queries/07_browser.cypher](../queries/07_browser.cypher).
**Patrón:** Nodos agrupados por etiqueta.
**Parámetros, filtros e índice/restricción:** ORDER BY etiqueta; sin índice adicional.
**Campos devueltos:** etiqueta,cantidad.
**Esperado:** 64/8/128/1536/64 por orden de etiqueta.
**Resultado real:** Consulta ejecutada correctamente en Neo4j Browser: 64 equipos, 8 estadios, 128 eventos, 1.536 jugadores y 64 partidos. [Captura de recuentos](evidencia/01_browser_carga.png).
**Interpretación:** Mostrar evidencia visual de la carga.
**Requisitos:** RF11.

### N01–N06 — rechazo efectivo de duplicados

**Objetivo:** probar cada constraint instalado. **Archivo:** `scripts/verification/generar_evidencias.ps1`, bloque `$cases`. **Patrón:** CREATE de un nodo de la etiqueta con una clave ya existente, dentro de `:begin` y sin confirmar. **Campos devueltos:** error del servidor y código de salida del cliente. **Resultado esperado:** rechazo, salida no cero y ningún cambio permanente. **Resultado real:** seis rechazos y snapshot posterior igual. **Interpretación:** cada identidad está protegida por Neo4j, no solamente por el generador. **Requisitos:** RF10, RNF7.

| Código | Etiqueta / propiedad y filtro | Restricción | Evidencia real |
|---|---|---|---|
| N01 | Equipo.equipoId=EQ-001 | uq_equipo_id | [Rechazo N01](evidencia/20260910T010744736Z/N01_rechazo.txt) |
| N02 | Equipo.codigo=F01 | uq_equipo_codigo | [Rechazo N02](evidencia/20260910T010744736Z/N02_rechazo.txt) |
| N03 | Jugador.jugadorId=JUG-0001 | uq_jugador_id | [Rechazo N03](evidencia/20260910T010744736Z/N03_rechazo.txt) |
| N04 | Partido.partidoId=PAR-001 | uq_partido_id | [Rechazo N04](evidencia/20260910T010744736Z/N04_rechazo.txt) |
| N05 | Estadio.estadioId=EST-01 | uq_estadio_id | [Rechazo N05](evidencia/20260910T010744736Z/N05_rechazo.txt) |
| N06 | EventoDeportivo.eventoId=EVT-PAR-001-LOCAL | uq_evento_id | [Rechazo N06](evidencia/20260910T010744736Z/N06_rechazo.txt) |

La ejecución final realizó ambas cargas sobre el conjunto existente. `SET` puede informar propiedades asignadas aunque sus valores sean iguales; la comparación del contenido confirmó la idempotencia.
