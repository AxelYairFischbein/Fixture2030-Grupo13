# Hito 11 - Ejecución de conectividad

Fecha UTC: 2026-11-17T21:05:11.958686+00:00
Fecha local del lanzador: 2026-11-17T18:05:11.958686-03:00
Commit base: ed49e3fcb1dad4f1767dc17dbb0c87753e9cc4aa. Cambios locales del módulo: False.
Origen de conexiones: contenedor grupo13-hito10-api-1. Lanzador: PowerShell/Python en Windows.
Modo: completo. Sin cargas ni escrituras del dominio.

Imagen API: grupo13-hito10-api. Docker Engine: 29.7.2

## Matriz

| Producto | Estado observado | Evaluación del modo solicitado |
| --- | --- | --- |
| mongodb | disponible | completa |
| neo4j | disponible | incompleta |
| cassandra | disponible | incompleta |
| redis | disponible | incompleta |
| influxdb | disponible | incompleta |
| iris | disponible | incompleta |

## mongodb

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=27017 protocolo=MongoDB wire contexto=fixture2030.equipos credencial_configurada=True timeout_driver=3.0s driver=pymongo/4.19.0 Python=3.12.16 |
| dns | OK | 3.95 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 1.34 | host.docker.internal:27017 acepta TCP. No acredita protocolo ni identidad. |
| protocolo | OK | 12.54 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | OK | 0.89 | connectionStatus: identidad autenticada coincide con la configurada. |
| autorizacion | OK | 1.34 | connectionStatus: privilegio find sobre fixture2030.equipos. No evalúa escrituras ni otras colecciones. |
| contexto | OK | 0 | Colección equipos existente y accesible en fixture2030 |
| lectura | OK | 2.53 | find_one equipo=EQ-001, documento encontrado |
| api | OK | 42.62 | GET /api/v1/equipos params={"tamanio": 3} HTTP=200 items=3 X-Request-ID=h11-20261117T210511-mongodb-0 |
| api | OK | 6.25 | GET /api/v1/equipos/EQ-999/jugadores params={"tamanio": 1} HTTP=404 RECURSO_NO_ENCONTRADO X-Request-ID=h11-20261117T210511-mongodb-1 |
| api_validacion | OK | 4.14 | GET /api/v1/equipos params={"tamanio": 0} HTTP=400 VALIDACION_FALLIDA X-Request-ID=h11-20261117T210511-mongodb-2 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261117T210511-mongodb-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261117T210511-mongodb-1 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261117T210511-mongodb-2 |

## neo4j

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=7687 protocolo=Bolt contexto=neo4j credencial_configurada=True timeout_driver=3.0s driver=neo4j/6.4.1 Python=3.12.16 |
| dns | OK | 4.09 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 1.47 | host.docker.internal:7687 acepta TCP. No acredita protocolo ni identidad. |
| http_auxiliar | OK | 114.49 | HTTP 200. Solo accesibilidad HTTP, no acredita acceso a datos. |
| protocolo | OK | 8.82 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | OK | 152.45 | SHOW CURRENT USER: identidad coincide con la configurada. |
| autorizacion | WARN | 0.0 | Autorización no verificada independientemente. No se inspeccionan permisos efectivos por recurso. La lectura se registra por separado y no acredita otras operaciones. |
| contexto | OK | 0 | neo4j. Contexto utilizado por el driver, no por el portal. |
| lectura | OK | 11.57 | Cypher parametrizado, partido=PAR-001, encontrado=True, eventos=2, limite=3 |
| api | OK | 51.52 | GET /api/v1/partidos/PAR-001 params={"limiteEventos": 3} HTTP=200 items=2 X-Request-ID=h11-20261117T210511-neo4j-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261117T210511-neo4j-0 |

## cassandra

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=9042 protocolo=CQL contexto=fixture2030_comentarios.comentarios_por_partido credencial_configurada=False timeout_driver=3.0s driver=cassandra-driver/3.30.1 Python=3.12.16 |
| dns | OK | 4.19 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 1.14 | host.docker.internal:9042 acepta TCP. No acredita protocolo ni identidad. |
| protocolo | OK | 49.46 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | WARN | 0.0 | Autenticación no verificada independientemente. El cliente del módulo no inspecciona la identidad autenticada. Una operación aceptada solo acredita acceso funcional. |
| autorizacion | WARN | 0.0 | Autorización no verificada independientemente. No se inspeccionan permisos efectivos por recurso. La lectura se registra por separado y no acredita otras operaciones. |
| contexto | OK | 0 | fixture2030_comentarios.comentarios_por_partido. Contexto utilizado por el driver, no por el portal. |
| lectura | OK | 11.09 | partido=PAR-001, [2030-06-10T18:00:00Z, 2030-06-10T18:01:00Z), 4 segmentos, filas=3, limite=3 |
| api | OK | 100.67 | GET /api/v1/partidos/PAR-001/comentarios params={"desde": "2030-06-10T18:00:00Z", "hasta": "2030-06-10T18:01:00Z", "limite": 3} HTTP=200 items=3 X-Request-ID=h11-20261117T210511-cassandra-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261117T210511-cassandra-0 |

## redis

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=16379 protocolo=RESP contexto=db=0, prefijo=fixture2030:h10 credencial_configurada=False timeout_driver=3.0s driver=redis/8.1.0 Python=3.12.16 |
| dns | OK | 3.99 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 1.18 | host.docker.internal:16379 acepta TCP. No acredita protocolo ni identidad. |
| protocolo | OK | 12.44 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | WARN | 0.87 | ACL WHOAMI: identidad efectiva consultada. Autenticación por credencial no verificada independientemente. No se deduce que esté deshabilitada. |
| autorizacion | OK | 1.69 | ACL DRYRUN: permiso GET para la clave configurada, sin ejecutar GET. No verifica otros comandos ni la existencia de la clave. |
| contexto | OK | 0 | db=0, prefijo=fixture2030:h10. Contexto utilizado por el driver, no por el portal. |
| memoria | OK | 0 | Política=noeviction |
| muestra | WARN | 0 | No existe la clave de demostración configurada. No se creó una. Ausencia no demuestra expiración. |
| lectura | OK | 2.54 | clave=fixture2030:h11:demo:conectividad, tipo=none, TTL=-2. Sin renovar TTL ni mostrar valores. |
| api | OK | 44.33 | GET /api/v1/sesiones/SES-000000000000000000000000 params={} HTTP=404 SESION_NO_VIGENTE X-Request-ID=h11-20261117T210511-redis-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261117T210511-redis-0 |

## influxdb

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=8181 protocolo=HTTP contexto=fixture2030_h8 credencial_configurada=True timeout_driver=3.0s driver=httpx/0.28.1 Python=3.12.16 |
| dns | OK | 4.62 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 1.19 | host.docker.internal:8181 acepta TCP. No acredita protocolo ni identidad. |
| http_auxiliar | OK | 38.24 | HTTP 401. Solo accesibilidad HTTP, no acredita acceso a datos. |
| health_autorizado | OK | 6.15 | Health HTTP 200 con token. La consulta posterior verifica database y tabla. |
| protocolo | OK | 4.49 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | WARN | 0.0 | Autenticación no verificada independientemente. El cliente del módulo no inspecciona la identidad autenticada. Una operación aceptada solo acredita acceso funcional. |
| autorizacion | WARN | 0.0 | Autorización no verificada independientemente. No se inspeccionan permisos efectivos por recurso. La lectura se registra por separado y no acredita otras operaciones. |
| contexto | OK | 0 | fixture2030_h8. Contexto utilizado por el driver, no por el portal. |
| lectura | OK | 5.11 | DATE_BIN 1m, partido=PAR-001, equipo=EQ-001, [2026-11-17T21:00:00+00:00, 2026-11-17T21:05:00+00:00), intervalos=0. Cero puntos es válido. |
| api | OK | 44.22 | GET /api/v1/partidos/PAR-001/estadisticas params={"equipoId": "EQ-001", "desde": "2026-11-17T21:00:00+00:00", "hasta": "2026-11-17T21:05:00+00:00", "intervalo": "1m"} HTTP=200 items=0 X-Request-ID=h11-20261117T210511-influxdb-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261117T210511-influxdb-0 |

## iris

| Prueba | Resultado | ms | Diagnóstico y contexto |
| --- | --- | ---: | --- |
| configuracion | OK | 0 | host=host.docker.internal puerto=1972 protocolo=Superserver contexto=USER.FixtureH9.Partido credencial_configurada=True timeout_driver=3.0s driver=intersystems-irispython/5.4.1 Python=3.12.16 |
| dns | OK | 4.66 | host.docker.internal: 2 direcciones resueltas |
| tcp | OK | 1.29 | host.docker.internal:1972 acepta TCP. No acredita protocolo ni identidad. |
| http_auxiliar | OK | 82.3 | HTTP 200. Solo accesibilidad HTTP, no acredita acceso a datos. |
| protocolo | OK | 18.75 | Driver completó ping/lectura constante en el contexto configurado. |
| autenticacion | WARN | 0.0 | Autenticación no verificada independientemente. El cliente del módulo no inspecciona la identidad autenticada. Una operación aceptada solo acredita acceso funcional. |
| autorizacion | WARN | 0.0 | Autorización no verificada independientemente. No se inspeccionan permisos efectivos por recurso. La lectura se registra por separado y no acredita otras operaciones. |
| contexto | OK | 0 | USER.FixtureH9.Partido. Contexto utilizado por el driver, no por el portal. |
| lectura | OK | 3.13 | FixtureH9.Partido codigo=PAR-001, encontrado=True, eventos=2 |
| api | OK | 57.58 | GET /api/v1/actas/PAR-001 params={} HTTP=200 items=2 X-Request-ID=h11-20261117T210511-iris-0 |
| logs | OK | 0 | Correlación HTTP/dependencia comprobada. X-Request-ID=h11-20261117T210511-iris-0 |

## Logs correlacionados de la API

```text
req=h11-20261117T210511-mongodb-0 dep=mongodb op=listar_equipos resultado=ok ms=10.07
req=h11-20261117T210511-mongodb-0 metodo=GET ruta=/api/v1/equipos estado=200 ms=11.22
req=h11-20261117T210511-mongodb-1 dep=mongodb op=existe_equipo resultado=ok ms=1.38
req=h11-20261117T210511-mongodb-1 metodo=GET ruta=/api/v1/equipos/EQ-999/jugadores estado=404 ms=2.09
req=h11-20261117T210511-mongodb-2 metodo=GET ruta=/api/v1/equipos estado=400 ms=0.26
req=h11-20261117T210511-neo4j-0 dep=neo4j op=partido resultado=ok ms=12.7
req=h11-20261117T210511-neo4j-0 dep=neo4j op=eventos resultado=ok ms=5.88
req=h11-20261117T210511-neo4j-0 metodo=GET ruta=/api/v1/partidos/PAR-001 estado=200 ms=19.65
req=h11-20261117T210511-cassandra-0 dep=cassandra op=listar_ventana resultado=ok ms=67.49
req=h11-20261117T210511-cassandra-0 metodo=GET ruta=/api/v1/partidos/PAR-001/comentarios estado=200 ms=68.82
req=h11-20261117T210511-redis-0 dep=redis op=obtener_sesion resultado=ok ms=6.58
req=h11-20261117T210511-redis-0 metodo=GET ruta=/api/v1/sesiones/SES-000000000000000000000000 estado=404 ms=7.53
req=h11-20261117T210511-influxdb-0 dep=influxdb op=resumen_ventana resultado=ok ms=7.65
req=h11-20261117T210511-influxdb-0 metodo=GET ruta=/api/v1/partidos/PAR-001/estadisticas estado=200 ms=9.01
req=h11-20261117T210511-iris-0 dep=iris op=leer_acta resultado=ok ms=21.4
req=h11-20261117T210511-iris-0 metodo=GET ruta=/api/v1/actas/PAR-001 estado=200 ms=22.56
```

Resumen: OK=61, WARN=9, FAIL=0, SKIP=0
Código de salida: 2. 0=completa sin fallas, 1=completa con fallas, 2=incompleta.
Los tiempos por prueba excluyen docker exec. Los de API incluyen HTTP y trabajo de sus adaptadores.
Las filas con 0 ms describen configuración o conclusiones de otras operaciones, sin medición independiente.
OK acredita solo la operación indicada. No mide rendimiento ni disponibilidad permanente.
