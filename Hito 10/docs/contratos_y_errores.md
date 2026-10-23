# Contratos, validación, errores e idempotencia

El contrato completo está en [openapi/openapi.yaml](../openapi/openapi.yaml) (OpenAPI 3.1, versión 1.0.0, servidor `http://127.0.0.1:8000`, tags por módulo, parámetros, cuerpos, schemas, ejemplos y todos los códigos posibles). Se explora en Swagger UI (`/docs`). Se regenera con `scripts/exportar_openapi.py`, y una prueba falla si el archivo versionado difiere de la aplicación.

No hay autenticación de consumidores en este hito. La API solo escucha en `127.0.0.1`.

## Formato de respuestas

Éxito (200/201):

```json
{
  "data": { "equipoId": "EQ-004", "codigo": "F04", "...": "..." },
  "meta": {
    "requestId": "c87d9add97584820a2e4d5d9b0d6e630",
    "fuentes": [
      {"fuente": "redis", "operacion": "leer_cache_equipo", "resultado": "ok", "ms": 0.8},
      {"fuente": "mongodb", "operacion": "buscar_equipo", "resultado": "ok", "ms": 1.9}
    ],
    "paginacion": {"pagina": 1, "tamanio": 16, "total": 64, "siguienteCursor": null},
    "cache": "MISS"
  }
}
```

`meta.fuentes` lista las operaciones efectivamente ejecutadas en cada fuente durante ese request: es la evidencia de que el endpoint llega a su fuente. 204 no lleva cuerpo.

Error (4xx/5xx), siempre con la misma forma:

```json
{"error": {"codigo": "DEPENDENCIA_NO_DISPONIBLE", "mensaje": "No se pudo utilizar la fuente redis.",
           "requestId": "11791c71f91140feb8c7b810b4440640", "dependencia": "redis"}}
```

`detalles` aparece en validaciones (campo y problema, sin repetir el valor recibido) y en `/salud`. Nunca se incluyen URIs, consultas, trazas ni mensajes del driver.

Encabezados: `X-Request-ID` en todas las respuestas (se acepta uno entrante de 8-64 caracteres `[A-Za-z0-9-]`), `X-Cache` en la ficha, `Idempotent-Replayed: true` en una repetición.

## Códigos HTTP

| Situación | HTTP | `codigo` | Ejemplo |
| --- | --- | --- | --- |
| Parámetro, cuerpo o encabezado fuera del contrato | 400 | `VALIDACION_FALLIDA` | `EQ-04`, ventana de 20 min, falta `Idempotency-Key` |
| Recurso inexistente | 404 | `RECURSO_NO_ENCONTRADO` | `EQ-999`, `PAR-999`, acta `NO-EXISTE` |
| Sesión inexistente, cerrada o vencida | 404 | `SESION_NO_VIGENTE` | Redis no distingue "venció" de "nunca existió". Ambas son ausencia de sesión vigente |
| Ruta o método inexistente | 404/405 | `RUTA_NO_ENCONTRADA` / `METODO_NO_PERMITIDO` | |
| Transición de estado prohibida | 409 | `TRANSICION_INVALIDA` | `PENDIENTE -> FINALIZADO` |
| `Idempotency-Key` reutilizada con otro cuerpo, o la original aún en curso | 409 | `CONFLICTO` | |
| Fuente caída, credencial rechazada u otra falla de acceso del driver | 503 | `DEPENDENCIA_NO_DISPONIBLE` | incluye `dependencia` |
| Tiempo de espera agotado e identificado por el driver | 504 | `DEPENDENCIA_TIMEOUT` | incluye `dependencia` |
| Error no previsto | 500 | `ERROR_INTERNO` | detalle solo en el log, ubicable por `requestId` |

FastAPI documenta 422 por defecto. La aplicación reemplaza ese código por 400 tanto en la respuesta como en el OpenAPI.

La clasificación de timeout utiliza tipos y códigos específicos, sin interpretar cualquier excepción de un driver como demora. Una causa no identificada conserva el 503 y el tipo de excepción en el log. Los errores internos producen 500 y registran únicamente su tipo y request ID, sin traceback ni mensajes que puedan contener secretos. `/salud` conserva el 503 agregado si alguna fuente falla. La caché conserva el fallback ante 503 o 504.

## Validación (antes de tocar cualquier fuente)

| Entrada | Regla |
| --- | --- |
| `equipoId` | `^EQ-\d{3}$` |
| `partidoId` | `^PAR-\d{3}$` |
| `sesionId` | `^SES-[0-9a-f]{24}$` |
| `codigo` de acta | `^[A-Z0-9][A-Z0-9-]{2,23}$` |
| `usuarioId` | `^USR-\d{5}$` |
| `confederacion`, `posicion`, `intervalo`, `estado` | Enumeraciones cerradas |
| `pagina` / `tamanio` | 1-1000 / 1-50 |
| `limite` (agenda / eventos / comentarios) | 1-20 / 1-50 / 1-50 |
| `desde`, `hasta` | ISO-8601. Sin zona se toman como UTC. Debe cumplirse `hasta > desde` |
| Ventana de comentarios | ≤ 5 minutos (≤ 6 buckets de minuto × 4 segmentos = 24 particiones, límite del Hito 6) |
| Ventana de estadísticas | `desde` y `hasta` juntos u omitidos, con ≤ 720 intervalos por equipo |
| `cursor` | `^\d{13}_[A-Za-z0-9-]{1,64}$` y dentro de la ventana pedida |
| Cuerpos JSON | Sin campos adicionales (`extra=forbid`). `contenido` admite 1-280 caracteres |
| `Idempotency-Key` | Obligatoria en `POST comentarios`, `^[A-Za-z0-9-]{8,64}$` |

Las pruebas unitarias comprueban que una entrada inválida no produce ninguna llamada a los adaptadores.

## Paginación y límites

- **MongoDB**: página y tamaño con orden estable (`rankingReferencia, equipoId` o `numeroCamiseta`) y `total`.
- **Cassandra**: ventana obligatoria y cursor de continuación `"<ms>_<comentarioId>"`. Como el orden global es `creado_en DESC, comentario_id ASC`, la página siguiente lee primero los empates del mismo instante con ID mayor y después los instantes anteriores. Ninguna fila se repite ni se pierde (probado con la muestra del Hito 6: 8 comentarios en páginas de 3).
- **Neo4j**: `LIMIT`/slice en el Cypher.
- **InfluxDB**: agregación obligatoria (`DATE_BIN`), tope de intervalos y `LIMIT` calculado. Los intervalos se alinean a la época Unix, por lo que el primero y el último de una ventana pueden ser parciales (lo indica `muestras`).
- **IRIS**: `TOP 100` eventos por acta.

## Lectura, escritura e idempotencia

| Endpoint | Efecto | Repetición |
| --- | --- | --- |
| Todos los `GET` | Sin efecto sobre los datos (la ficha puede poblar la caché) | Seguro |
| `GET /sesiones/{id}` | No renueva el TTL (a diferencia de la actividad del Hito 7) | Seguro |
| `DELETE /equipos/{id}/cache` | Invalida la copia. La próxima lectura vuelve a MongoDB | 204 siempre, mismo estado final |
| `DELETE /sesiones/{id}` | Cierra la sesión | 204 siempre, mismo estado final |
| `PUT /actas/{codigo}/estado` | Avanza el estado mediante `CambiarEstado()` | Pedir el estado actual responde 200 `cambio: false`, sin guardar. Una transición prohibida responde 409 y no modifica |
| `POST /sesiones` | Crea una sesión nueva con ID aleatorio | **No idempotente**: cada llamada abre otra sesión (un usuario puede tener varias, como en el Hito 7) |
| `POST /partidos/{id}/comentarios` | Crea el comentario en las dos tablas del Hito 6 | **Idempotente por clave**, ver abajo |

### Escritura segura de comentarios

Cassandra hace upsert por clave primaria, pero `creado_en` y el ID se generan al escribir: un reintento ingenuo crearía otra fila. Por eso:

1. `SET NX EX 86400` de `fixture2030:h10:idem:comentario:{partido}:{clave}` con estado `EN_CURSO` y la huella SHA-256 del cuerpo. Solo un request puede reservar la clave.
2. Si la clave existía: misma huella y `COMPLETADO` → 200 con el comentario original y `Idempotent-Replayed: true`. Otra huella o `EN_CURSO` → 409.
3. Se verifica que el partido exista en Neo4j (evita comentarios huérfanos) y se escribe un `BATCH LOGGED` con las dos representaciones (misma decisión del Hito 6). Segmento = `CRC32(comentario_id) % 4`.
4. Se guarda el resultado en la clave (`COMPLETADO`).

Si Neo4j o Cassandra fallan, la clave se libera y el cliente puede reintentar con la misma clave. Si Redis falla después de escribir, la fila existe y la clave queda `EN_CURSO` hasta su TTL: los reintentos reciben 409 en vez de duplicar. Sin Redis no se aceptan publicaciones (503), porque no se podría garantizar la no duplicación.
