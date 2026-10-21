"""Rutas HTTP: contrato, validación de entrada y armado de la respuesta. Sin lógica de acceso a datos."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request, Response
from fastapi.responses import JSONResponse

from app import contexto
from app import schemas as s
from app.errors import cuerpo_error

router = APIRouter(prefix="/api/v1")

DESCRIPCION_ERRORES = {
    404: "Recurso inexistente (o sesión no vigente).",
    409: "Conflicto con el estado actual del recurso.",
    503: "Dependencia no disponible o sin respuesta dentro del timeout. Nunca se devuelve 200 vacío.",
}


def errores(*codigos: int) -> dict:
    return {c: {"model": s.ErrorRespuesta, "description": DESCRIPCION_ERRORES[c]} for c in codigos}


def ok(data, **meta) -> dict:
    return {"data": data, "meta": {"requestId": contexto.request_id.get(),
                                   "fuentes": contexto.trazas.get() or [], **meta}}


def srv(request: Request):
    return request.app.state.servicios


EquipoId = Annotated[str, Path(pattern=s.EQUIPO_ID, examples=["EQ-001"])]
PartidoId = Annotated[str, Path(pattern=s.PARTIDO_ID, examples=["PAR-001"])]
SesionId = Annotated[str, Path(pattern=s.SESION_ID)]
CodigoActa = Annotated[str, Path(pattern=s.ACTA_CODIGO, examples=["PAR-001"])]
Pagina = Annotated[int, Query(ge=1, le=1000)]
Tamanio = Annotated[int, Query(ge=1, le=50)]


# --- Salud -------------------------------------------------------------------------------
@router.get("/salud", tags=["Salud"], summary="Conectividad de las seis fuentes",
            response_model=s.Respuesta[list[s.EstadoFuente]],
            responses={503: {"model": s.ErrorRespuesta, "description": "Al menos una fuente no responde; "
                             "`detalles` informa el estado de cada una."}})
def salud(request: Request):
    estados = srv(request).salud()
    if any(e["estado"] != "ok" for e in estados):
        return JSONResponse(status_code=503, content=cuerpo_error(
            "DEPENDENCIA_NO_DISPONIBLE", "Una o más fuentes no están disponibles.",
            contexto.request_id.get(), detalles=estados))
    return ok(estados)


# --- Equipos (MongoDB + caché Redis) ---------------------------------------------------------
@router.get("/equipos", tags=["Equipos · MongoDB"], summary="Listado paginado de equipos",
            response_model=s.Respuesta[list[s.EquipoResumen]], responses=errores(503))
def listar_equipos(request: Request, confederacion: s.Confederacion | None = None,
                   pagina: Pagina = 1, tamanio: Tamanio = 16):
    conf = confederacion.value if confederacion else None
    items, total = srv(request).listar_equipos(conf, pagina, tamanio)
    return ok(items, paginacion={"pagina": pagina, "tamanio": tamanio, "total": total})


@router.get("/equipos/{equipoId}", tags=["Equipos · MongoDB"], summary="Ficha de un equipo (cache-aside en Redis)",
            response_model=s.Respuesta[s.Equipo], responses=errores(404, 503))
def obtener_equipo(request: Request, response: Response, equipoId: EquipoId):
    equipo, cache = srv(request).obtener_equipo(equipoId)
    response.headers["X-Cache"] = cache
    return ok(equipo, cache=cache)


@router.delete("/equipos/{equipoId}/cache", tags=["Equipos · MongoDB"], status_code=204,
               summary="Invalidar la ficha en caché (idempotente)", responses=errores(503))
def invalidar_equipo(request: Request, equipoId: EquipoId):
    srv(request).invalidar_equipo(equipoId)
    return Response(status_code=204)


@router.get("/equipos/{equipoId}/jugadores", tags=["Equipos · MongoDB"], summary="Plantel paginado por camiseta",
            response_model=s.Respuesta[list[s.Jugador]], responses=errores(404, 503))
def plantel(request: Request, equipoId: EquipoId, posicion: s.Posicion | None = None,
            pagina: Pagina = 1, tamanio: Tamanio = 24):
    items, total = srv(request).plantel(equipoId, posicion.value if posicion else None, pagina, tamanio)
    return ok(items, paginacion={"pagina": pagina, "tamanio": tamanio, "total": total})


# --- Partidos (Neo4j) -------------------------------------------------------------------------
@router.get("/equipos/{equipoId}/partidos", tags=["Partidos · Neo4j"], summary="Agenda del equipo con rival y estadio",
            response_model=s.Respuesta[list[s.PartidoAgenda]], responses=errores(404, 503))
def agenda(request: Request, equipoId: EquipoId, limite: Annotated[int, Query(ge=1, le=20)] = 10):
    return ok(srv(request).agenda(equipoId, limite))


@router.get("/partidos/{partidoId}", tags=["Partidos · Neo4j"], summary="Partido con equipos, estadio y eventos",
            response_model=s.Respuesta[s.Partido], responses=errores(404, 503))
def partido(request: Request, partidoId: PartidoId, limiteEventos: Annotated[int, Query(ge=1, le=50)] = 20):
    return ok(srv(request).partido(partidoId, limiteEventos))


# --- Comentarios (Cassandra) -------------------------------------------------------------------
@router.get("/partidos/{partidoId}/comentarios", tags=["Comentarios · Cassandra"],
            summary="Comentarios de una ventana de hasta 5 minutos, con cursor",
            response_model=s.Respuesta[s.VentanaComentarios], responses=errores(503))
def comentarios(request: Request, partidoId: PartidoId,
                desde: Annotated[datetime, Query(examples=["2030-06-10T18:00:00Z"])],
                hasta: Annotated[datetime, Query(examples=["2030-06-10T18:03:00Z"])],
                limite: Annotated[int, Query(ge=1, le=50)] = 20,
                cursor: Annotated[str | None, Query(pattern=s.CURSOR)] = None):
    datos, siguiente = srv(request).comentarios(partidoId, desde, hasta, limite, cursor)
    return ok(datos, paginacion={"tamanio": limite, "siguienteCursor": siguiente})


@router.post("/partidos/{partidoId}/comentarios", tags=["Comentarios · Cassandra"], status_code=201,
             summary="Publicar un comentario (requiere Idempotency-Key)",
             response_model=s.Respuesta[s.ComentarioCreado],
             responses={200: {"model": s.Respuesta[s.ComentarioCreado],
                              "description": "Repetición con la misma Idempotency-Key: devuelve el comentario "
                                             "original sin crear otra fila (Idempotent-Replayed: true)."},
                        **errores(404, 409, 503)})
def crear_comentario(request: Request, response: Response, partidoId: PartidoId, cuerpo: s.ComentarioNuevo,
                     idempotency_key: Annotated[str, Header(alias="Idempotency-Key", pattern=s.IDEMPOTENCY_KEY)]):
    comentario, repetido = srv(request).crear_comentario(partidoId, cuerpo.usuarioId, cuerpo.contenido.strip(),
                                                         idempotency_key)
    if repetido:
        response.status_code = 200
        response.headers["Idempotent-Replayed"] = "true"
    return ok(comentario)


# --- Estadísticas (InfluxDB) -------------------------------------------------------------------
@router.get("/partidos/{partidoId}/estadisticas", tags=["Estadísticas · InfluxDB"],
            summary="Resumen temporal por intervalo (ventana acotada)",
            description="Sin `desde`/`hasta` devuelve los últimos 10 minutos con datos del partido. "
                        "Máximo 720 intervalos por equipo.",
            response_model=s.Respuesta[s.Estadisticas], responses=errores(503))
def estadisticas(request: Request, partidoId: PartidoId,
                 equipoId: Annotated[str | None, Query(pattern=s.EQUIPO_ID)] = None,
                 desde: datetime | None = None, hasta: datetime | None = None,
                 intervalo: s.Intervalo = s.Intervalo.m1):
    return ok(srv(request).estadisticas(partidoId, equipoId, desde, hasta, intervalo.value))


# --- Sesiones (Redis) ----------------------------------------------------------------------------
@router.post("/sesiones", tags=["Sesiones · Redis"], status_code=201, summary="Abrir una sesión con TTL",
             response_model=s.Respuesta[s.Sesion], responses=errores(503))
def crear_sesion(request: Request, cuerpo: s.SesionNueva):
    return ok(srv(request).crear_sesion(cuerpo.usuarioId, cuerpo.rol))


@router.get("/sesiones/{sesionId}", tags=["Sesiones · Redis"], summary="Consultar una sesión vigente",
            response_model=s.Respuesta[s.Sesion], responses=errores(404, 503))
def obtener_sesion(request: Request, sesionId: SesionId):
    return ok(srv(request).obtener_sesion(sesionId))


@router.delete("/sesiones/{sesionId}", tags=["Sesiones · Redis"], status_code=204,
               summary="Cerrar (invalidar) una sesión; idempotente", responses=errores(503))
def cerrar_sesion(request: Request, sesionId: SesionId):
    srv(request).cerrar_sesion(sesionId)
    return Response(status_code=204)


# --- Actas (IRIS) -----------------------------------------------------------------------------
@router.get("/actas/{codigo}", tags=["Actas · IRIS"], summary="Acta del partido: árbitro, estado y eventos",
            response_model=s.Respuesta[s.Acta], responses=errores(404, 503))
def acta(request: Request, codigo: CodigoActa):
    return ok(srv(request).acta(codigo))


@router.put("/actas/{codigo}/estado", tags=["Actas · IRIS"], summary="Transición de estado validada por el dominio",
            description="PENDIENTE -> EN_JUEGO -> FINALIZADO. Pedir el estado actual responde `cambio: false`.",
            response_model=s.Respuesta[s.ActaCambio], responses=errores(404, 409, 503))
def cambiar_estado(request: Request, codigo: CodigoActa, cuerpo: s.CambioEstado):
    cambio, acta_actual = srv(request).cambiar_estado_acta(codigo, cuerpo.estado.value)
    return ok({"cambio": cambio, "acta": acta_actual})
