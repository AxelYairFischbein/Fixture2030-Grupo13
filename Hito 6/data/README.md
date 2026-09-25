# Datos sintéticos

La muestra está escrita directamente en `scripts/carga_muestra.cql`. Contiene 12 comentarios lógicos, 24 filas entre las dos tablas, tres partidos (`PAR-001`, `PAR-002`, `PAR-009`), tres autores y dos días UTC. Incluye ocho visibles, dos pendientes y dos ocultos. Hay dos mensajes con el mismo instante para comprobar el desempate por identificador. Los extremos exactos de Q2 permiten comprobar que el inicio se incluye y el final se excluye.

El generador crea `data/generados/comentarios.csv` con una fila por comentario. Ese mismo archivo se importa en las dos tablas, por lo que cada comentario queda guardado dos veces. Los timestamps se expresan como milisegundos desde la época Unix.

Para el índice `n`, comenzando en cero, la distribución es:

- Partido `n módulo 64 + 1`, compatible con el calendario sintético del Hito 5.
- Día `10 de junio de 2030 + piso((partido - 1) / 8)`.
- Instante a partir de las 18:00 UTC, desplazado `(piso(n / 64) × 997) módulo 7.200.000` milisegundos. Cubre distintas posiciones de las dos horas de cada partido.
- Usuario `n módulo 10.000 + 1`.
- ID `MASIVO-` seguido por `n + 1` con 12 dígitos. No colisiona con la muestra ni el CRUD.
- Segmento `CRC32(ID en UTF-8) módulo 4` y minuto UTC truncado.
- Estado según `n módulo 20`, con 16 visibles, tres pendientes y uno oculto. Likes entre 0 y 10.

Con 1.000.100 comentarios, se generan 800.080 visibles, 150.015 pendientes y 50.005 ocultos. Cada partido recibe 15.626 o 15.627 comentarios. Cada autor recibe 100 o 101, distribuidos entre días y partidos. La distribución es uniforme y reproducible, no una simulación de popularidad ni una prueba del pico extraordinario.

El script informa cantidades de particiones y su máximo de filas calculados a partir del CSV. Son estadísticas del conjunto generado, no una medición del tamaño de SSTables. No mantiene el millón de mensajes completo en memoria.

La carpeta `generados/` contiene el CSV y `distribucion.json`. Al ejecutar una carga se agregan `medicion.json`, dos registros de COPY y posibles archivos `.err`. Cada ejecución reemplaza sus archivos de salida. Para comparar mediciones, guardar una copia antes de repetirlas. Generar archivos no borra datos de Cassandra.
