"""Rutas de comentarios sobre Cassandra (Hito 6): CU-08, CU-09, CU-10 y CU-20.

Orden en cada ruta: validación de la entrada (400, sin tocar ninguna base), sesión en
Redis (401/403/503), catálogo de partidos (404/503) y recién entonces Cassandra.
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Path, Query, status

from app.schemas.comentarios import (
    PATRON_COMENTARIO,
    PATRON_USUARIO,
    ComentarioCreado,
    ComentarioModerado,
    ComentariosPartido,
    HistorialUsuario,
    Moderacion,
    NuevoComentario,
)
from app.schemas.errores import CAIDA_O_CATALOGO, respuestas_error
from app.schemas.partidos import PATRON_PARTIDO, InstanteUTC
from app.services.comentarios import (
    ROL_MODERADOR,
    ServicioComentarios,
    cursor_valido,
    obtener_servicio_comentarios,
)
from app.services.sesiones import Autorizacion, sesion_requerida

router = APIRouter(prefix="/api/v1", tags=["comentarios"])

Servicio = Annotated[ServicioComentarios, Depends(obtener_servicio_comentarios)]
PartidoId = Annotated[str, Path(pattern=PATRON_PARTIDO, examples=["PAR-001"])]
DescripcionCursor = "Cursor creadoEn|comentarioId del último ítem recibido (siguienteCursor)."


@router.get(
    "/partidos/{partidoId}/comentarios",
    response_model=ComentariosPartido,
    summary="CU-08 · Leer comentarios de un partido",
    description="Modo minuto (`minuto`; `limite` 1–20), modo ventana (`desde` + `hasta`, como "
                "máximo 5 min; `limite` 1–50) o, sin ninguno de ellos, los últimos 60 segundos "
                "(`limite` 1–20). Orden creadoEn "
                "DESC, comentarioId ASC con límite global. X-Session-Id es opcional: sin sesión o "
                "sin rol moderador solo se devuelven comentarios visibles; con rol moderador, "
                "todos los estados. Partido fuera del catálogo → 404 sin consultar Cassandra.",
    responses=respuestas_error(400, 401, 404, 500, 503, 504, ejemplos={
        404: ["PARTIDO_NO_ENCONTRADO"], 503: CAIDA_O_CATALOGO}),
)
def leer_comentarios(
    partidoId: PartidoId,
    servicio: Servicio,
    auth: Annotated[Autorizacion, Depends(sesion_requerida())],
    minuto: Annotated[InstanteUTC | None, Query(examples=["2030-06-10T18:01:00Z"])] = None,
    desde: Annotated[InstanteUTC | None, Query(examples=["2030-06-10T18:00:30Z"])] = None,
    hasta: Annotated[InstanteUTC | None, Query(examples=["2030-06-10T18:02:10Z"])] = None,
    limite: Annotated[int | None, Query(ge=1, le=50)] = None,
    antesDe: Annotated[str | None, Query(max_length=120, description=DescripcionCursor)] = None,
) -> ComentariosPartido:
    lectura = servicio.preparar_lectura(minuto, desde, hasta, limite)
    cursor = cursor_valido(antesDe)
    sesion = auth.opcional()
    return servicio.leer_de_partido(partidoId, lectura, cursor, sesion)


@router.post(
    "/partidos/{partidoId}/comentarios",
    response_model=ComentarioCreado,
    status_code=status.HTTP_201_CREATED,
    summary="CU-09 · Publicar un comentario",
    description="Requiere sesión. Idempotente por Idempotency-Key (UUID, también es el "
                "comentarioId): repetir con la misma clave y el mismo body devuelve el mismo "
                "comentario sin duplicar filas; con otro body → 409. Nace con estado visible. "
                "504 = resultado incierto: reintentar con la misma clave.",
    responses=respuestas_error(400, 401, 404, 409, 500, 503, 504, ejemplos={
        404: ["PARTIDO_NO_ENCONTRADO"], 409: ["IDEMPOTENCY_KEY_REUTILIZADA"], 503: CAIDA_O_CATALOGO}),
)
def publicar_comentario(
    partidoId: PartidoId,
    servicio: Servicio,
    auth: Annotated[Autorizacion, Depends(sesion_requerida())],
    idempotencyKey: Annotated[UUID, Header(alias="Idempotency-Key")],
    cuerpo: Annotated[NuevoComentario, Body()],
) -> ComentarioCreado:
    sesion = auth.exigir()
    return servicio.publicar(partidoId, idempotencyKey, cuerpo.contenido, sesion)


@router.patch(
    "/partidos/{partidoId}/comentarios/{comentarioId}",
    response_model=ComentarioModerado,
    summary="CU-20 · Moderar un comentario",
    description="Requiere rol moderador. Lee primero la fila por clave primaria completa "
                "(creadoEn del body + comentarioId): si no existe → 404 sin escribir. Cambia "
                "estado en las dos tablas con un batch registrado. Si ya tenía el estado pedido "
                "→ 200 con cambio=false sin escribir.",
    responses=respuestas_error(400, 401, 403, 404, 500, 503, 504, ejemplos={
        404: ["PARTIDO_NO_ENCONTRADO", "COMENTARIO_NO_ENCONTRADO"], 503: CAIDA_O_CATALOGO}),
)
def moderar_comentario(
    partidoId: PartidoId,
    comentarioId: Annotated[str, Path(pattern=PATRON_COMENTARIO, examples=["MUESTRA-004"])],
    servicio: Servicio,
    auth: Annotated[Autorizacion, Depends(sesion_requerida(ROL_MODERADOR))],
    cuerpo: Annotated[Moderacion, Body()],
) -> ComentarioModerado:
    auth.exigir()
    return servicio.moderar(partidoId, comentarioId, cuerpo.creadoEn, cuerpo.estado.value)


@router.get(
    "/usuarios/{usuarioId}/comentarios",
    response_model=HistorialUsuario,
    summary="CU-10 · Ver historial diario de un autor",
    description="Requiere una sesión del propio autor o con rol moderador (si no → 403 sin "
                "renovar la sesión). Una sola partición (usuario_id, dia). Autor sin comentarios "
                "ese día → items vacío.",
    responses=respuestas_error(400, 401, 403, 500, 503, 504),
)
def historial_de_usuario(
    usuarioId: Annotated[str, Path(pattern=PATRON_USUARIO, examples=["USR-00001"])],
    dia: Annotated[date, Query(examples=["2030-06-10"], description="Día UTC (YYYY-MM-DD).")],
    servicio: Servicio,
    auth: Annotated[Autorizacion, Depends(sesion_requerida(ROL_MODERADOR))],
    limite: Annotated[int, Query(ge=1, le=20)] = 20,
    antesDe: Annotated[str | None, Query(max_length=120, description=DescripcionCursor)] = None,
) -> HistorialUsuario:
    cursor = cursor_valido(antesDe)
    auth.exigir_autor_o_rol(usuarioId)
    return servicio.historial(usuarioId, dia, cursor, limite)
