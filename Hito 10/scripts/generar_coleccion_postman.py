"""Genera postman/fixture2030_collection.json (Postman Collection v2.1).

Uso, desde la carpeta "Hito 10":  python scripts/generar_coleccion_postman.py

La colección se declara acá y no se edita a mano: cada caso de uso tiene una carpeta con
la request exitosa y sus escenarios de error, cada una con tests de código HTTP, código de
error (§6.2) y campos del contrato. Un script de colección comprueba en TODAS las
respuestas el X-Request-Id y, en los errores, el formato único de casos_de_uso.md §6.1.

Los IDs de sesión son credenciales: las variables sesionLector, sesionModerador y
sesionOperador quedan vacías y las completa el entorno local que genera
scripts/crear_sesiones_prueba.ps1 (.local/postman_entorno_local.json, ignorado por git).
"""

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "postman" / "fixture2030_collection.json"

CARPETA_MANUAL = "Dependencias caídas (manual)"
SESION_INEXISTENTE = "SES-NO-EXISTE-00000000"

VARIABLES = [
    ("baseUrl", "http://127.0.0.1:8000", "URL de la API (scripts/iniciar_api.ps1)."),
    ("sesionLector", "", "Sesión rol lector de USR-00001. La completa el entorno local."),
    ("sesionModerador", "", "Sesión rol moderador de USR-00002. La completa el entorno local."),
    ("sesionOperador", "", "Sesión rol operador de USR-00003. La completa el entorno local."),
    ("equipoId", "EQ-001", "Equipo de la muestra (Hitos 4 y 5)."),
    ("jugadorId", "JUG-0313", "Jugador de la muestra del Hito 4."),
    ("partidoId", "PAR-001", "Partido con eventos, comentarios, estadísticas y acta. Solo se lee."),
    ("partidoSinActa", "PAR-002", "Partido del calendario sin acta en IRIS."),
    ("partidoComentarios", "PAR-064", "Partido donde la colección publica y modera su comentario."),
    ("influxDesde", "2026-10-16T00:12:00Z",
     "Inicio de la ventana de 5 min de la carga de muestra del Hito 8 (ajustar si se recargó)."),
    ("influxHasta", "2026-10-16T00:17:00Z", "Fin de la ventana de la carga de muestra del Hito 8."),
    ("partidoTemporal", "",
     "Acta temporal PAR-9xx para CU-19 (python -m tests.integracion.iris_temporal crear). "
     "Vacía → se omiten las transiciones reales. Nunca PAR-001."),
    ("idempotencyKey", "", "Interna: la genera la publicación de CU-09."),
    ("contenidoComentario", "", "Interna."),
    ("comentarioId", "", "Interna: comentario publicado en CU-09."),
    ("creadoEn", "", "Interna."),
    ("minutoComentario", "", "Interna."),
    ("diaComentario", "", "Interna."),
]

PRE_COLECCION = """\
// Una variable de sesión vacía produciría un 400 confuso: se avisa antes de enviar.
const encabezado = pm.request.headers.get('X-Session-Id');
if (encabezado !== undefined && encabezado !== null) {
    const valor = pm.variables.replaceIn(encabezado);
    if (!valor || /^\\{\\{.*\\}\\}$/.test(valor)) {
        throw new Error('Variable de sesión vacía: ejecutar scripts/crear_sesiones_prueba.ps1 '
            + 'y seleccionar el entorno .local/postman_entorno_local.json');
    }
}"""

TEST_COLECCION = """\
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const requestId = pm.response.headers.get('X-Request-Id');
pm.test('X-Request-Id es un UUID', () => pm.expect(requestId).to.match(UUID));
if (pm.response.code >= 400) {
    pm.test('Error con el formato único (§6.1)', () => {
        const error = pm.response.json().error;
        pm.expect(error).to.be.an('object');
        pm.expect(error.codigo).to.be.a('string');
        pm.expect(error.mensaje).to.be.a('string');
        pm.expect(error.requestId).to.eql(requestId);
        pm.expect(error.detalles).to.be.an('array');
    });
}
const texto = pm.response.text();
pm.test('Sin identificadores internos (_id, elementId, %ID)', () => {
    pm.expect(texto).to.not.include('"_id"');
    pm.expect(texto).to.not.include('elementId');
    pm.expect(texto).to.not.include('%ID');
});"""

OMITIR_SIN_TEMPORAL = """\
if (!pm.variables.get('partidoTemporal')) {
    console.log('partidoTemporal vacía: se omite la transición real de CU-19');
    pm.execution.skipRequest();
}"""


def js(texto: str) -> list[str]:
    return texto.split("\n")


def _lista_js(valores) -> str:
    return json.dumps(list(valores), ensure_ascii=False)


def request(nombre: str, metodo: str, ruta: str, esperado: int, *, codigo: str | None = None,
            claves=(), sesion: str | None = None, cuerpo=None, encabezados=None, tests="",
            pre="", descripcion: str = "") -> dict:
    """Una request con sus tests. `sesion` es el nombre de una variable o un valor literal."""
    lineas = [f"pm.test('HTTP {esperado}', () => pm.response.to.have.status({esperado}));"]
    if codigo:
        lineas.append(f"pm.test('error.codigo = {codigo}', () => "
                      f"pm.expect(pm.response.json().error.codigo).to.eql('{codigo}'));")
    if claves:
        lineas.append(f"pm.test('Campos del contrato', () => "
                      f"pm.expect(pm.response.json()).to.include.all.keys({_lista_js(claves)}));")
    if tests:
        lineas.append(f"if (pm.response.code === {esperado}) {{")
        lineas += ["    " + linea for linea in tests.strip("\n").split("\n")]
        lineas.append("}")
    cabeceras = []
    if sesion is not None:
        valor = sesion if sesion.startswith("SES-") or sesion == "x" else "{{" + sesion + "}}"
        cabeceras.append({"key": "X-Session-Id", "value": valor})
    for clave, valor in (encabezados or {}).items():
        cabeceras.append({"key": clave, "value": valor})
    req = {"method": metodo, "header": cabeceras, "url": "{{baseUrl}}" + ruta}
    if descripcion:
        req["description"] = descripcion
    if cuerpo is not None:
        cabeceras.append({"key": "Content-Type", "value": "application/json"})
        req["body"] = {"mode": "raw", "raw": json.dumps(cuerpo, ensure_ascii=False),
                       "options": {"raw": {"language": "json"}}}
    eventos = [{"listen": "test", "script": {"type": "text/javascript", "exec": lineas}}]
    if pre:
        eventos.insert(0, {"listen": "prerequest",
                           "script": {"type": "text/javascript", "exec": js(pre.strip("\n"))}})
    return {"name": nombre, "event": eventos, "request": req}


def carpeta(nombre: str, descripcion: str, items: list[dict]) -> dict:
    return {"name": nombre, "description": descripcion, "item": items}


E = "/api/v1/equipos"
P = "/api/v1/partidos"
S = "/api/v1/sesiones/actual"
FICHA_EQUIPO = ["equipoId", "codigo", "nombre", "confederacion", "region", "rankingReferencia",
                "sedeBase", "participacionesMundiales", "titulosMundiales", "estado"]
FICHA_JUGADOR = ["jugadorId", "equipoId", "nombre", "apellido", "fechaNacimiento",
                 "nacionalidadCodigo", "posicion", "numeroCamiseta", "pieHabil", "alturaCm",
                 "partidosInternacionales", "golesInternacionales", "estadoPlantel"]
SESION = ["usuarioId", "rol", "estado", "expiraEnSegundos"]
COMENTARIOS = ["partidoId", "items", "siguienteCursor"]
CREADO = ["comentarioId", "partidoId", "usuarioId", "creadoEn", "contenido", "estado", "likes"]
MODERADO = ["comentarioId", "partidoId", "usuarioId", "creadoEn", "estadoAnterior", "estado",
            "cambio"]
MEDIDAS = ["muestras", "muestrasEsperadas", "posesionMedia", "pasesNuevos", "tiros",
           "intervalosInvalidos", "completo"]
ACTA = ["partidoId", "estadioId", "estado", "arbitro", "eventos"]
TRANSICION = ["partidoId", "estadoAnterior", "estadoActual", "cambio"]
VENTANA = "desde={{influxDesde}}&hasta={{influxHasta}}"
MODERAR = P + "/{{partidoComentarios}}/comentarios/{{comentarioId}}"
PUBLICAR = P + "/{{partidoComentarios}}/comentarios"
IDEM = {"Idempotency-Key": "{{idempotencyKey}}"}
TRANSICIONES_TEMPORAL = P + "/{{partidoTemporal}}/acta/transiciones"


def contiene_comentario(variable_items: str = "pm.response.json().items") -> str:
    return (f"const ids = {variable_items}.map(c => c.comentarioId);\n"
            "pm.test('Incluye el comentario publicado una sola vez', () => pm.expect("
            "ids.filter(i => i === pm.collectionVariables.get('comentarioId'))).to.have.length(1));")


CARPETAS = [
    carpeta("Salud", "GET /api/v1/salud: estado por dependencia y del catálogo de partidos.", [
        request("Salud de la API", "GET", "/api/v1/salud", 200,
                claves=["estado", "dependencias", "catalogoPartidos"], tests="""
const s = pm.response.json();
pm.test('Las seis dependencias informadas', () => pm.expect(s.dependencias).to.have.all.keys(
    ['mongodb', 'neo4j', 'cassandra', 'redis', 'influxdb', 'iris']));
pm.test('Catálogo cargado con 64 partidos', () => {
    pm.expect(s.catalogoPartidos.estado).to.eql('cargado');
    pm.expect(s.catalogoPartidos.partidos).to.eql(64);
});"""),
    ]),
    carpeta("Errores globales", "Ruta inexistente y método no admitido (§6.2).", [
        request("Ruta inexistente → 404 RUTA_NO_ENCONTRADA", "GET", "/api/v1/no-existe", 404,
                codigo="RUTA_NO_ENCONTRADA"),
        request("Método no admitido → 405 METODO_NO_PERMITIDO", "PUT", E + "/{{equipoId}}", 405,
                codigo="METODO_NO_PERMITIDO",
                tests="pm.test('Encabezado Allow con GET', () => "
                      "pm.expect(pm.response.headers.get('Allow')).to.include('GET'));"),
    ]),
    carpeta("CU-01 · Ver ficha de un equipo", "Cache-aside Redis + MongoDB. Se invalida primero "
            "la copia (CU-14) para observar MISS y después HIT.", [
        request("Preparación: invalidar la copia (CU-14)", "DELETE",
                "/api/v1/cache/equipos/{{equipoId}}", 204, sesion="sesionOperador"),
        request("Ficha EQ-001 → 200 MISS", "GET", E + "/{{equipoId}}", 200, claves=FICHA_EQUIPO,
                tests="""
pm.test('X-Cache: MISS', () => pm.expect(pm.response.headers.get('X-Cache')).to.eql('MISS'));
pm.test('Mismo equipoId', () => pm.expect(pm.response.json().equipoId).to.eql(pm.variables.get('equipoId')));"""),
        request("Repetida → 200 HIT", "GET", E + "/{{equipoId}}", 200, claves=FICHA_EQUIPO,
                tests="pm.test('X-Cache: HIT', () => "
                      "pm.expect(pm.response.headers.get('X-Cache')).to.eql('HIT'));"),
        request("Formato inválido EQ-1 → 400", "GET", E + "/EQ-1", 400, codigo="VALIDACION"),
        request("Inexistente EQ-999 → 404", "GET", E + "/EQ-999", 404,
                codigo="EQUIPO_NO_ENCONTRADO"),
    ]),
    carpeta("CU-02 · Listar equipos de una confederación", "MongoDB, Hito 4 Q03.", [
        request("CONMEBOL rankingMax=50 → 8 equipos", "GET",
                E + "?confederacion=CONMEBOL&rankingMax=50", 200,
                claves=["items", "pagina", "limite", "total"], tests="""
const p = pm.response.json();
pm.test('8 equipos (Q03)', () => { pm.expect(p.total).to.eql(8); pm.expect(p.items).to.have.length(8); });
pm.test('Orden rankingReferencia ASC', () => {
    const r = p.items.map(e => e.rankingReferencia);
    pm.expect(r).to.eql([...r].sort((a, b) => a - b));
});"""),
        request("Filtros sin coincidencias → 200 vacío", "GET",
                E + "?confederacion=OFC&rankingMax=1", 200, claves=["items", "total"],
                tests="pm.test('items vacío', () => pm.expect(pm.response.json().items).to.eql([]));"),
        request("Sin confederacion → 400", "GET", E, 400, codigo="VALIDACION"),
        request("Confederación fuera del enum → 400", "GET", E + "?confederacion=FIFA", 400,
                codigo="VALIDACION"),
        request("limite=51 → 400", "GET", E + "?confederacion=UEFA&limite=51", 400,
                codigo="VALIDACION"),
    ]),
    carpeta("CU-03 · Ver plantel de un equipo", "MongoDB, Hito 4 Q06/Q07.", [
        request("Plantel EQ-002 → 24 jugadores", "GET", E + "/EQ-002/jugadores", 200,
                claves=["equipoId", "items", "pagina", "limite", "total"], tests="""
pm.test('24 jugadores', () => pm.expect(pm.response.json().items).to.have.length(24));"""),
        request("EQ-001 página 2 con limite=5 → 5 jugadores", "GET",
                E + "/{{equipoId}}/jugadores?pagina=2&limite=5", 200, claves=["items", "pagina"],
                tests="pm.test('5 jugadores de la página 2', () => { "
                      "pm.expect(pm.response.json().items).to.have.length(5); "
                      "pm.expect(pm.response.json().pagina).to.eql(2); });"),
        request("Filtro posicion=ARQUERO → 3", "GET", E + "/EQ-002/jugadores?posicion=ARQUERO",
                200, claves=["items"],
                tests="pm.test('3 arqueros', () => pm.expect(pm.response.json().items"
                      ".filter(j => j.posicion === 'ARQUERO')).to.have.length(3));"),
        request("Equipo inexistente EQ-999 → 404", "GET", E + "/EQ-999/jugadores", 404,
                codigo="EQUIPO_NO_ENCONTRADO"),
        request("Posición fuera del enum → 400", "GET", E + "/EQ-002/jugadores?posicion=PORTERO",
                400, codigo="VALIDACION"),
        request("limite=25 → 400", "GET", E + "/EQ-002/jugadores?limite=25", 400,
                codigo="VALIDACION"),
    ]),
    carpeta("CU-04 · Ver ficha de un jugador", "MongoDB, Hito 4 Q02.", [
        request("Ficha JUG-0313 → 200", "GET", "/api/v1/jugadores/{{jugadorId}}", 200,
                claves=FICHA_JUGADOR,
                tests="pm.test('equipoId EQ-014', () => "
                      "pm.expect(pm.response.json().equipoId).to.eql('EQ-014'));"),
        request("Inexistente JUG-9999 → 404", "GET", "/api/v1/jugadores/JUG-9999", 404,
                codigo="JUGADOR_NO_ENCONTRADO"),
        request("Formato inválido JUG-1 → 400", "GET", "/api/v1/jugadores/JUG-1", 400,
                codigo="VALIDACION"),
    ]),
    carpeta("CU-05 · Ver agenda y rivales de un equipo", "Neo4j, Hito 5 Q04 + Q06.", [
        request("Agenda EQ-001 → PAR-001 y PAR-033", "GET", E + "/{{equipoId}}/partidos", 200,
                claves=["equipoId", "items"], tests="""
const items = pm.response.json().items;
pm.test('PAR-001 vs EQ-002 y PAR-033 vs EQ-003', () => {
    pm.expect(items.map(p => p.partidoId)).to.eql(['PAR-001', 'PAR-033']);
    pm.expect(items.map(p => p.rival.equipoId)).to.eql(['EQ-002', 'EQ-003']);
});
pm.test('Sin estado del partido (fuente IRIS)', () => items.forEach(p => pm.expect(p).to.not.have.property('estado')));"""),
        request("Inexistente EQ-999 → 404", "GET", E + "/EQ-999/partidos", 404,
                codigo="EQUIPO_NO_ENCONTRADO"),
        request("limite=0 → 400", "GET", E + "/{{equipoId}}/partidos?limite=0", 400,
                codigo="VALIDACION"),
    ]),
    carpeta("CU-06 · Ver eventos y participantes de un partido", "Neo4j, Hito 5 Q07.", [
        request("Eventos PAR-001 → 2 sustituciones", "GET", P + "/{{partidoId}}/eventos", 200,
                claves=["partidoId", "items"], tests="""
const items = pm.response.json().items;
pm.test('Minutos 60 y 65 con SALE y ENTRA', () => {
    pm.expect(items.map(e => e.minuto)).to.eql([60, 65]);
    items.forEach(e => pm.expect(e.participantes.map(p => p.rol)).to.eql(['SALE', 'ENTRA']));
});"""),
        request("Inexistente PAR-999 → 404", "GET", P + "/PAR-999/eventos", 404,
                codigo="PARTIDO_NO_ENCONTRADO"),
        request("Formato inválido PAR-1 → 400", "GET", P + "/PAR-1/eventos", 400,
                codigo="VALIDACION"),
    ]),
    carpeta("CU-07 · Ver partidos de un rango de fechas", "Neo4j, Hito 5 Q09. Rango [desde, "
            "hasta) de hasta 7 días con zona horaria.", [
        request("10/06/2030 → PAR-001…PAR-008", "GET",
                P + "?desde=2030-06-10T00:00:00Z&hasta=2030-06-11T00:00:00Z", 200,
                claves=["items"], tests="""
const ids = pm.response.json().items.map(p => p.partidoId);
pm.test('PAR-001…PAR-008', () => pm.expect(ids).to.eql(
    ['PAR-001', 'PAR-002', 'PAR-003', 'PAR-004', 'PAR-005', 'PAR-006', 'PAR-007', 'PAR-008']));"""),
        request("Filtro estadioId=EST-01 → solo PAR-001", "GET",
                P + "?desde=2030-06-10T00:00:00Z&hasta=2030-06-11T00:00:00Z&estadioId=EST-01",
                200, claves=["items"],
                tests="pm.test('PAR-001', () => pm.expect(pm.response.json().items"
                      ".map(p => p.partidoId)).to.eql(['PAR-001']));"),
        request("Estadio sin partidos EST-99 → 200 vacío", "GET",
                P + "?desde=2030-06-10T00:00:00Z&hasta=2030-06-11T00:00:00Z&estadioId=EST-99",
                200, tests="pm.test('items vacío', () => "
                           "pm.expect(pm.response.json().items).to.eql([]));"),
        request("Intervalo invertido → 400", "GET",
                P + "?desde=2030-06-11T00:00:00Z&hasta=2030-06-10T00:00:00Z", 400,
                codigo="VALIDACION"),
        request("Intervalo de más de 7 días → 400", "GET",
                P + "?desde=2030-06-10T00:00:00Z&hasta=2030-06-18T00:00:00Z", 400,
                codigo="VALIDACION"),
        request("Fecha sin zona horaria → 400", "GET",
                P + "?desde=2030-06-10T00:00:00&hasta=2030-06-11T00:00:00Z", 400,
                codigo="VALIDACION"),
        request("Sin hasta → 400", "GET", P + "?desde=2030-06-10T00:00:00Z", 400,
                codigo="VALIDACION"),
    ]),
    carpeta("CU-08 · Leer comentarios de un partido", "Cassandra, Hito 6 Q1/Q2, sobre la "
            "muestra de PAR-001. X-Session-Id opcional: sin rol moderador solo visibles.", [
        request("Minuto anónimo → solo visibles", "GET",
                P + "/{{partidoId}}/comentarios?minuto=2030-06-10T18:01:00Z", 200,
                claves=COMENTARIOS, tests="""
const items = pm.response.json().items;
pm.test('Hay comentarios de la muestra', () => pm.expect(items).to.not.be.empty);
pm.test('Todos visibles', () => items.forEach(c => pm.expect(c.estado).to.eql('visible')));
pm.test('Orden creadoEn DESC', () => {
    const t = items.map(c => c.creadoEn);
    pm.expect(t).to.eql([...t].sort().reverse());
});"""),
        request("Minuto con moderador → todos los estados", "GET",
                P + "/{{partidoId}}/comentarios?minuto=2030-06-10T18:01:00Z", 200,
                sesion="sesionModerador", claves=COMENTARIOS,
                tests="pm.test('Incluye estados no visibles', () => pm.expect(pm.response.json()"
                      ".items.some(c => c.estado !== 'visible')).to.be.true);"),
        request("Ventana con limite=3 → siguienteCursor", "GET",
                P + "/{{partidoId}}/comentarios?desde=2030-06-10T18:00:30Z"
                    "&hasta=2030-06-10T18:02:10Z&limite=3", 200,
                sesion="sesionModerador", claves=COMENTARIOS, tests="""
pm.test('3 ítems y cursor', () => {
    pm.expect(pm.response.json().items).to.have.length(3);
    pm.expect(pm.response.json().siguienteCursor).to.be.a('string');
});"""),
        request("Sin minuto ni ventana (últimos 60 s) → 200", "GET",
                P + "/{{partidoId}}/comentarios", 200, claves=COMENTARIOS),
        request("Ventana de 6 min → 400", "GET",
                P + "/{{partidoId}}/comentarios?desde=2030-06-10T18:00:00Z"
                    "&hasta=2030-06-10T18:06:00Z", 400, codigo="VALIDACION"),
        request("minuto y desde juntos → 400", "GET",
                P + "/{{partidoId}}/comentarios?minuto=2030-06-10T18:01:00Z"
                    "&desde=2030-06-10T18:00:00Z&hasta=2030-06-10T18:01:00Z", 400,
                codigo="VALIDACION"),
        request("Cursor inválido → 400", "GET",
                P + "/{{partidoId}}/comentarios?minuto=2030-06-10T18:01:00Z&antesDe=basura", 400,
                codigo="VALIDACION"),
        request("Sesión inexistente → 401", "GET",
                P + "/{{partidoId}}/comentarios?minuto=2030-06-10T18:01:00Z", 401,
                sesion=SESION_INEXISTENTE, codigo="SESION_NO_VIGENTE"),
        request("Partido fuera del catálogo PAR-999 → 404", "GET", P + "/PAR-999/comentarios",
                404, codigo="PARTIDO_NO_ENCONTRADO"),
    ]),
    carpeta("CU-09 · Publicar un comentario", "Redis (sesión + idempotencia) + Cassandra. Cada "
            "ejecución publica un comentario nuevo en {{partidoComentarios}} (dato de prueba).", [
        request("Publicar → 201", "POST", PUBLICAR, 201, sesion="sesionLector",
                encabezados=IDEM, cuerpo={"contenido": "{{contenidoComentario}}"}, claves=CREADO,
                pre="""
pm.collectionVariables.set('idempotencyKey', pm.variables.replaceIn('{{$guid}}'));
pm.collectionVariables.set('contenidoComentario', 'Comentario de prueba Postman ' + new Date().toISOString());""",
                tests="""
const c = pm.response.json();
pm.collectionVariables.set('comentarioId', c.comentarioId);
pm.collectionVariables.set('creadoEn', c.creadoEn);
pm.collectionVariables.set('minutoComentario', c.creadoEn.substring(0, 16) + ':00Z');
pm.collectionVariables.set('diaComentario', c.creadoEn.substring(0, 10));
pm.test('comentarioId = Idempotency-Key', () => pm.expect(c.comentarioId).to.eql(
    pm.collectionVariables.get('idempotencyKey').toLowerCase()));
pm.test('Nace visible, con 0 likes y autor de la sesión', () => {
    pm.expect(c.estado).to.eql('visible');
    pm.expect(c.likes).to.eql(0);
    pm.expect(c.usuarioId).to.eql('USR-00001');
});"""),
        request("Reintento con la misma clave → mismo comentario", "POST", PUBLICAR, 201,
                sesion="sesionLector", encabezados=IDEM,
                cuerpo={"contenido": "{{contenidoComentario}}"}, claves=CREADO, tests="""
pm.test('Mismo comentarioId y creadoEn', () => {
    pm.expect(pm.response.json().comentarioId).to.eql(pm.collectionVariables.get('comentarioId'));
    pm.expect(pm.response.json().creadoEn).to.eql(pm.collectionVariables.get('creadoEn'));
});"""),
        request("Misma clave con otro contenido → 409", "POST", PUBLICAR, 409,
                sesion="sesionLector", encabezados=IDEM, cuerpo={"contenido": "Otro texto"},
                codigo="IDEMPOTENCY_KEY_REUTILIZADA"),
        request("CU-08 del minuto → aparece una sola vez", "GET",
                PUBLICAR + "?minuto={{minutoComentario}}", 200, claves=COMENTARIOS,
                tests=contiene_comentario()),
        request("CU-10 del autor → aparece una sola vez", "GET",
                "/api/v1/usuarios/USR-00001/comentarios?dia={{diaComentario}}", 200,
                sesion="sesionLector", tests=contiene_comentario()),
        request("Sin X-Session-Id → 401", "POST", PUBLICAR, 401,
                encabezados={"Idempotency-Key": "{{$guid}}"}, cuerpo={"contenido": "Sin sesión"},
                codigo="SESION_REQUERIDA"),
        request("Sin Idempotency-Key → 400", "POST", PUBLICAR, 400, sesion="sesionLector",
                cuerpo={"contenido": "Sin clave"}, codigo="VALIDACION"),
        request("Campo extra en el body → 400", "POST", PUBLICAR, 400, sesion="sesionLector",
                encabezados={"Idempotency-Key": "{{$guid}}"},
                cuerpo={"contenido": "Hola", "usuarioId": "USR-00009"}, codigo="VALIDACION"),
        request("Contenido de 281 caracteres → 400", "POST", PUBLICAR, 400, sesion="sesionLector",
                encabezados={"Idempotency-Key": "{{$guid}}"}, cuerpo={"contenido": "x" * 281},
                codigo="VALIDACION"),
        request("Partido fuera del catálogo PAR-999 → 404", "POST", P + "/PAR-999/comentarios",
                404, sesion="sesionLector", encabezados={"Idempotency-Key": "{{$guid}}"},
                cuerpo={"contenido": "Partido inexistente"}, codigo="PARTIDO_NO_ENCONTRADO"),
    ]),
    carpeta("CU-10 · Ver historial diario de un autor", "Redis (sesión y rol) + Cassandra, "
            "Hito 6 Q3. El propio autor o un moderador.", [
        request("Historial propio (lector USR-00001) → 200", "GET",
                "/api/v1/usuarios/USR-00001/comentarios?dia=2030-06-10", 200,
                sesion="sesionLector",
                claves=["usuarioId", "dia", "items", "siguienteCursor"]),
        request("Moderador ve el historial de otro → 200", "GET",
                "/api/v1/usuarios/USR-00001/comentarios?dia=2030-06-10", 200,
                sesion="sesionModerador", claves=["usuarioId", "dia", "items"]),
        request("Día sin comentarios → 200 vacío", "GET",
                "/api/v1/usuarios/USR-00001/comentarios?dia=2030-01-01", 200,
                sesion="sesionLector",
                tests="pm.test('items vacío', () => pm.expect(pm.response.json().items).to.eql([]));"),
        request("Lector pide el historial de otro → 403", "GET",
                "/api/v1/usuarios/USR-00003/comentarios?dia=2030-06-10", 403,
                sesion="sesionLector", codigo="ROL_NO_AUTORIZADO"),
        request("Sin X-Session-Id → 401", "GET",
                "/api/v1/usuarios/USR-00001/comentarios?dia=2030-06-10", 401,
                codigo="SESION_REQUERIDA"),
        request("Día con formato inválido → 400", "GET",
                "/api/v1/usuarios/USR-00001/comentarios?dia=10-06-2030", 400,
                sesion="sesionLector", codigo="VALIDACION"),
        request("usuarioId con formato inválido → 400", "GET",
                "/api/v1/usuarios/USR-1/comentarios?dia=2030-06-10", 400, sesion="sesionLector",
                codigo="VALIDACION"),
    ]),
    carpeta("CU-20 · Moderar un comentario", "Moderador sobre el comentario publicado en CU-09: "
            "lo oculta y después lo restaura.", [
        request("Ocultar → 200 cambio=true", "PATCH", MODERAR, 200, sesion="sesionModerador",
                cuerpo={"creadoEn": "{{creadoEn}}", "estado": "oculto"}, claves=MODERADO,
                tests="""
const m = pm.response.json();
pm.test('visible → oculto', () => {
    pm.expect(m.estadoAnterior).to.eql('visible');
    pm.expect(m.estado).to.eql('oculto');
    pm.expect(m.cambio).to.be.true;
});"""),
        request("Repetir → 200 cambio=false", "PATCH", MODERAR, 200, sesion="sesionModerador",
                cuerpo={"creadoEn": "{{creadoEn}}", "estado": "oculto"}, claves=MODERADO,
                tests="pm.test('cambio=false', () => pm.expect(pm.response.json().cambio)"
                      ".to.be.false);"),
        request("CU-08 anónimo → ya no aparece", "GET",
                PUBLICAR + "?minuto={{minutoComentario}}", 200, tests="""
pm.test('El comentario oculto no se muestra a la APP', () => pm.expect(pm.response.json().items
    .map(c => c.comentarioId)).to.not.include(pm.collectionVariables.get('comentarioId')));"""),
        request("CU-10 moderador → aparece oculto", "GET",
                "/api/v1/usuarios/USR-00001/comentarios?dia={{diaComentario}}", 200,
                sesion="sesionModerador", tests="""
const c = pm.response.json().items.find(i => i.comentarioId === pm.collectionVariables.get('comentarioId'));
pm.test('Mismo estado en comentarios_por_usuario', () => pm.expect(c.estado).to.eql('oculto'));"""),
        request("Restaurar visible → 200", "PATCH", MODERAR, 200, sesion="sesionModerador",
                cuerpo={"creadoEn": "{{creadoEn}}", "estado": "visible"}, claves=MODERADO,
                tests="pm.test('oculto → visible', () => pm.expect(pm.response.json().estado)"
                      ".to.eql('visible'));"),
        request("creadoEn equivocado → 404 sin escribir", "PATCH", MODERAR, 404,
                sesion="sesionModerador",
                cuerpo={"creadoEn": "2030-01-01T00:00:00.000Z", "estado": "oculto"},
                codigo="COMENTARIO_NO_ENCONTRADO"),
        request("Lector → 403", "PATCH", MODERAR, 403, sesion="sesionLector",
                cuerpo={"creadoEn": "{{creadoEn}}", "estado": "oculto"},
                codigo="ROL_NO_AUTORIZADO"),
        request("Sin X-Session-Id → 401", "PATCH", MODERAR, 401,
                cuerpo={"creadoEn": "{{creadoEn}}", "estado": "oculto"},
                codigo="SESION_REQUERIDA"),
        request("Volver a pendiente → 400", "PATCH", MODERAR, 400, sesion="sesionModerador",
                cuerpo={"creadoEn": "{{creadoEn}}", "estado": "pendiente"}, codigo="VALIDACION"),
        request("Partido fuera del catálogo PAR-999 → 404", "PATCH",
                P + "/PAR-999/comentarios/{{comentarioId}}", 404, sesion="sesionModerador",
                cuerpo={"creadoEn": "{{creadoEn}}", "estado": "oculto"},
                codigo="PARTIDO_NO_ENCONTRADO"),
    ]),
    carpeta("CU-11 · Consultar la sesión vigente", "Redis HGETALL + TTL. No renueva.", [
        request("Sesión lector → 200", "GET", S, 200, sesion="sesionLector", claves=SESION,
                tests="""
const s = pm.response.json();
pm.test('Rol lector y TTL > 0', () => { pm.expect(s.rol).to.eql('lector'); pm.expect(s.expiraEnSegundos).to.be.above(0); });
pm.test('No expone el ID ni ultima_actividad', () => {
    pm.expect(s).to.not.have.property('sesionId');
    pm.expect(s).to.not.have.property('ultima_actividad');
});"""),
        request("Sin X-Session-Id → 401", "GET", S, 401, codigo="SESION_REQUERIDA"),
        request("Sesión inexistente → 401", "GET", S, 401, sesion=SESION_INEXISTENTE,
                codigo="SESION_NO_VIGENTE"),
        request("Formato inválido → 400", "GET", S, 400, sesion="x", codigo="VALIDACION"),
    ]),
    carpeta("CU-12 · Registrar actividad de la sesión", "EVAL atómico que renueva el TTL.", [
        request("Renovar sesión lector → 200 (1800 s)", "POST", S + "/actividad", 200,
                sesion="sesionLector", claves=["expiraEnSegundos"],
                tests="pm.test('expiraEnSegundos = 1800', () => "
                      "pm.expect(pm.response.json().expiraEnSegundos).to.eql(1800));"),
        request("Sesión inexistente → 401 (no se recrea)", "POST", S + "/actividad", 401,
                sesion=SESION_INEXISTENTE, codigo="SESION_NO_VIGENTE"),
        request("Sin X-Session-Id → 401", "POST", S + "/actividad", 401,
                codigo="SESION_REQUERIDA"),
    ]),
    carpeta("CU-14 · Invalidar la ficha cacheada de un equipo", "Redis DEL, rol operador.", [
        request("Operador invalida EQ-001 → 204", "DELETE", "/api/v1/cache/equipos/{{equipoId}}",
                204, sesion="sesionOperador"),
        request("Repetir (sin copia) → 204", "DELETE", "/api/v1/cache/equipos/{{equipoId}}", 204,
                sesion="sesionOperador"),
        request("CU-01 siguiente → MISS", "GET", E + "/{{equipoId}}", 200,
                tests="pm.test('X-Cache: MISS', () => "
                      "pm.expect(pm.response.headers.get('X-Cache')).to.eql('MISS'));"),
        request("Lector → 403", "DELETE", "/api/v1/cache/equipos/{{equipoId}}", 403,
                sesion="sesionLector", codigo="ROL_NO_AUTORIZADO"),
        request("Sin X-Session-Id → 401", "DELETE", "/api/v1/cache/equipos/{{equipoId}}", 401,
                codigo="SESION_REQUERIDA"),
        request("Formato inválido EQ-1 → 400", "DELETE", "/api/v1/cache/equipos/EQ-1", 400,
                sesion="sesionOperador", codigo="VALIDACION"),
    ]),
    carpeta("CU-15 · Ver estado reciente de un equipo en un partido", "InfluxDB, Hito 8 P2. "
            "Ventana [hasta − 60 s, hasta) de la carga de muestra.", [
        request("PAR-001 / EQ-001 → últimas 5 observaciones", "GET",
                P + "/{{partidoId}}/equipos/{{equipoId}}/estadisticas/recientes"
                    "?hasta={{influxHasta}}", 200,
                claves=["partidoId", "equipoId", "estadioId", "items", "ultimaObservacion"],
                tests="""
const r = pm.response.json();
pm.test('5 observaciones en orden time DESC', () => {
    pm.expect(r.items).to.have.length(5);
    const t = r.items.map(o => o.time);
    pm.expect(t).to.eql([...t].sort().reverse());
});
pm.test('ultimaObservacion = primer time', () => pm.expect(r.ultimaObservacion).to.eql(r.items[0].time));"""),
        request("Ventana sin puntos → 200 vacío y null", "GET",
                P + "/{{partidoId}}/equipos/{{equipoId}}/estadisticas/recientes"
                    "?hasta=2020-01-01T00:00:00Z", 200, tests="""
pm.test('items vacío y ultimaObservacion null', () => {
    pm.expect(pm.response.json().items).to.eql([]);
    pm.expect(pm.response.json().ultimaObservacion).to.be.null;
});"""),
        request("Equipo que no disputa el partido → 404", "GET",
                P + "/{{partidoId}}/equipos/EQ-003/estadisticas/recientes", 404,
                codigo="EQUIPO_NO_PARTICIPA"),
        request("Partido fuera del catálogo PAR-999 → 404", "GET",
                P + "/PAR-999/equipos/{{equipoId}}/estadisticas/recientes", 404,
                codigo="PARTIDO_NO_ENCONTRADO"),
        request("limite=61 → 400", "GET",
                P + "/{{partidoId}}/equipos/{{equipoId}}/estadisticas/recientes?limite=61", 400,
                codigo="VALIDACION"),
        request("hasta sin zona horaria → 400", "GET",
                P + "/{{partidoId}}/equipos/{{equipoId}}/estadisticas/recientes"
                    "?hasta=2026-10-16T00:17:00", 400, codigo="VALIDACION"),
    ]),
    carpeta("CU-16 · Comparar los equipos de un partido", "InfluxDB, Hito 8 P3: reproduce los "
            "valores del Hito 8 sobre la ventana de la carga de muestra.", [
        request("PAR-001 en la ventana de muestra → valores del Hito 8", "GET",
                P + "/{{partidoId}}/estadisticas/comparacion?" + VENTANA, 200,
                claves=["partidoId", "desde", "hasta", "equipos"], tests="""
const eq = pm.response.json().equipos;
pm.test('Dos equipos con todas las medidas', () => {
    pm.expect(eq.map(e => e.equipoId)).to.eql(['EQ-001', 'EQ-002']);
    eq.forEach(e => pm.expect(e).to.include.all.keys(%s));
});
pm.test('300 muestras, 30 y 25 pases, 1 tiro, 0 inválidos', () => {
    pm.expect(eq.map(e => e.muestras)).to.eql([300, 300]);
    pm.expect(eq.map(e => e.pasesNuevos)).to.eql([30, 25]);
    pm.expect(eq.map(e => e.tiros)).to.eql([1, 1]);
    pm.expect(eq.map(e => e.intervalosInvalidos)).to.eql([0, 0]);
});""" % _lista_js(MEDIDAS)),
        request("Intervalo invertido → 400", "GET",
                P + "/{{partidoId}}/estadisticas/comparacion?desde={{influxHasta}}"
                    "&hasta={{influxDesde}}", 400, codigo="VALIDACION"),
        request("Ventana de más de 5 min → 400", "GET",
                P + "/{{partidoId}}/estadisticas/comparacion?desde=2026-10-16T00:11:00Z"
                    "&hasta=2026-10-16T00:17:00Z", 400, codigo="VALIDACION"),
        request("Sin desde → 400", "GET",
                P + "/{{partidoId}}/estadisticas/comparacion?hasta={{influxHasta}}", 400,
                codigo="VALIDACION"),
        request("Partido fuera del catálogo PAR-999 → 404", "GET",
                P + "/PAR-999/estadisticas/comparacion?" + VENTANA, 404,
                codigo="PARTIDO_NO_ENCONTRADO"),
    ]),
    carpeta("CU-17 · Ver evolución por minuto", "InfluxDB DATE_BIN, Hito 8 P4.", [
        request("1m → 5 intervalos por equipo que suman lo de CU-16", "GET",
                P + "/{{partidoId}}/estadisticas/evolucion?" + VENTANA, 200,
                claves=["partidoId", "desde", "hasta", "resolucion", "series"], tests="""
const series = pm.response.json().series;
pm.test('Dos series de 5 intervalos', () => {
    pm.expect(series.map(s => s.equipoId)).to.eql(['EQ-001', 'EQ-002']);
    series.forEach(s => pm.expect(s.intervalos).to.have.length(5));
});
pm.test('Sumas de pases = CU-16 (30 y 25)', () => pm.expect(series.map(
    s => s.intervalos.reduce((t, i) => t + i.pasesNuevos, 0))).to.eql([30, 25]));"""),
        request("5m filtrado por EQ-002 → una serie", "GET",
                P + "/{{partidoId}}/estadisticas/evolucion?" + VENTANA
                + "&resolucion=5m&equipoId=EQ-002", 200,
                tests="pm.test('Solo EQ-002', () => pm.expect(pm.response.json().series"
                      ".map(s => s.equipoId)).to.eql(['EQ-002']));"),
        request("Resolución 10m → 400", "GET",
                P + "/{{partidoId}}/estadisticas/evolucion?" + VENTANA + "&resolucion=10m", 400,
                codigo="VALIDACION"),
        request("Ventana de 3 h → 400", "GET",
                P + "/{{partidoId}}/estadisticas/evolucion?desde=2026-10-15T21:17:00Z"
                    "&hasta=2026-10-16T00:17:00Z", 400, codigo="VALIDACION"),
        request("equipoId que no disputa el partido → 404", "GET",
                P + "/{{partidoId}}/estadisticas/evolucion?" + VENTANA + "&equipoId=EQ-003", 404,
                codigo="EQUIPO_NO_PARTICIPA"),
        request("Partido fuera del catálogo PAR-999 → 404", "GET",
                P + "/PAR-999/estadisticas/evolucion?" + VENTANA, 404,
                codigo="PARTIDO_NO_ENCONTRADO"),
    ]),
    carpeta("CU-18 · Ver el acta de un partido", "IRIS, Hito 9. Única fuente del estado.", [
        request("Acta PAR-001 → PENDIENTE, EST-01, 2 eventos", "GET", P + "/{{partidoId}}/acta",
                200, claves=ACTA, tests="""
const a = pm.response.json();
pm.test('PENDIENTE en EST-01 con ARB-001 y dos eventos', () => {
    pm.expect(a.estado).to.eql('PENDIENTE');
    pm.expect(a.estadioId).to.eql('EST-01');
    pm.expect(a.arbitro.codigo).to.eql('ARB-001');
    pm.expect(a.eventos).to.have.length(2);
});
pm.test('Sin licencia del árbitro', () => pm.expect(a.arbitro).to.not.have.property('licencia'));"""),
        request("Partido sin acta PAR-002 → 404", "GET", P + "/{{partidoSinActa}}/acta", 404,
                codigo="ACTA_NO_ENCONTRADA"),
        request("Formato inválido PAR-1 → 400", "GET", P + "/PAR-1/acta", 400,
                codigo="VALIDACION"),
    ]),
    carpeta("CU-19 · Cambiar el estado de un partido", "Redis (rol operador) + IRIS "
            "CambiarEstado(). Las transiciones reales usan {{partidoTemporal}} (PAR-9xx, creado "
            "por scripts/ejecutar_pruebas.ps1 o con python -m tests.integracion.iris_temporal "
            "crear); si está vacía se omiten. Sobre PAR-001 solo se prueban rechazos que no "
            "llegan a IRIS o no cambian nada.", [
        request("Temporal PENDIENTE → EN_JUEGO → 200", "POST", TRANSICIONES_TEMPORAL, 200,
                sesion="sesionOperador", cuerpo={"nuevoEstado": "EN_JUEGO"}, claves=TRANSICION,
                pre=OMITIR_SIN_TEMPORAL, tests="""
const t = pm.response.json();
pm.test('PENDIENTE → EN_JUEGO con cambio', () => {
    pm.expect(t.estadoAnterior).to.eql('PENDIENTE');
    pm.expect(t.estadoActual).to.eql('EN_JUEGO');
    pm.expect(t.cambio).to.be.true;
});"""),
        request("Repetir EN_JUEGO → 200 cambio=false", "POST", TRANSICIONES_TEMPORAL, 200,
                sesion="sesionOperador", cuerpo={"nuevoEstado": "EN_JUEGO"}, claves=TRANSICION,
                pre=OMITIR_SIN_TEMPORAL,
                tests="pm.test('cambio=false', () => pm.expect(pm.response.json().cambio)"
                      ".to.be.false);"),
        request("Temporal EN_JUEGO → FINALIZADO → 200", "POST", TRANSICIONES_TEMPORAL, 200,
                sesion="sesionOperador", cuerpo={"nuevoEstado": "FINALIZADO"}, claves=TRANSICION,
                pre=OMITIR_SIN_TEMPORAL,
                tests="pm.test('FINALIZADO', () => pm.expect(pm.response.json().estadoActual)"
                      ".to.eql('FINALIZADO'));"),
        request("Reabrir el temporal → 409 y sigue FINALIZADO", "POST", TRANSICIONES_TEMPORAL, 409,
                sesion="sesionOperador", cuerpo={"nuevoEstado": "EN_JUEGO"},
                codigo="TRANSICION_NO_PERMITIDA", pre=OMITIR_SIN_TEMPORAL,
                tests="pm.test('detalles con el estado actual', () => pm.expect(pm.response.json()"
                      ".error.detalles[0].problema).to.include('FINALIZADO'));"),
        request("CU-18 del temporal → FINALIZADO", "GET", P + "/{{partidoTemporal}}/acta", 200,
                claves=ACTA, pre=OMITIR_SIN_TEMPORAL,
                tests="pm.test('estado FINALIZADO', () => pm.expect(pm.response.json().estado)"
                      ".to.eql('FINALIZADO'));"),
        request("nuevoEstado PENDIENTE → 400 (sin consultar IRIS)", "POST",
                P + "/{{partidoId}}/acta/transiciones", 400, sesion="sesionOperador",
                cuerpo={"nuevoEstado": "PENDIENTE"}, codigo="VALIDACION"),
        request("Lector → 403", "POST", P + "/{{partidoId}}/acta/transiciones", 403,
                sesion="sesionLector", cuerpo={"nuevoEstado": "EN_JUEGO"},
                codigo="ROL_NO_AUTORIZADO"),
        request("Sin X-Session-Id → 401", "POST", P + "/{{partidoId}}/acta/transiciones", 401,
                cuerpo={"nuevoEstado": "EN_JUEGO"}, codigo="SESION_REQUERIDA"),
        request("Partido sin acta PAR-002 → 404", "POST",
                P + "/{{partidoSinActa}}/acta/transiciones", 404, sesion="sesionOperador",
                cuerpo={"nuevoEstado": "EN_JUEGO"}, codigo="ACTA_NO_ENCONTRADA"),
    ]),
    carpeta("CU-13 · Cerrar la sesión", "Va al final porque cierra sesionLector: para volver a "
            "correr la colección, ejecutar otra vez scripts/crear_sesiones_prueba.ps1.", [
        request("Cerrar sesión lector → 204", "DELETE", S, 204, sesion="sesionLector"),
        request("Cerrar otra vez → 204 (idempotente)", "DELETE", S, 204, sesion="sesionLector"),
        request("CU-11 con la sesión cerrada → 401", "GET", S, 401, sesion="sesionLector",
                codigo="SESION_NO_VIGENTE"),
        request("Sin X-Session-Id → 401", "DELETE", S, 401, codigo="SESION_REQUERIDA"),
    ]),
]

DEPENDENCIA_CAIDA = """\
pm.test('503 o 504, nunca 200 vacío', () => pm.expect(pm.response.code).to.be.oneOf([503, 504]));
pm.test('DEPENDENCIA_NO_DISPONIBLE o DEPENDENCIA_TIMEOUT', () => pm.expect(
    pm.response.json().error.codigo).to.be.oneOf(['DEPENDENCIA_NO_DISPONIBLE', 'DEPENDENCIA_TIMEOUT']));"""


def caida(nombre: str, metodo: str, ruta: str, detener: str, **opciones) -> dict:
    item = request(nombre, metodo, ruta, 503, descripcion=f"Antes de enviar: {detener}",
                   **opciones)
    # El test de status de request() exige 503; acá también se acepta 504.
    item["event"][-1]["script"]["exec"] = js(DEPENDENCIA_CAIDA)
    return item


MANUAL = carpeta(CARPETA_MANUAL, "No la corre scripts/ejecutar_pruebas.ps1. Cada request indica "
                 "qué contenedor detener (docker compose stop en la carpeta del hito) y se vuelve "
                 "a levantar con docker compose start.", [
    caida("MongoDB detenido: CU-02 → 503/504", "GET", E + "?confederacion=UEFA",
          'docker compose -f "Hito 4/docker-compose.yml" stop'),
    request("Redis detenido: CU-01 → 200 X-Cache BYPASS", "GET", E + "/{{equipoId}}", 200,
            descripcion='Antes de enviar: docker compose -f "Hito 7/docker-compose.yml" stop',
            claves=FICHA_EQUIPO,
            tests="pm.test('X-Cache: BYPASS', () => "
                  "pm.expect(pm.response.headers.get('X-Cache')).to.eql('BYPASS'));"),
    caida("Redis detenido: CU-11 → 503 (nunca 401)", "GET", S,
          'docker compose -f "Hito 7/docker-compose.yml" stop', sesion="sesionLector"),
    caida("Neo4j detenido: CU-06 → 503/504", "GET", P + "/{{partidoId}}/eventos",
          'docker compose -f "Hito 5/docker-compose.yml" stop'),
    caida("Neo4j detenido al iniciar la API: CU-08 → 503 (catálogo no cargado)", "GET",
          P + "/{{partidoId}}/comentarios",
          'detener Neo4j (Hito 5) y reiniciar la API: el catálogo queda no_cargado'),
    caida("Cassandra detenido: CU-08 → 503/504", "GET",
          P + "/{{partidoId}}/comentarios?minuto=2030-06-10T18:01:00Z",
          'docker compose -f "Hito 6/docker-compose.yml" stop'),
    caida("InfluxDB detenido: CU-16 → 503/504", "GET",
          P + "/{{partidoId}}/estadisticas/comparacion?" + VENTANA,
          'docker compose -f "Hito 8/docker-compose.yml" stop'),
    caida("IRIS detenido: CU-18 → 503/504", "GET", P + "/{{partidoId}}/acta",
          'docker compose -f "Hito 9/docker-compose.yml" stop'),
])

DESCRIPCION = """\
Colección del Hito 10 (Grupo 13): por cada caso de uso de docs/casos_de_uso.md, la request \
exitosa y sus escenarios de error, con tests de código HTTP y estructura.

Preparación:
1. Levantar los contenedores de los Hitos 4 a 9 y la API (scripts/iniciar_api.ps1).
2. Ejecutar scripts/crear_sesiones_prueba.ps1 e importar el entorno \
.local/postman_entorno_local.json (contiene los IDs de sesión: no se versiona).
3. Opcional: crear un acta temporal para CU-19 (python -m tests.integracion.iris_temporal \
crear) y cargarla en la variable partidoTemporal; borrarla después con ... borrar PAR-9xx.

Efectos: CU-09 publica un comentario nuevo en partidoComentarios en cada ejecución; CU-20 lo \
oculta y lo restaura; CU-14 invalida la copia cacheada de EQ-001; CU-13 cierra sesionLector \
(volver a crear las sesiones para repetir). PAR-001 solo se lee.

scripts/ejecutar_pruebas.ps1 hace todo esto con newman. La carpeta \
"Dependencias caídas (manual)" no se ejecuta automáticamente.

Regenerar: python scripts/generar_coleccion_postman.py (no editar el JSON a mano)."""


def coleccion() -> dict:
    return {
        "info": {
            "_postman_id": "5d2c8a3e-1f4b-4c6e-9a7d-2030f1a13013",
            "name": "Fixture 2030 · API integrada (Hito 10)",
            "description": DESCRIPCION,
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": CARPETAS + [MANUAL],
        "event": [
            {"listen": "prerequest", "script": {"type": "text/javascript",
                                                "exec": js(PRE_COLECCION)}},
            {"listen": "test", "script": {"type": "text/javascript", "exec": js(TEST_COLECCION)}},
        ],
        "variable": [{"key": k, "value": v, "type": "string", "description": d}
                     for k, v, d in VARIABLES],
    }


def main() -> None:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with DESTINO.open("w", encoding="utf-8", newline="\n") as archivo:
        json.dump(coleccion(), archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")
    total = sum(len(c["item"]) for c in coleccion()["item"])
    print(f"Colección escrita en {DESTINO.relative_to(RAIZ)} ({total} requests)")


if __name__ == "__main__":
    main()
