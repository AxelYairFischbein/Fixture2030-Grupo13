# Modelo clave/valor y datos de muestra

La convención es `fixture2030:h7:demo:<dominio>:<identificador o alcance>`. `fixture2030` identifica el proyecto, `h7` el módulo y `demo` delimita las claves sintéticas que pueden limpiarse. Los dos puntos son una convención de nombres, no directorios ni particiones.

| Clave después del prefijo | Tipo y contenido | Operaciones | Vida útil |
| --- | --- | --- | --- |
| `sesion:SES-DEMO-01` | Hash del usuario `USR-00001` | Creación, `HGETALL`, actualización de actividad y `DEL` | 1800 segundos desde la última actividad válida |
| `sesion:SES-DEMO-02` | Hash del usuario `USR-00002` | Creación, recuperación y cierre | 1800 segundos, con cierre explícito en la prueba |
| `sesion:SES-CORTA` | Hash del usuario `USR-00001` | Creación y prueba de vencimiento | 3 segundos, exclusivamente para la prueba |
| `cache:equipo:EQ-001` | String JSON con `equipoId`, `codigo`, `nombre`, `confederacion` | `GET`, `SET EX 300`, `DEL` | Hasta 300 segundos, sin renovación por lectura |
| `ranking:visitas:ventana` | Sorted Set con `PAR-001`, `PAR-002`, `PAR-003` y visitas como score | `ZINCRBY`, `ZRANGE 0 2 REV WITHSCORES` | 3600 segundos desde la primera visita, sin renovación |

Una sesión tiene `sesion_id`, `usuario_id`, `ultima_actividad`, `estado` y `rol`. La última actividad se expresa en segundos Unix UTC obtenidos con `TIME` del servidor. El estado de la muestra es `activa` y el rol es `lector`. El ID de sesión identifica un acceso específico, por lo que un usuario puede tener más de una sesión. Los IDs legibles de prueba no son credenciales ni tokens de autenticación.

Se elige Hash para acceder a campos y actualizar uno sin reescribir un JSON completo. La ficha se consulta completa y por eso se guarda como String serializado. El Sorted Set se justifica por el incremento de puntajes y el orden del Top 3. No se agregan otras estructuras sin una operación que las necesite.

## Origen, cantidad y estado final

`carga_muestra.redis` elimina solamente las cinco claves enumeradas y crea las dos sesiones normales. `sesiones.redis` crea además la sesión corta. Hay dos usuarios sintéticos y como máximo tres sesiones. No se carga una base de perfiles ni se simulan millones de personas.

`demo.py cache` inicializa una sola ficha fuera de Redis. Luego de demostrar el hit, cambia su nombre a `Seleccion Sintetica 01 - ficha actualizada` y comprueba la recarga. El cambio es sintético y no se aplica a los archivos de los otros hitos.

La prueba de ranking agrega dos visitas a `PAR-002` y una a `PAR-003` como preparación. Durante el intervalo medido agrega exactamente 400 visitas a `PAR-001`. Quedan tres miembros y 403 visitas totales. Volver a ejecutar la prueba elimina únicamente esa clave de ranking antes de empezar.

Tras los tres flujos quedan tres claves con vencimiento: la sesión `SES-DEMO-01`, la ficha y el ranking. La sesión cerrada y la vencida están ausentes. A medida que transcurre el tiempo esas claves desaparecen normalmente. La repetición completa restablece el mismo escenario con timestamps actuales.
