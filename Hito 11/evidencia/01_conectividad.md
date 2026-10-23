# Hito 11 - Ejecución de conectividad

Fecha UTC: 2026-10-22T00:56:28.051886+00:00
Fecha local del lanzador: 2026-10-21T21:56:28.051886-03:00
Commit base: c1bb4cd54905f7a83dbc73420ec96f30bedfb989. Cambios locales del módulo: True.
Origen de conexiones: contenedor grupo13-hito10-api-1. Lanzador: PowerShell/Python en Windows.
Modo: completo. Sin cargas ni escrituras del dominio.

Imagen API: grupo13-hito10-api. Docker Engine: 29.7.2

## Matriz

| Producto | Estado observado | Evaluación del modo solicitado |
| --- | --- | --- |
| mongodb | disponible | completa |
| neo4j | disponible | completa |
| cassandra | disponible | completa |
| redis | disponible | completa |
| influxdb | disponible | completa |
| iris | disponible | completa |

## mongodb

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=27017 protocolo=MongoDB wire contexto=fixture2030.equipos credencial_configurada=True timeout_driver=3.0s driver=pymongo/4.19.0 Python=3.12.15 |
| dns | OK | 5.53 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 3.06 | host.docker.internal:27017 acepta TCP. No acredita protocolo ni identidad. |
| protocolo | OK | 94.68 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | OK | 0 | La conexión autenticada fue aceptada. |
| contexto | OK | 0 | Colección equipos existente y accesible en fixture2030 |
| lectura | OK | 105.64 | find_one equipo=EQ-001, documento encontrado |
| autorizacion | OK | 0 | Lectura autorizada para esta operación. No acredita permisos de escritura. |
| api | OK | 79.11 | GET /api/v1/equipos params={"tamanio": 3} HTTP=200 items=3 X-Request-ID=h11-20261022T005628-mongodb-0 |
| api | OK | 7.46 | GET /api/v1/equipos/EQ-999/jugadores params={"tamanio": 1} HTTP=404 RECURSO_NO_ENCONTRADO X-Request-ID=h11-20261022T005628-mongodb-1 |
| api_validacion | OK | 4.55 | GET /api/v1/equipos params={"tamanio": 0} HTTP=400 VALIDACION_FALLIDA X-Request-ID=h11-20261022T005628-mongodb-2 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261022T005628-mongodb-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261022T005628-mongodb-1 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261022T005628-mongodb-2 |

## neo4j

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=7687 protocolo=Bolt contexto=neo4j credencial_configurada=True timeout_driver=3.0s driver=neo4j/6.4.1 Python=3.12.15 |
| dns | OK | 4.08 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 2.94 | host.docker.internal:7687 acepta TCP. No acredita protocolo ni identidad. |
| http_auxiliar | OK | 47.93 | HTTP 200. Solo accesibilidad HTTP, no acredita acceso a datos. |
| protocolo | OK | 13.89 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | OK | 0 | La conexión autenticada fue aceptada. |
| contexto | OK | 0 | neo4j. Contexto utilizado por el driver, no por el portal. |
| lectura | OK | 16.23 | Cypher parametrizado, partido=PAR-001, encontrado=True, eventos=2, limite=3 |
| autorizacion | OK | 0 | Lectura autorizada para esta operación. No acredita permisos de escritura. |
| api | OK | 66.24 | GET /api/v1/partidos/PAR-001 params={"limiteEventos": 3} HTTP=200 items=2 X-Request-ID=h11-20261022T005628-neo4j-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261022T005628-neo4j-0 |

## cassandra

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=9042 protocolo=CQL contexto=fixture2030_comentarios.comentarios_por_partido credencial_configurada=False timeout_driver=3.0s driver=cassandra-driver/3.30.1 Python=3.12.15 |
| dns | OK | 4.23 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 2.16 | host.docker.internal:9042 acepta TCP. No acredita protocolo ni identidad. |
| protocolo | OK | 70.31 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | WARN | 0 | Sin credencial en el adaptador. El servidor aceptó la operación. |
| contexto | OK | 0 | fixture2030_comentarios.comentarios_por_partido. Contexto utilizado por el driver, no por el portal. |
| lectura | OK | 8.96 | partido=PAR-001, [2030-06-10T18:00:00Z, 2030-06-10T18:01:00Z), 4 segmentos, filas=3, limite=3 |
| autorizacion | OK | 0 | Lectura autorizada para esta operación. No acredita permisos de escritura. |
| api | OK | 120.71 | GET /api/v1/partidos/PAR-001/comentarios params={"desde": "2030-06-10T18:00:00Z", "hasta": "2030-06-10T18:01:00Z", "limite": 3} HTTP=200 items=3 X-Request-ID=h11-20261022T005628-cassandra-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261022T005628-cassandra-0 |

## redis

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=16379 protocolo=RESP contexto=db=0, prefijo=fixture2030:h10 credencial_configurada=False timeout_driver=3.0s driver=redis/8.1.0 Python=3.12.15 |
| dns | OK | 4.52 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 2.24 | host.docker.internal:16379 acepta TCP. No acredita protocolo ni identidad. |
| protocolo | OK | 12.38 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | WARN | 0 | Sin credencial en el adaptador. El servidor aceptó la operación. |
| contexto | OK | 0 | db=0, prefijo=fixture2030:h10. Contexto utilizado por el driver, no por el portal. |
| memoria | OK | 0 | Política=noeviction |
| muestra | WARN | 0 | No existe la clave de demostración configurada. No se creó una. Ausencia no demuestra expiración. |
| lectura | OK | 3.4 | clave=fixture2030:h11:demo:conectividad, tipo=none, TTL=-2. Sin renovar TTL ni mostrar valores. |
| autorizacion | OK | 0 | Lectura autorizada para esta operación. No acredita permisos de escritura. |
| api | OK | 44.35 | GET /api/v1/sesiones/SES-000000000000000000000000 params={} HTTP=404 SESION_NO_VIGENTE X-Request-ID=h11-20261022T005628-redis-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261022T005628-redis-0 |

## influxdb

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=8181 protocolo=HTTP contexto=fixture2030_h8 credencial_configurada=True timeout_driver=3.0s driver=httpx/0.28.1 Python=3.12.15 |
| dns | OK | 4.41 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 1.74 | host.docker.internal:8181 acepta TCP. No acredita protocolo ni identidad. |
| http_auxiliar | OK | 37.21 | HTTP 401. Solo accesibilidad HTTP, no acredita acceso a datos. |
| health_autorizado | OK | 6.67 | Health HTTP 200 con token. La consulta posterior verifica database y tabla. |
| protocolo | OK | 12.27 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | OK | 0 | La conexión autenticada fue aceptada. |
| contexto | OK | 0 | fixture2030_h8. Contexto utilizado por el driver, no por el portal. |
| lectura | OK | 10.36 | DATE_BIN 1m, partido=PAR-001, equipo=EQ-001, [2026-10-22T00:51:00+00:00, 2026-10-22T00:56:00+00:00), intervalos=0. Cero puntos es válido. |
| autorizacion | OK | 0 | Lectura autorizada para esta operación. No acredita permisos de escritura. |
| api | OK | 51.48 | GET /api/v1/partidos/PAR-001/estadisticas params={"equipoId": "EQ-001", "desde": "2026-10-22T00:51:00+00:00", "hasta": "2026-10-22T00:56:00+00:00", "intervalo": "1m"} HTTP=200 items=0 X-Request-ID=h11-20261022T005628-influxdb-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261022T005628-influxdb-0 |

## iris

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=1972 protocolo=Superserver contexto=USER.FixtureH9.Partido credencial_configurada=True timeout_driver=3.0s driver=intersystems-irispython/5.4.1 Python=3.12.15 |
| dns | OK | 4.29 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 2.43 | host.docker.internal:1972 acepta TCP. No acredita protocolo ni identidad. |
| http_auxiliar | OK | 59.15 | HTTP 200. Solo accesibilidad HTTP, no acredita acceso a datos. |
| protocolo | OK | 18.26 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | OK | 0 | La conexión autenticada fue aceptada. |
| contexto | OK | 0 | USER.FixtureH9.Partido. Contexto utilizado por el driver, no por el portal. |
| lectura | OK | 5.02 | FixtureH9.Partido codigo=PAR-001, encontrado=True, eventos=2 |
| autorizacion | OK | 0 | Lectura autorizada para esta operación. No acredita permisos de escritura. |
| api | OK | 56.41 | GET /api/v1/actas/PAR-001 params={} HTTP=200 items=2 X-Request-ID=h11-20261022T005628-iris-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261022T005628-iris-0 |

## Logs correlacionados de la API

```text
req=h11-20261022T005628-mongodb-0 dep=mongodb op=listar_equipos resultado=ok ms=15.19
req=h11-20261022T005628-mongodb-0 metodo=GET ruta=/api/v1/equipos estado=200 ms=31.44
req=h11-20261022T005628-mongodb-1 dep=mongodb op=existe_equipo resultado=ok ms=2.02
req=h11-20261022T005628-mongodb-1 metodo=GET ruta=/api/v1/equipos/EQ-999/jugadores estado=404 ms=2.81
req=h11-20261022T005628-mongodb-2 metodo=GET ruta=/api/v1/equipos estado=400 ms=0.28
req=h11-20261022T005628-neo4j-0 dep=neo4j op=partido resultado=ok ms=18.56
req=h11-20261022T005628-neo4j-0 dep=neo4j op=eventos resultado=ok ms=6.66
req=h11-20261022T005628-neo4j-0 metodo=GET ruta=/api/v1/partidos/PAR-001 estado=200 ms=26.37
req=h11-20261022T005628-cassandra-0 dep=cassandra op=listar_ventana resultado=ok ms=84.63
req=h11-20261022T005628-cassandra-0 metodo=GET ruta=/api/v1/partidos/PAR-001/comentarios estado=200 ms=86.02
req=h11-20261022T005628-redis-0 dep=redis op=obtener_sesion resultado=ok ms=10.06
req=h11-20261022T005628-redis-0 metodo=GET ruta=/api/v1/sesiones/SES-000000000000000000000000 estado=404 ms=10.90
req=h11-20261022T005628-influxdb-0 dep=influxdb op=resumen_ventana resultado=ok ms=7.94
req=h11-20261022T005628-influxdb-0 metodo=GET ruta=/api/v1/partidos/PAR-001/estadisticas estado=200 ms=9.29
req=h11-20261022T005628-iris-0 dep=iris op=leer_acta resultado=ok ms=21.87
req=h11-20261022T005628-iris-0 metodo=GET ruta=/api/v1/actas/PAR-001 estado=200 ms=22.81
```

Resumen: OK=67, WARN=3, FAIL=0, SKIP=0
Código de salida: 0. 0=completa sin fallas, 1=completa con fallas, 2=incompleta.
Los tiempos por prueba excluyen docker exec. Los de API incluyen HTTP y trabajo de sus adaptadores.
Las filas con 0 ms describen configuración o conclusiones de otras operaciones, sin medición independiente.
OK acredita solo la operación indicada. No mide rendimiento ni disponibilidad permanente.
