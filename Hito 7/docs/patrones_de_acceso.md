# Patrones de acceso

El problema es sostener muchas lecturas de información repetida y actualizaciones breves de actividad. Una visita no necesita recuperar todo el Fixture ni recorrer usuarios. El consumidor conoce un identificador de sesión, equipo o partido y puede derivar la clave directamente.

| Patrón y responsable | Entrada y respuesta | Lecturas y escrituras esperadas | Estructura y decisión |
| --- | --- | --- | --- |
| Sesión durante la navegación | ID de sesión, atributos de usuario y acceso válido o rechazo | Lectura y actualización ante actividad válida. Alta al iniciar y baja al cerrar | Hash para consultar atributos y actualizar última actividad. Estado temporal con 30 minutos de inactividad |
| Ficha de equipo solicitada por un lector | `equipoId`, ficha serializada o dato no disponible | Muchas lecturas repetidas. Escritura por miss e invalidación cuando cambia el origen | String JSON porque se devuelve la ficha completa. La copia dura hasta 5 minutos. La ficha autoritativa permanece fuera de Redis |
| Visita a un partido y consulta del ranking | `partidoId`, nuevo puntaje o Top 3 de la ventana | Una escritura por visita. Lectura acotada del ranking durante la navegación | Sorted Set porque mantiene puntajes por partido y permite recuperar los primeros sin ordenar en el cliente. Es actividad temporal, no información deportiva |

## Volumen y concurrencia

Como escenario de análisis, 10.000 sesiones con una actividad cada 30 segundos suponen unas 333 renovaciones por segundo. Se pueden sumar 500 lecturas de fichas y 200 visitas a partidos por segundo en un pico hipotético. Son supuestos para reconocer los patrones y el riesgo de concurrencia, no resultados medidos ni capacidades garantizadas.

La muestra tiene dos usuarios, hasta tres sesiones durante la prueba, una ficha y tres partidos. La prueba concurrente usa cuatro clientes con 100 visitas cada uno. Dos clientes que leyeran el mismo puntaje y luego escribieran su suma podrían perder una visita. `ZINCRBY` resuelve el incremento dentro de Redis y no usa esa secuencia.

El ranking mantiene una ventana de una hora desde su primera visita. Agrupa interés reciente durante la navegación y vence aunque sigan llegando visitas. La siguiente visita abre otra ventana en la misma clave. No representa los últimos 60 minutos móviles ni conserva un historial. Top 3 es suficiente para los tres partidos de la muestra. En un volumen mayor, el límite de respuesta seguiría siendo explícito.

## Relación con los otros hitos

La ficha mantiene `equipoId=EQ-001`, `codigo=F01`, `nombre=Seleccion Sintetica 01` y `confederacion=AFC`, coherentes con los datos sintéticos documentales y del grafo. Los partidos conservan `PAR-001` a `PAR-003`. Los usuarios usan `USR-00001` y `USR-00002`, compatibles con los comentarios.

El Hito 4 sigue siendo el módulo documental para las entidades de negocio. El Hito 5 conserva las relaciones y consultas del grafo. El Hito 6 conserva los comentarios masivos. Redis agrega estado temporal y acelera lecturas repetidas. Aquí la fuente documental se representa mediante un diccionario en Python para demostrar cache-aside sin conectar ni modificar esos módulos. No se miden tiempos de MongoDB, Neo4j ni Cassandra.
