# Decisiones técnicas del Grupo 13

## Problema y relación con los Hitos anteriores

El Fixture 2030 necesita responder qué jugadores pertenecen a un equipo, contra quién juega, dónde se programa cada encuentro y quién participa en una incidencia. Neo4j permite representar estas conexiones como relaciones y consultarlas mediante recorridos.

El problema planteado en los Hitos 1 y 2 combina equipos, jugadores, partidos y eventos. El Hito 2 identifica a Neo4j como una opción para los datos relacionados con partidos e incidencias. El Hito 3 separa las fichas documentales de sus conexiones deportivas, y el Hito 4 implementa las fichas de equipos y jugadores. Este módulo mantiene esa separación y utiliza los mismos identificadores de equipos y jugadores.

## MongoDB, Neo4j e información replicada

MongoDB organiza la información en documentos y resulta adecuado para las fichas de equipos y jugadores. Neo4j organiza nodos y relaciones, lo que permite recorrer planteles, encuentros, sedes e incidencias.

Los nodos de equipo y jugador conservan únicamente los atributos necesarios para identificarlos y recorrer sus relaciones. Del equipo se replican `equipoId`, `codigo`, `nombre` y `confederacion`; del jugador, `jugadorId`, `nombre`, `apellido` y `posicion`. La camiseta se guarda en la relación `PERTENECE_A`.

Las estadísticas acumuladas y las fichas extensas no forman parte de este módulo. Los partidos conservan identidad, grupo, jornada, fase, estado y fecha de inicio. Los eventos representan incidencias individuales.

La carga es independiente y utiliza datos sintéticos definidos en Cypher. No hay conexión ni sincronización con MongoDB.

## Modelo e identificadores

Se utilizan cinco etiquetas: `Equipo`, `Jugador`, `Partido`, `Estadio` y `EventoDeportivo`. Sus conexiones son:

- Jugador → `PERTENECE_A` → Equipo, con la camiseta.
- Equipo → `DISPUTA` → Partido, con el rol LOCAL o VISITANTE.
- Partido → `SE_JUEGA_EN` → Estadio.
- EventoDeportivo → `OCURRE_EN` → Partido.
- EventoDeportivo → `INVOLUCRA` → Jugador, con el rol SALE o ENTRA.

Los identificadores son legibles y estables: `EQ-001`, `JUG-0001`, `PAR-001`, `EST-01` y `EVT-PAR-001-LOCAL`. Se usan como claves de negocio en lugar de los identificadores internos de Neo4j. El [modelo de grafo](modelo_grafo.md) detalla propiedades, direcciones y cardinalidades.

## Datos sintéticos

La muestra contiene **64 equipos, 1.536 jugadores, 64 partidos, 8 estadios y 128 eventos**: 1.800 nodos y 2.112 relaciones.

Hay 16 grupos ficticios de cuatro equipos y dos jornadas. Para un grupo con equipos A, B, C y D, la primera jornada incluye A–B y C–D; la segunda, A–C y B–D. Cada equipo disputa dos encuentros.

Los partidos se distribuyen entre ocho estadios, del 10 al 17 de junio de 2030 a las 18:00 UTC. Cada estadio recibe ocho partidos y no hay superposiciones de equipo o sede. Cada encuentro tiene dos sustituciones: una por equipo, con la camiseta 20 como SALE y la 21 como ENTRA.

Los datos permiten probar los recorridos; no representan el fixture, los planteles ni las sedes oficiales.

## Carga idempotente e integridad

La carga utiliza `UNWIND` y `range` para construir la muestra. `MERGE` busca o crea cada nodo por su identificador y cada relación por su tipo y extremos. `SET` asigna las propiedades. La carga se ejecuta en una única transacción.

Repetirla sobre el ambiente preparado mantiene nodos, relaciones y propiedades, sin duplicados. La [ejecución final](evidencia/20260910T010744736Z/00_resumen.json) comprobó la igualdad del contenido entre cargas y después del reinicio.

El CRUD utiliza una incidencia temporal para demostrar creación, lectura, actualización y eliminación. La actualización registra el motivo `CORRECCION_DE_PLANILLA`. Al terminar, elimina esa incidencia y conserva el conjunto de prueba.

Se definen seis restricciones de unicidad: los cinco identificadores y el código de equipo. Se crean con `IF NOT EXISTS`. Las propiedades requeridas y las cardinalidades se comprueban mediante consultas de integridad.

El índice `idx_partido_inicio` acompaña el filtro por rango de fechas de Q09. El plan registrado muestra su uso. Las restricciones e índices ocupan espacio y deben mantenerse al escribir, a cambio de proteger identidades y facilitar búsquedas.

## Alternativas y trade-offs

| Decisión | Alternativa | Elección y consecuencia |
|---|---|---|
| Evento deportivo | Guardarlo como propiedad o lista del partido | Un nodo propio permite identificar cada incidencia y vincular sus participantes; agrega nodos y relaciones |
| Pertenencia al equipo | Repetir una lista de jugadores en cada equipo | `PERTENECE_A` evita esa duplicación y permite guardar la camiseta del plantel |
| Participación en partidos | Usar relaciones separadas para LOCAL y VISITANTE | `DISPUTA` con una propiedad de rol permite consultar ambos casos con el mismo patrón; los roles se verifican por partido |
| Estadio | Guardar su nombre en cada partido | Un nodo `Estadio` reúne la programación de una sede mediante un recorrido adicional |
| Rivales y agenda del jugador | Guardar relaciones directas para cada resultado | Se derivan a través de equipos y partidos; requieren varios saltos, pero evitan actualizar información repetida |
| Carga | Importar archivos CSV | Cypher define una muestra pequeña y reproducible sin archivos externos; modificar los datos requiere editar la carga |
| Análisis | Agregar una extensión de algoritmos | Las funciones nativas de camino mínimo resuelven la pregunta planteada sin dependencias adicionales |
| Persistencia | Guardar los datos solo en el contenedor | Los volúmenes nombrados conservan datos y logs entre reinicios |

## Análisis de relaciones

A01 busca una cadena mínima de encuentros entre EQ-001 y EQ-004. Recorre únicamente `DISPUTA`, en ambos sentidos, con un máximo de seis relaciones. Si hay varios caminos mínimos, el orden por identificadores permite elegir uno de forma estable.

El resultado tiene cuatro relaciones: EQ-001 → PAR-001 → EQ-002 → PAR-034 → EQ-004. A02 consulta EQ-001 y EQ-005 y devuelve que no están conectados mediante encuentros en esta muestra. Compartir estadio no se considera un enfrentamiento.

Estos resultados describen conexiones entre equipos y partidos. No miden rendimiento deportivo ni distancias geográficas. El [catálogo](catalogo_consultas.md) incluye las consultas y sus resultados.

## Ambiente y limitaciones

El ambiente utiliza `neo4j:latest`, con volúmenes nombrados para datos y logs, HTTP en el puerto 7474 y Bolt en el 7687, publicados localmente. La versión registrada en la ejecución final es Neo4j 2026.07.1 Community.

- Se utiliza un único servicio local; no se evalúa disponibilidad de un sistema en producción.
- La muestra cubre dos jornadas y sustituciones de ejemplo. No incluye historia de planteles, alineaciones ni otros tipos de incidencia.
- Las restricciones de unicidad protegen identificadores; las cardinalidades se revisan con Cypher.
- Repetir la carga restablece sus valores definidos, pero no elimina datos agregados por fuera de ella.
- Las credenciales de ejemplo corresponden al laboratorio. Cambiar `.env` no modifica la contraseña de una base ya inicializada.
- La etiqueta `latest` puede cambiar; una actualización requiere comprobar nuevamente la compatibilidad.
