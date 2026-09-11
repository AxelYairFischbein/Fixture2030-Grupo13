# Decisiones de diseño del Grupo 13

## 1. Problema relacional

El Fixture 2030 necesita relacionar planteles, encuentros, sedes e incidencias. Preguntas como quiénes son los rivales de un equipo o en qué estadio juega el equipo de un jugador requieren seguir varias conexiones. Elegimos Neo4j para representar esas conexiones como relaciones y consultarlas con Cypher.

## 2. Relación con los hitos anteriores

Los Hitos 1 y 2 plantean el problema de equipos, jugadores, partidos y eventos. El Hito 2 propone Neo4j para las relaciones entre partidos e incidencias. El Hito 3 separa las fichas documentales de sus conexiones deportivas, y el Hito 4 implementa las fichas de equipos y jugadores en MongoDB.

Este hito conserva los identificadores `equipoId` y `jugadorId` y los atributos básicos de esos datos de prueba. MongoDB organiza las fichas y Neo4j permite recorrer sus conexiones deportivas. La carga del grafo es independiente, sin conexión ni sincronización con MongoDB.

## 3. Modelo elegido

Usamos cinco etiquetas: `Equipo`, `Jugador`, `Partido`, `Estadio` y `EventoDeportivo`. Las conectamos mediante `PERTENECE_A`, `DISPUTA`, `SE_JUEGA_EN`, `OCURRE_EN` e `INVOLUCRA`.

La camiseta queda en `PERTENECE_A` porque corresponde al jugador dentro de su plantel. Los roles LOCAL y VISITANTE quedan en `DISPUTA`, y SALE y ENTRA en `INVOLUCRA`. Cada evento tiene un nodo propio para vincularlo con su partido y sus participantes.

Usamos identificadores estables como `EQ-001`, `JUG-0001`, `PAR-001`, `EST-01` y `EVT-PAR-001-LOCAL`. El [modelo de grafo](modelo_grafo.md) detalla las propiedades, direcciones y cardinalidades.

## 4. Datos de prueba

La muestra contiene **64 equipos, 1.536 jugadores, 64 partidos, 8 estadios y 128 eventos**, con un total de **1.800 nodos y 2.112 relaciones**. Cada equipo tiene 24 jugadores.

Organizamos 16 grupos ficticios de cuatro equipos y dos jornadas. Para un grupo con equipos A, B, C y D, la primera jornada incluye A–B y C–D. La segunda incluye A–C y B–D. Cada equipo disputa dos encuentros.

Los partidos se distribuyen del 10 al 17 de junio de 2030 a las 18:00 UTC. Cada estadio recibe ocho partidos, sin superposiciones de equipo o sede. Cada encuentro tiene dos sustituciones, una por equipo. Sale el jugador con camiseta 20 y entra el de camiseta 21.

Estos datos permiten probar las consultas y los recorridos. No representan el fixture, los planteles ni las sedes oficiales.

## 5. Carga repetible e integridad

La carga usa `MERGE` para buscar o crear nodos por identificador y relaciones por tipo y extremos. Con `SET` asigna sus propiedades. La idempotencia permite repetir la carga sin generar duplicados, como se comprobó en las [evidencias](evidencia/README.md).

Definimos seis restricciones de unicidad para los cinco identificadores y el código de equipo. Las propiedades requeridas y la cardinalidad de las relaciones se comprueban con consultas Cypher. El índice `idx_partido_inicio` se utiliza en el filtro por rango de fechas de Q09.

El CRUD trabaja con la incidencia temporal `CRUD-G13-EVT-001` para mostrar creación, lectura, actualización y eliminación. Al finalizar, elimina esa incidencia y mantiene los datos de prueba.

## 6. Alternativas consideradas

| Decisión | Alternativa | Motivo de la elección |
|---|---|---|
| Evento como nodo | Guardarlo en una lista del partido | Permite identificar cada incidencia y conectar sus participantes, aunque agrega nodos y relaciones |
| Pertenencia mediante `PERTENECE_A` | Guardar una lista de jugadores en el equipo | Evita repetir el plantel y permite asociar la camiseta a la pertenencia |
| `DISPUTA` con propiedad `rol` | Usar relaciones distintas para LOCAL y VISITANTE | Permite consultar ambos roles con el mismo patrón |
| Estadio como nodo | Guardar su nombre en cada partido | Reúne los encuentros de una sede mediante una relación |
| Rivales y agenda mediante recorridos | Guardar relaciones directas adicionales | Evita mantener datos repetidos, a cambio de recorrer varias relaciones |
| Datos definidos en Cypher | Importar archivos CSV | Permite cargar la muestra sin archivos externos, aunque cambiarla requiere editar la carga |
| Camino mínimo nativo de Neo4j | Agregar una extensión de algoritmos | Resuelve el análisis planteado sin dependencias adicionales |
| Volúmenes para datos y logs | Guardarlos solo en el contenedor | Conserva la información entre reinicios |

## 7. Análisis de relaciones

A01 busca un camino mínimo entre EQ-001 y EQ-004 mediante `DISPUTA`, en ambos sentidos y con un máximo de seis relaciones. El resultado tiene cuatro relaciones: EQ-001 → PAR-001 → EQ-002 → PAR-034 → EQ-004. Si hay más de un camino mínimo, el orden de los identificadores permite elegir uno de forma estable.

A02 consulta la conexión entre EQ-001 y EQ-005 y devuelve `FALSE`. Pertenecen a grupos distintos que no tienen encuentros entre sí en esta muestra. Compartir estadio no se considera un enfrentamiento.

El análisis describe conexiones entre equipos y partidos. No mide rendimiento deportivo ni distancias geográficas. Los resultados están en el [catálogo de consultas](catalogo_consultas.md).

## 8. Alcance y limitaciones

- El módulo usa un servicio local de Neo4j. La prueba registrada se realizó con Neo4j 2026.07.1 Community y la imagen `neo4j:latest`.
- La muestra cubre dos jornadas y sustituciones de ejemplo. No incluye historia de planteles, alineaciones, marcadores ni estadísticas acumuladas.
- Pertenecer al plantel no demuestra que un jugador haya participado en un partido.
- Repetir la carga restablece sus valores definidos, pero no elimina datos agregados por fuera de ella.
- Los datos se conservan en volúmenes de Docker. La imagen `latest` puede cambiar, por lo que una actualización requiere volver a comprobar el funcionamiento.
