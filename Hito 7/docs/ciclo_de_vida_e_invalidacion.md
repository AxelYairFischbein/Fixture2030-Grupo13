# Ciclo de vida e invalidación

## Sesiones

La creación simula un acceso ya validado fuera del módulo. Se guardan los atributos y se fija el TTL en una llamada `EVAL`. Para considerar válido un acceso, la clave debe existir, tener `estado=activa` y `TTL > 0`. La lectura de atributos por sí sola no autoriza una operación.

La duración normal es 1800 segundos. Treinta minutos permiten navegar el Fixture sin pedir un nuevo acceso por pausas breves y limitan cuánto permanece una sesión abandonada. Una consulta válida que representa actividad del usuario actualiza `ultima_actividad` y renueva el TTL. Una inspección administrativa, un `HGETALL` o un intento rechazado no lo renuevan.

La comprobación, actualización y renovación ocurren en un único `EVAL`. Así, un cierre concurrente no puede intercalarse entre comprobar existencia y ejecutar `HSET`. Si el cierre sucede primero, la renovación devuelve 0. Si sucede después, elimina la sesión renovada. No se recrea una sesión ausente ni se usa `PERSIST`.

Se usa expiración nativa. Redis determina el vencimiento sin un proceso que recorra sesiones. `SES-CORTA` dura 3 segundos y el auxiliar espera 4 para observar `HGETALL {}` y `TTL -2`. Es una prueba de inactividad, no la duración normal. `DEL` representa cierre o invalidación explícita. Repetir el cierre devuelve 0 y mantiene la sesión ausente.

Ante ausencia, vencimiento o pérdida de la sesión se rechaza el acceso y se requiere iniciar una nueva sesión. Si Redis no responde, no se puede validar el acceso y se informa indisponibilidad. La ficha pública puede recuperarse de su origen, pero ese dato no reconstruye una sesión autenticada. Si la renovación falla, no se confirma actividad ni se informa un TTL nuevo.

`HSET` no renueva por sí solo el vencimiento. `EXPIRE` debe ser deliberado y `TTL -1` indicaría una clave sin vencimiento, que este módulo no acepta como sesión válida.

## Caché y fuente de verdad

El diccionario `origen` en `demo.py` es una fuente simulada externa a Redis. Representa la ficha que correspondería al módulo documental. Se conserva en el proceso durante el flujo, permite modificar el origen y vuelve a su valor inicial en la próxima ejecución. No es almacenamiento durable ni existe integración física con MongoDB.

El flujo cache-aside implementado es:

1. Eliminar la copia de prueba y comprobar que no existe.
2. Ejecutar `GET`. Ante miss, obtener una copia del diccionario de origen.
3. Guardar el JSON con `SET ... EX 300` y devolverlo.
4. Repetir la lectura. Ante hit, devolver el JSON de Redis sin consultar el origen.
5. Cambiar el nombre en la fuente simulada.
6. Ejecutar `DEL` después de confirmar el cambio de origen.
7. Consultar otra vez. El miss recupera la ficha nueva y vuelve a guardarla con TTL.

Cinco minutos reducen lecturas repetidas de una ficha que cambia poco. La lectura no extiende ese plazo. La invalidación después de un cambio evita esperar el TTL para reflejarlo en el flujo secuencial probado. El TTL limita la vida de cada copia, pero no detecta modificaciones de negocio.

Si Redis no contiene la clave, la lectura falla o agota su tiempo de espera, se consulta el origen. Si guardar la copia falla o agota su tiempo de espera, se devuelve igualmente el dato obtenido del origen sin confirmar que quedó cacheado. Si tampoco se puede obtener el origen, se informa dato no disponible y no se fabrica una ficha. Un hit vigente puede responder sin consultar el origen.

Si falla la invalidación, el cambio de origen no se deshace. El auxiliar termina con error y no continúa leyendo una copia potencialmente vieja. Antes de reanudar lecturas cacheadas se debe lograr la invalidación. En una aplicación real, durante ese intervalo se consultaría directamente el origen. No hay atomicidad entre dos sistemas independientes. La demostración usa un solo escritor de origen y lecturas secuenciales. No garantiza coherencia estricta ante un lector que repueble una copia vieja al mismo tiempo que otro proceso modifica el origen. Resolver esa carrera requeriría coordinación adicional fuera de este alcance.

## Ranking y atomicidad

Cada visita ejecuta `ZINCRBY` y `EXPIRE 3600 NX` dentro de un `EVAL` corto. El incremento es nativo. `NX` asigna el vencimiento solo si aún no existe y evita extender la ventana indefinidamente. La ejecución atómica impide que una desconexión del cliente deje el incremento sin TTL entre esos dos comandos. Al vencer se descarta la actividad de esa ventana y la próxima visita comienza desde uno.

Los argumentos y tipos son conocidos en esta muestra. Si una clave tiene un tipo incompatible, la operación falla y el auxiliar no informa éxito. Los scripts Lua se ejecutan sin intercalación, pero no ofrecen rollback general de escrituras anteriores a un error. Tampoco `MULTI/EXEC` ofrecería ese rollback. No se hacen reintentos automáticos de incrementos ante una respuesta perdida, porque podrían duplicar una visita.
