# Verificación nueva de la variante optimizada

El 15 de noviembre de 2026 a las 23:36, UTC−03:00, se ejecutó nuevamente el escenario existente desde un checkout limpio y separado del commit **5054f7f333133228cc23c635ad4c4491a4567974**. La optimización se introdujo en **69216b706ae2d501539ccd5be2a44eae3246f5c0**. El commit 5054f7f conserva ese código y solo agrega una corrección al registro de validación.

El cambio acota `Q_EMPATE` al minuto UTC del cursor y conserva los cuatro segmentos. Se verificó el diff antes de ejecutar. No se agregaron optimizaciones ni se alteró el medidor.

## Identidad del código y configuración

- [version.json](version.json) registra el SHA completo, imagen `fixture-h12-verificacion:5054f7f`, su ID, etiqueta de revisión y 28 archivos dentro de `/app` comparados con los blobs de Git mediante SHA256, normalizando CRLF a LF. No existían montajes que reemplazaran código de la imagen.
- [configuracion.json](configuracion.json) conserva el Compose efectivo, checkout limpio y hashes del medidor, generador, configuración y esquema. La API monta el Hito 12 de ese mismo worktree en solo lectura.
- [optimizada.json](optimizada.json) conserva fecha, configuración efectiva, versiones, recursos, fases e integridad antes y después. `commit_base` identifica aquí el commit efectivamente ejecutado. `cambios_locales` está vacío y se verificó además el estado completo del worktree.

Se construyó una imagen nueva desde el worktree y se recreó únicamente la API del Hito 12. Se compararon los archivos del contenedor antes de medir. No se reutilizó sin comprobar la imagen anterior. Cassandra conservó su contenedor y el keyspace `fixture2030_h12`. Solo se ejecutó `datos.py validar`, con cero escrituras. No se llamó a `preparar`.

## Resultados de esta ejecución

| Fase de sostenimiento | Resultado |
| --- | ---: |
| Clientes y duración programada | 8 durante 15 s |
| Requests correctos | 4.762 |
| Fallidos y timeouts | 0 |
| Throughput correcto | 317,134 requests/s |
| Media / P50 | 25,197 / 24,458 ms |
| P95 / P99 | 35,287 / 48,154 ms |
| Integridad completa | OK |

Se verificaron 2.400 comentarios antes y después, 1.200 por partido. La validación recorrió todas las páginas y comprobó atributos, orden, cursores y distribución en 40 particiones. La correlación de logs fue completa. Todas las fases terminaron sin fallos.

Esta es una verificación nueva de la variante identificada, no una quinta repetición de la comparación histórica. El proceso recién construido y los servicios que compartían el equipo no reproducen necesariamente las condiciones de octubre. No se midió nuevamente la variante base y no se infiere una mejora de rendimiento entre fechas. Se mantiene la conclusión histórica de que no hubo mejora uniforme de P95 y P99.

## Comandos usados y reproducción

Desde la raíz del repositorio, con Cassandra iniciada y la muestra ya existente:

```powershell
$checkoutH12 = Join-Path (Split-Path (Get-Location)) 'Fixture-h12-verificacion'
git worktree add --detach $checkoutH12 5054f7f333133228cc23c635ad4c4491a4567974
git -C $checkoutH12 status --porcelain
docker build --label org.opencontainers.image.revision=5054f7f333133228cc23c635ad4c4491a4567974 -t fixture-h12-verificacion:5054f7f "$checkoutH12/Hito 10"
```

Si ese worktree ya existe, verificar su SHA y que esté limpio en vez de volver a crearlo. Se usó una superposición local `tmp/h12-image.yml` con este único contenido:

```yaml
services:
  api:
    image: fixture-h12-verificacion:5054f7f
```

```powershell
docker compose -f "$checkoutH12/Hito 12/docker-compose.yml" -f "$PWD/tmp/h12-image.yml" config --quiet
docker compose -f "$checkoutH12/Hito 12/docker-compose.yml" -f "$PWD/tmp/h12-image.yml" up -d --no-build api
Invoke-RestMethod http://127.0.0.1:8012/openapi.json | Out-Null
$salidaH12 = "Hito 12/evidencia/verificacion-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
python -X utf8 'Hito 13/verificar_version.py' --repo $checkoutH12 --contenedor grupo13-hito12-api-1 --salida "$salidaH12/version.json"
docker exec grupo13-hito12-api-1 python /h12/datos.py validar
python -X utf8 "$checkoutH12/Hito 12/medir.py" --variante optimizada --salida "$salidaH12/optimizada.json"
docker stop grupo13-hito12-api-1
```

Esperar disponibilidad HTTP antes del medidor. Si la validación informa diferencias, conservar los datos y diagnosticar, sin sobrescribir la muestra. La API de esta ejecución quedó detenida al terminar. Cassandra y las demás fuentes permanecen disponibles para la demostración del Hito 13.
