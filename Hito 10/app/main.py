"""Aplicación FastAPI: ensambla rutas, servicios y adaptadores; middleware de correlación y errores."""

import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException

from app import config, contexto
from app.errors import ApiError, cuerpo_error
from app.routes import router
from app.services import Servicios

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # la traza propia ya registra cada operación
log = logging.getLogger("fixture2030")

VERSION = "1.0.0"
RID_VALIDO = re.compile(r"^[A-Za-z0-9-]{8,64}$")
GUI = config.RAIZ / "web" / "index.html"
ERROR_REF = {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorRespuesta"}}}
TAGS = [
    {"name": "Salud", "description": "Conectividad de las fuentes."},
    {"name": "Equipos · MongoDB", "description": "Hito 4. Documentos de equipos y jugadores; ficha cacheada en Redis (Hito 7)."},
    {"name": "Partidos · Neo4j", "description": "Hito 5. Recorridos parametrizados del grafo."},
    {"name": "Comentarios · Cassandra", "description": "Hito 6. Lectura por partición (partido, minuto, segmento)."},
    {"name": "Estadísticas · InfluxDB", "description": "Hito 8. Ventanas temporales agregadas."},
    {"name": "Sesiones · Redis", "description": "Hito 7. Sesiones con TTL e invalidación."},
    {"name": "Actas · IRIS", "description": "Hito 9. Objetos persistentes y transición de estado validada."},
]


def servicios_reales(cfg) -> Servicios:
    from app.adapters.cassandra_comentarios import CassandraComentarios
    from app.adapters.influx_estadisticas import InfluxEstadisticas
    from app.adapters.iris_actas import IrisActas
    from app.adapters.mongo_equipos import MongoEquipos
    from app.adapters.neo4j_partidos import Neo4jPartidos
    from app.adapters.redis_kv import RedisKV

    return Servicios(cfg, mongo=MongoEquipos(cfg), neo4j=Neo4jPartidos(cfg), cassandra=CassandraComentarios(cfg),
                     redis=RedisKV(cfg), influx=InfluxEstadisticas(cfg), iris=IrisActas(cfg))


def crear_app(servicios: Servicios | None = None) -> FastAPI:
    app = FastAPI(title="Fixture 2030 - API integrada (Grupo 13, Hito 10)", version=VERSION,
                  description="Acceso controlado a los módulos NoSQL del Fixture Mundial 2030. Datos sintéticos.")
    app.state.servicios = servicios or servicios_reales(config.cargar())
    app.include_router(router)

    @app.middleware("http")
    async def correlacion(request: Request, call_next):
        entrante = request.headers.get("X-Request-ID", "")
        rid = entrante if RID_VALIDO.match(entrante) else uuid.uuid4().hex
        contexto.request_id.set(rid)
        contexto.trazas.set([])
        inicio = time.perf_counter()
        try:
            respuesta = await call_next(request)
        except Exception as error:
            # El mensaje o traceback de un driver puede contener secretos.
            log.error("req=%s error_interno tipo=%s", rid, type(error).__name__)
            respuesta = JSONResponse(status_code=500, content=cuerpo_error(
                "ERROR_INTERNO", "Error interno. Informar el requestId para su diagnóstico.", rid))
        respuesta.headers["X-Request-ID"] = rid
        log.info("req=%s metodo=%s ruta=%s estado=%s ms=%.2f", rid, request.method, request.url.path,
                 respuesta.status_code, (time.perf_counter() - inicio) * 1000)
        return respuesta

    @app.exception_handler(ApiError)
    async def error_api(request: Request, error: ApiError):
        return JSONResponse(status_code=error.estado, content=cuerpo_error(
            error.codigo, error.mensaje, contexto.request_id.get(), detalles=error.detalles, dependencia=error.dependencia))

    @app.exception_handler(RequestValidationError)
    async def error_validacion(request: Request, error: RequestValidationError):
        # No se repite el valor recibido: solo ubicación y problema.
        detalles = [{"campo": ".".join(str(p) for p in e["loc"]), "problema": e["msg"]} for e in error.errors()]
        return JSONResponse(status_code=400, content=cuerpo_error(
            "VALIDACION_FALLIDA", "La solicitud no cumple el contrato.", contexto.request_id.get(), detalles=detalles))

    @app.exception_handler(HTTPException)
    async def error_http(request: Request, error: HTTPException):
        codigo = {404: "RUTA_NO_ENCONTRADA", 405: "METODO_NO_PERMITIDO"}.get(error.status_code, "ERROR_HTTP")
        return JSONResponse(status_code=error.status_code, content=cuerpo_error(
            codigo, str(error.detail), contexto.request_id.get()))

    @app.get("/", include_in_schema=False)
    def interfaz():
        return FileResponse(GUI)

    def openapi():
        if app.openapi_schema:
            return app.openapi_schema
        esquema = get_openapi(title=app.title, version=app.version, description=app.description,
                              routes=app.routes, tags=TAGS,
                              servers=[{"url": "http://127.0.0.1:8000", "description": "API local en la notebook"}])
        # FastAPI documenta 422 por defecto; esta API responde 400 con el formato de error común.
        for operaciones in esquema["paths"].values():
            for op in operaciones.values():
                respuestas = op["responses"]
                if respuestas.pop("422", None) is not None:
                    respuestas["400"] = {"description": "Validación fallida. No se consulta ninguna fuente.",
                                         "content": ERROR_REF}
                respuestas["500"] = {"description": "Error interno seguro; detalle solo en logs.", "content": ERROR_REF}
        for nombre in ("HTTPValidationError", "ValidationError"):
            esquema["components"]["schemas"].pop(nombre, None)
        app.openapi_schema = esquema
        return esquema

    app.openapi = openapi
    return app
