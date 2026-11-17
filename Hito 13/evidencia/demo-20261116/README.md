# Intento incompleto del 16 de noviembre de 2026

El [resultado original](demostracion.json) conserva `completa: false`. Se ejecutó entre las 15:03:38 y las 15:07:26, UTC−03, con el commit `ec409d8dfd7993df7f7ca50a1ad03bd9ec4bb301`. La identidad de la imagen y la comparación de sus 30 archivos están dentro del resultado.

La fase previa registró 348 respuestas 200 y 116 respuestas 404 deliberadas. Durante la falla se observaron 204 respuestas 200, 102 respuestas 503 esperadas, 100 respuestas 404 y 102 accesos con BYPASS. El exporter siguió disponible y observó Redis en cero.

La comprobación se realizó después de 105 segundos de carga con Redis detenido. `FuenteNoDisponible` estaba `firing`, pero `ErroresAPIAltos` seguía `pending`. Esta última comenzó su período sostenido a las 15:06:18.917, UTC−03. La consulta se hizo a las 15:07:26.091 y todavía reflejaba la evaluación anterior. Los ciclos de scraping y evaluación de 15 segundos no coinciden necesariamente con el final de la carga.

La ejecución se interrumpió correctamente ante esa condición. No registró la fase posterior y no demuestra una recuperación completa del monitoreo. La finalización recuperó Redis con `PONG` y cerró la sesión con 204. No hubo respuestas inesperadas en las fases registradas.

Este intento se conserva sin modificar sus JSON. La repetición usa una espera acotada que mantiene carga, verifica ambas alertas en `firing` y exige su resolución después de recuperar Redis. No cambia reglas ni umbrales.

[Validaciones de esta versión](validacion.txt) · [Entorno observado](entorno.json)
