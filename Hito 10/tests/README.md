# Pruebas

| Carpeta | Necesita | Ejecutar |
| --- | --- | --- |
| `unit/` | Nada (adaptadores en memoria) | `.\.venv\Scripts\python -m pytest tests\unit -v` |
| `integration/` | Contenedores de los Hitos 4 a 9 con sus muestras y `.env` | `.\.venv\Scripts\python -m pytest tests\integration -v` |

Todo junto, con exportación de OpenAPI y verificación de conectividad previa: `powershell -ExecutionPolicy Bypass -File .\scripts\ejecutar_pruebas.ps1`.

Si `/salud` no responde 200, las pruebas de integración que usan las seis fuentes se omiten con el motivo. Las de dependencia detenida no necesitan contenedores: apuntan cada driver real a un puerto sin servicio.

Datos que crean y limpian las pruebas de integración: un comentario en `PAR-064` (se borra de ambas tablas), sesiones en Redis (se cierran o vencen) y el acta `H10-TEMPORAL` en IRIS (se borra). La prueba de estadísticas se omite si InfluxDB no tiene puntos retenidos para `PAR-001`: ejecutar `scripts/cargar_muestra_influx.py`.

Detalle de escenarios y resultados: [docs/pruebas_y_evidencia.md](../docs/pruebas_y_evidencia.md).
