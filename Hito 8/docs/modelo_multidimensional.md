# Modelo multidimensional

La base `fixture2030_h8` contiene la tabla `estadisticas_equipo`. Cada fila representa una observación de un equipo en un partido y un instante. Una tabla común permite comparar equipos y agregar por tiempo sin crear una tabla por entidad o consulta.

| Componente | Nombre y tipo | Significado y uso |
| --- | --- | --- |
| Tag | `partido_id`, texto | Identificador estable, filtro principal de las ventanas |
| Tag | `equipo_id`, texto | Equipo participante, comparación y separación de contadores |
| Tag | `estadio_id`, texto | Sede del partido. Depende de `partido_id` y no varía por muestra |
| Field | `posesion_pct`, Float64 | Indicador de posesión estimada que la fuente informa en ese instante, entre 0 y 100 |
| Field | `pases_acumulados`, Int64 | Contador de pases desde el inicio del partido. Comienza en cero y no disminuye en la muestra |
| Field | `tiros_intervalo`, Int64 | Cantidad de tiros ocurridos en el intervalo de muestreo que termina en el timestamp |
| Timestamp | `time` | Instante de observación UTC. Se escribe como Unix epoch con `precision=second` |

Una serie es la tabla más una combinación de sus tres tags. La identidad de un punto agrega el timestamp a esa combinación. Los tres fields pertenecen al mismo punto. Repetir esa identidad y esos valores conserva el mismo punto lógico, como se comprobó al repetir la carga. Escribir valores diferentes sobre la misma identidad sería una modificación y no un dato nuevo. Por eso los reintentos conservan el contenido exacto del lote.

No hay identificadores únicos por observación ni texto libre en tags. Los porcentajes y contadores son valores observados, no dimensiones. La variación de un field no crea una serie nueva. Los nombres, descripciones y atributos maestros de equipos y estadios se conservan fuera del modelo temporal.

## Tiempo y agregaciones

La precisión de escritura es de un segundo. La frecuencia predeterminada es una observación por segundo para cada serie. Con `--paso 5` la precisión seguiría siendo de segundos, pero habría una observación cada cinco segundos. El motor puede representar internamente `time` como `Timestamp(ns)`, sin que ello agregue precisión a la fuente.

Los puntos se generan en `[inicio, fin)`. Para un paso de un segundo, cada `tiros_intervalo` cubre `(t - 1 s, t]`. El primer punto es una línea de base con cero pases y cero tiros. Las consultas que calculan incrementos incluyen una muestra anterior al inicio de la ventana y usan `LAG` dentro de cada serie. Los intervalos se atribuyen al timestamp de su extremo final. Por eso una selección de timestamps `[a, b)` resume eventos en `(a - paso, b - paso]`, sin duplicar los límites entre intervalos adyacentes.

| Medida | Agregación aplicada | Condición y límite |
| --- | --- | --- |
| Posesión estimada | `AVG` de muestras, más su cantidad | Una media temporal aproximada requiere cadencia uniforme, cobertura completa y que la muestra represente el estado de ese intervalo. No equivale a reconstruir la posesión oficial a partir de eventos ni es una suma de porcentajes |
| Pases acumulados | `SUM` de diferencias consecutivas obtenidas con `LAG` | Requiere la muestra anterior a la ventana, intervalos completos y ausencia de reinicios. El máximo de un contador monotónico es el último acumulado, no el incremento de una ventana |
| Tiros por intervalo | `SUM` | Requiere intervalos consecutivos sin solapamientos ni muestras faltantes |

`DATE_BIN` agrupa timestamps por minuto UTC. La salida incluye la cobertura y las discontinuidades. Un contador que retrocede no se transforma automáticamente en un incremento válido. Es necesario revisar la fuente. No se implementan correcciones automáticas de estadísticas.

## Datos de muestra y relación con el Fixture

| Partido | Equipos | Estadio | Series |
| --- | --- | --- | ---: |
| PAR-001 | EQ-001 y EQ-002 | EST-01 | 2 |
| PAR-002 | EQ-003 y EQ-004 | EST-02 | 2 |

Estos identificadores y relaciones coinciden con los datos de partidos, equipos y estadios utilizados en los hitos anteriores. La opción de hasta 32 partidos mantiene la correspondencia de la primera jornada del conjunto existente. Las fechas de observación son una reproducción sintética reciente, separada del calendario del torneo. No se consultó ninguna base anterior para producir estas estadísticas.

Conceptualmente, el Hito 4 conserva información documental del Fixture, el Hito 5 sus relaciones, el Hito 6 sus patrones de consulta de gran volumen y el Hito 7 la caché, las sesiones y la actividad temporal. Este módulo conserva la evolución de medidas deportivas. Un tiro agregado no reemplaza a un evento deportivo con identidad propia. Los usuarios serían consumidores de las consultas, pero sus sesiones no forman parte de las series. No se duplican usuarios ni se ejecutan integraciones con otros motores.

El generador utiliza fórmulas deterministas. Los porcentajes de los dos equipos suman 100 en cada instante. Los pases aumentan cada 10 o 12 segundos según el equipo y los tiros se distribuyen en intervalos de varios minutos. Las variaciones son didácticas y no pretenden simular estadísticamente un torneo real.
