# Ejecución completa del monitoreo

El 16 de noviembre de 2026 se ejecutó la demostración de 23:47:01.861 a 23:53:05.462, UTC−03, durante 363,6 segundos. El [resultado original](demostracion.json) conserva `completa: true`, las tres fases comprobadas, cero errores inesperados, recuperación con PONG y cierre de la sesión temporal con 204.

## Versión y configuración

El código ejecutado corresponde a **10f3c7d37e1bb6cb48067cc256a54991ade1d7c6**. La API se reconstruyó desde ese commit y se recreó su contenedor. Su imagen es `sha256:c5fed5ced746a672c6dd1bda37504907aec5061436caeaf3a816e081f218ee04`. La sección `version` del resultado contiene la etiqueta OCI, los hashes coincidentes de los 30 archivos de `/app` y la ausencia de montajes que reemplacen código. La evidencia puede incorporarse a un commit posterior y conserva esta identidad.

Prometheus usa scraping y evaluación cada 15 s. Las tasas y el histograma usan ventanas de 2 min. Las reglas conservan 30 s para indisponibilidad y 1 min para errores mayores a 5 %, con al menos 20 requests en la ventana. Se ejecutaron dos clientes con una pausa de 0,5 s entre respuestas, timeout de 15 s y sin recargar muestras.

El [entorno](entorno.json) identifica las imágenes y contenedores. También registra el dashboard provisionado, sus seis paneles idénticos al JSON versionado y la consulta correcta de la fuente Prometheus desde Grafana. La otra instancia `fixture2030-redis` no se detuvo. La falla afectó únicamente a `grupo13-hito7-redis-1`, conservando su contenedor y sus datos.

## Resultados

| Observación | Antes | Durante la falla | Después |
| --- | --- | --- | --- |
| Inicio de carga, UTC−03 | 23:47:03 | 23:49:04 | 23:50:49 |
| Duración programada | 120 s | 105 s | 135 s |
| Respuestas 200 / 404 / 503 | 352 / 116 / 0 | 206 / 102 / 102 | 396 / 131 / 0 |
| Caché observada | 118 HIT | 102 BYPASS | 131 HIT y 1 MISS |
| Endpoints de métricas API, MongoDB y Redis | UP | UP | UP |
| `mongodb_up` / `redis_up` | 1 / 1 | 1 / 0 | 1 / 1 |
| Salud / lectura de sesión | 200 / 200 | 503 / 503 | 200 / 200 |
| Alertas al comprobar la fase | Ninguna | Ambas firing | Ninguna |
| RPS de negocio, ventana 2 min | 3,88 | 3,85 | 3,90 |
| P95 estimado por buckets | 9,61 ms | 9,28 ms | 9,12 ms |
| Media del histograma | 4,65 ms | 4,55 ms | 4,09 ms |
| 5xx por segundo, ventana 2 min | 0 | 0,859 | 0 |
| Conexiones MongoDB / clientes Redis | 7 / 3 | 7 / sin muestra | 7 / 3 |

Las tasas y latencias son consultas al cierre de cada fase sobre la ventana móvil, no percentiles exactos del conjunto completo de requests. Las series de todo el intervalo también están guardadas. La ausencia de la métrica de clientes Redis durante su caída no equivale a cero. El exporter siguió respondiendo y `redis_up=0` describió su falta de conexión al motor.

Los 404 y los 503 indicados son errores deliberados. La ficha de equipo siguió respondiendo desde MongoDB con BYPASS durante la caída. El estado de salud identificó Redis como la única fuente no disponible. Después, las seis fuentes respondieron correctamente y las alertas quedaron resueltas. InfluxDB respondió 200 con `puntos: []`, compatible con la retención de siete días. No se comprobó una agregación con datos recientes.

El [intento anterior](../demo-20261116/README.md) quedó incompleto por observar la segunda alerta en `pending`. Esta ejecución verificó ambas en `firing` a las 23:50:49.533, UTC−03. Alcanzó las condiciones sin prolongar los tramos iniciales. Las pruebas unitarias cubren la espera adicional, la resolución y el vencimiento del plazo sin aceptar `pending` como activación.

## Comandos y validación

Desde la raíz del repositorio, con las seis fuentes existentes iniciadas:

```powershell
$revisionH13 = git rev-parse HEAD
docker compose -f 'Hito 10/docker-compose.yml' build --build-arg "VCS_REF=$revisionH13" api
docker compose -f 'Hito 10/docker-compose.yml' up -d --no-build api
python -X utf8 'Hito 13/verificar_version.py' --salida 'tmp/h13-version-final.json'
docker compose -f 'Hito 10/docker-compose.yml' exec -T api python -m pytest tests/unit tests/integration -q -rs -p no:cacheprovider
python -X utf8 'Hito 13/demo.py' --falla-redis --salida 'Hito 13/evidencia/demo-20261116-final'
```

Estos son los comandos de esta ejecución, cuando HEAD era el commit indicado. Para repetir, usar una carpeta de evidencia y un archivo de versión nuevos. El script rechaza sobrescribir resultados. Al ejecutar desde un commit posterior, reconstruir y verificar esa versión o usar un checkout separado del commit original, con los `.env` locales necesarios. No atribuir a una versión nueva los resultados guardados aquí.

Las [validaciones registradas](validacion.txt) incluyen Compose de los Hitos 10 y 13, `promtool check config`, `promtool check rules`, nueve pruebas de la demostración y el resultado de pytest de la API. Resultado actual: 52 pruebas aprobadas, cero fallidas y una omitida. La omisión corresponde a estadísticas recientes de InfluxDB sin puntos retenidos. No se ejecutó la carga que sugiere el mensaje automático de esa prueba. La comprobación del Hito 12 se conservó sin repetir su carga.

## Capturas

- [01_targets.png](01_targets.png): captura real de los cuatro targets disponibles, obtenida durante la fase posterior. UP acredita acceso a cada endpoint de métricas.
- `02_dashboard.png`: pendiente. Abrir [Grafana en el intervalo exacto](http://127.0.0.1:3000/d/fixture2030-h13?from=1794883621861&to=1794883985462). Mostrar los seis paneles y el intervalo visible del 16/11/2026, 23:47:01 a 23:53:05, UTC−03. Ajustar el zoom del navegador si hace falta. Guardar en `Hito 13/evidencia/demo-20261116-final/02_dashboard.png`.
- `03_alertas.png`: pendiente. Abrir [Prometheus Query](http://127.0.0.1:9090/query), ejecutar `ALERTS{alertstate="firing"} @ 1794883849.533` y seleccionar Table. Deben aparecer `FuenteNoDisponible` y `ErroresAPIAltos`, ambas con valor 1. Guardar en `Hito 13/evidencia/demo-20261116-final/03_alertas.png`. La consulta es histórica, del 16/11/2026 a las 23:50:49.533, UTC−03, equivalente al 17/11/2026 a las 02:50:49.533 UTC. No representa el estado actual de alertas, ya resueltas.

Las capturas pendientes deben obtenerse antes de que venza la retención de siete días de Prometheus. Sus consultas ya están respaldadas por los resultados JSON. La publicación de la entrega permanece pendiente hasta completar ambas imágenes. Las capturas deben mostrar únicamente el monitoreo, sin credenciales ni otras pestañas personales.

Después de guardarlas, verificar su legibilidad y enlazarlas desde este resumen y el README del Hito 13. Actualizar también el estado de las capturas en `defensa.md`. Confirmar esos archivos en Denise, revisar otra vez las referencias remotas, integrar con main conservando el historial y publicar ambas ramas. Usar `Se agrego hito 13` como mensaje de los nuevos commits de cierre y del merge. El cambio local ajeno de `Hito 6/README.md` debe seguir fuera de esa integración, mediante un worktree separado si hace falta.
