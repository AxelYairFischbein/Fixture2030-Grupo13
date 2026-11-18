# Hito 6 - Comentarios masivos del Fixture 2030

Grupo 13. Este módulo guarda y consulta comentarios del Fixture 2030 con Cassandra. Usa una tabla para buscar por partido y otra para consultar el historial de un usuario. Los datos son sintéticos y se organizan por minuto y segmento para repartir las escrituras.

## Requisitos y preparación

Se necesita Windows con PowerShell y Docker Desktop en modo de contenedores Linux. Para generar datos y medir la carga también se necesita Python 3.10 o superior, sin bibliotecas adicionales. El esquema, la muestra, el CRUD y las consultas se ejecutan con `cqlsh`, incluido en el contenedor.

El puerto local 9042 debe estar libre. El heap de Cassandra se limita a 2 GB. Docker necesita memoria adicional para el proceso, cachés y sistema operativo. La imagen se declara `cassandra:latest`, por lo que otra fecha de descarga puede producir otra versión.

Desde la raíz del repositorio:

```powershell
Set-Location -LiteralPath '.\Hito 6'
docker version
docker compose version
```

Si el motor no responde, iniciar Docker Desktop y esperar a que termine su arranque. El entorno es local, sin autenticación, y el puerto CQL solo está disponible en `127.0.0.1`.

## Validar la persistencia e iniciar

El almacenamiento de `/var/lib/cassandra` usa el volumen nombrado `grupo13-hito6_cassandra_data`. El montaje de `/scripts` sigue siendo de solo lectura y `/data` conserva las salidas locales de COPY.

Antes de aplicar este Compose sobre una instalación anterior con carpeta de Windows, completar la migración descrita más abajo. Iniciar un volumen vacío no migra datos existentes.

```powershell
docker compose config --quiet
docker compose up -d --pull never
docker inspect grupo13-hito6-cassandra-1 --format '{{json .Mounts}}'
docker compose exec -T cassandra nodetool status
docker compose exec -T cassandra cqlsh --no-color -e 'SHOW VERSION'
```

El montaje de datos debe indicar `Type: volume` y el nombre anterior. Esperar hasta observar `UN` y respuesta CQL. La imagen efectiva de la migración es Cassandra 5.0.9 y se conservó sin descargar otra versión. La etiqueta `latest` no garantiza por sí sola esa identidad.

## Migración reversible desde el montaje de Windows

La migración del 17 de noviembre preservó el origen `$env:USERPROFILE\docker\data\cassandra` y el respaldo `$env:USERPROFILE\docker\backups\fixture-auditoria-20261117\cassandra.tar`. El archivo `docker-compose.rollback.yml` de esa carpeta conserva la configuración anterior. No se eliminó ninguna carpeta ni volumen.

1. Registrar la imagen efectiva, los montajes y una huella lógica de las cuatro tablas usadas por los Hitos 6, 10 y 12.
2. Ejecutar `nodetool flush`, `nodetool drain` y detener únicamente Cassandra.
3. Montar el origen como solo lectura en un contenedor auxiliar de la misma imagen. Crear un TAR preservando permisos y un manifiesto SHA256 de sus archivos.
4. Crear el volumen nombrado, restaurar el TAR y comparar todos los archivos con el manifiesto antes de iniciar el motor.
5. Iniciar con `docker compose up -d --pull never`, comprobar imagen, montaje, estado del nodo y huellas de las tablas. Reiniciar y repetir la comprobación de persistencia y las requests de la API.

La [evidencia de la migración](../Hito%2013/evidencia/auditoria-20261117/migraciones.json) registra los SHA256 y los recuentos. El respaldo contiene datos locales y queda fuera de Git. El procedimiento sigue el mecanismo de [respaldo y restauración de volúmenes de Docker](https://docs.docker.com/engine/storage/volumes/).

Para volver al montaje anterior, detener primero el servicio y respaldar también el volumen actual. Verificar que no existan escrituras posteriores que deban conservarse en el retorno. Desde esta carpeta, usar la copia del Compose anterior con el directorio de proyecto correcto:

```powershell
$respaldoH6 = Join-Path $env:USERPROFILE 'docker\backups\fixture-auditoria-20261117'
docker compose stop cassandra
docker compose --project-directory (Get-Location).Path -f (Join-Path $respaldoH6 'docker-compose.rollback.yml') up -d --pull never
docker exec grupo13-hito6-cassandra-1 nodetool status
```

Comparar nuevamente la imagen y la integridad antes de habilitar escrituras. Conservar ambos almacenamientos hasta decidir el cierre de la migración.

## Crear esquema y cargar la muestra

```powershell
docker compose exec -T cassandra cqlsh -f /scripts/esquema.cql
docker compose exec -T cassandra cqlsh -f /scripts/carga_muestra.cql
docker compose exec -T cassandra cqlsh -e 'DESCRIBE KEYSPACE fixture2030_comentarios'
docker compose exec -T cassandra cqlsh -f /scripts/consultas.cql
```

La muestra tiene 12 comentarios y 24 filas entre las dos tablas. Antes de una carga masiva, verificar cantidades, repetir la inicialización y la muestra, y volver a comprobarlas:

```powershell
$conteoHito6 = 'SELECT COUNT(*) FROM fixture2030_comentarios.comentarios_por_partido; SELECT COUNT(*) FROM fixture2030_comentarios.comentarios_por_usuario;'
docker compose exec -T cassandra cqlsh -e $conteoHito6
docker compose exec -T cassandra cqlsh -f /scripts/esquema.cql
docker compose exec -T cassandra cqlsh -f /scripts/carga_muestra.cql
docker compose exec -T cassandra cqlsh -e $conteoHito6
```

Se esperan 12 filas por tabla en ambas lecturas si solo se cargó la muestra. `COUNT(*)` sin clave produce una advertencia de escaneo global. Se usa aquí únicamente para comprobar estas 12 filas, no como consulta habitual ni sobre el millón.

## CRUD y tres consultas

```powershell
docker compose exec -T cassandra cqlsh -f /scripts/crud.cql
docker compose exec -T cassandra cqlsh -f /scripts/consultas.cql
```

El CRUD inserta `PRUEBA-CRUD-001`, consulta sus dos copias, modifica contenido, estado y likes, y elimina ese comentario. Las últimas dos lecturas deben devolver cero filas. Cada batch agrupa solo las dos escrituras del mismo comentario.

Con la muestra sola, Q1 devuelve cinco comentarios recientes del minuto indicado. Q2 devuelve ocho en la ventana `[18:00:30, 18:02:10)`, incluyendo su extremo inicial y excluyendo el final. Q3 devuelve seis comentarios del autor en ese día. Las cargas masivas agregan resultados a esas mismas ventanas. El límite y el orden siguen vigentes.

Las consultas contienen parámetros de ejemplo editables. Para otra ventana de Q2, reemplazar `desde`, `hasta` y la lista de minutos UTC que intersectan el intervalo. Mantener como máximo cinco minutos de duración, hasta seis buckets y 24 particiones. Q1 y Q2 combinan las particiones mediante `IN`, `ORDER BY` y un límite global con paginación desactivada.

## Generar más de un millón y medir una carga

Generar 1.000.100 comentarios lógicos sin escribir en Cassandra:

```powershell
python -X utf8 .\scripts\carga_o_prueba.py --cantidad 1000100
Get-Content -Encoding UTF8 .\data\generados\distribucion.json
```

Para una medición pequeña y repetible, usar 20.000 comentarios:

```powershell
python -X utf8 .\scripts\carga_o_prueba.py --cantidad 20000 --cargar --procesos 4
Get-Content -Encoding UTF8 .\data\generados\medicion.json
```

Para cargar el volumen superior al millón cuando se disponga de tiempo y espacio:

```powershell
python -X utf8 .\scripts\carga_o_prueba.py --cantidad 1000100 --cargar --procesos 4
```

Cada comando genera nuevamente un único CSV. `--cargar` lo importa con dos `COPY FROM` y registra sus confirmaciones. Los timestamps del CSV son milisegundos desde la época Unix para evitar ambigüedad de formato. Se usan sentencias de una fila, sin batches masivos. No se necesita ninguna dependencia Python adicional.

Durante la carga no se deben consultar ni editar esos datos. El script comprueba las confirmaciones de ambas tablas y las claves y fechas del primer y último comentario. Si informa errores, revisar los `.log` y `.err` de `data/generados/`, corregir la causa y repetir la misma cantidad. Las dos importaciones no forman una transacción.

El script reemplaza el CSV y sus resúmenes en `data/generados/`, pero no elimina datos de Cassandra. Repetir la misma cantidad actualiza las mismas claves sin duplicarlas. Esa medición corresponde a reescrituras, no a comentarios nuevos. Usar una cantidad menor tampoco elimina los datos sobrantes de una carga anterior. Guardar el resumen de una medición antes de repetirla.

La distinción entre volumen generado, cargado y confirmado, junto con la tasa real observada, está en [rendimiento](docs/rendimiento.md).

## Reiniciar y comprobar persistencia

Leer un comentario estable de ambas tablas antes y después del reinicio, sin volver a ejecutar la carga:

```powershell
$lecturaHito6 = "SELECT comentario_id, contenido, likes FROM fixture2030_comentarios.comentarios_por_partido WHERE partido_id='PAR-001' AND minuto='2030-06-10T18:00:00Z' AND segmento=2 AND creado_en='2030-06-10T18:00:20Z' AND comentario_id='MUESTRA-001'; SELECT comentario_id, contenido, likes FROM fixture2030_comentarios.comentarios_por_usuario WHERE usuario_id='USR-00001' AND dia='2030-06-10' AND creado_en='2030-06-10T18:00:20Z' AND comentario_id='MUESTRA-001';"
docker compose exec -T cassandra cqlsh -e $lecturaHito6
docker compose restart cassandra
```

Esperar a que vuelvan a responder `nodetool status` y `SHOW VERSION`, como en el inicio. Después:

```powershell
docker compose exec -T cassandra cqlsh -e $lecturaHito6
```

Ambas tablas deben conservar `MUESTRA-001`, `Buen comienzo` y 2 likes. Esta prueba comprueba la persistencia después de un reinicio.

Para detener y volver a iniciar conservando los datos:

```powershell
docker compose stop cassandra
docker compose start cassandra
```

## Documentación

- [Patrones de acceso](docs/patrones_de_acceso.md). Volumen previsto, consultas y relación con los hitos anteriores.
- [Modelo tabular](docs/modelo_tabular.md). Columnas, claves y operaciones sobre las dos tablas.
- [Decisiones de particionamiento](docs/decisiones_de_particionamiento.md). Tamaños estimados, distribución de escrituras y trade-offs.
- [Datos](data/README.md). Muestra y generación de comentarios sintéticos.
- [Rendimiento y evidencia](docs/rendimiento.md). Método, resultados y limitaciones de las pruebas.
