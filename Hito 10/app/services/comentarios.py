"""Casos de uso de comentarios sobre Cassandra (Hito 6): CU-08, CU-09, CU-10 y CU-20.

El partido se valida contra el catálogo en memoria (casos_de_uso.md §3.2) antes de tocar
Cassandra: 404 si no existe, 503 si el catálogo no pudo cargarse. La sesión se valida en
Redis (Hito 7) y la idempotencia de CU-09 usa un registro en Redis con SET NX EX.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends

from app.dependencias import (
    obtener_adaptador_cassandra,
    obtener_adaptador_redis,
    obtener_catalogo_partidos,
)
from app.errors import Conflicto, DependenciaTimeout, NoEncontrado, ValidacionInvalida
from app.schemas.comentarios import (
    ComentarioCreado,
    ComentarioModerado,
    ComentarioPartido,
    ComentariosPartido,
    ComentarioUsuario,
    Cursor,
    HistorialUsuario,
    iso_ms,
    parsear_cursor,
)
from app.services.sesiones import Sesion

VENTANA_MAXIMA = timedelta(minutes=5)
VENTANA_POR_DEFECTO = timedelta(seconds=60)
UN_MINUTO = timedelta(minutes=1)
LIMITE_MINUTO = 20
LIMITE_VENTANA = 50
ESTADO_VISIBLE = "visible"
ROL_MODERADOR = "moderador"

MENSAJE_RESULTADO_INCIERTO = (
    "Cassandra no confirmó la escritura a tiempo: el resultado es incierto. "
    "Reintente con la misma Idempotency-Key."
)
MENSAJE_MODERACION_INCIERTA = (
    "Cassandra no confirmó la moderación a tiempo: el resultado es incierto. "
    "Reintente la misma solicitud."
)


class RepositorioComentarios(Protocol):
    def leer_por_partido(self, partido_id: str, desde: datetime, hasta: datetime, antes_de: tuple[datetime, str] | None, limite: int,
                         solo_visibles: bool) -> tuple[list[dict], tuple[datetime, str] | None]: ...
    def leer_por_usuario(self, usuario_id: str, dia: date, antes_de: tuple[datetime, str] | None,
                         limite: int) -> tuple[list[dict], tuple[datetime, str] | None]: ...
    def leer_comentario(self, partido_id: str, creado_en: datetime,
                        comentario_id: str) -> dict | None: ...
    def insertar_comentario(self, comentario: dict) -> None: ...
    def actualizar_estado(self, fila: dict, estado: str) -> None: ...


class RegistroIdempotencia(Protocol):
    def reservar_idempotencia(self, clave: str, registro: dict) -> dict | None: ...


class Catalogo(Protocol):
    def validar_partido(self, partido_id: str) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class LecturaPartido:
    """Parámetros de CU-08 ya validados: intervalo [desde, hasta) y límite."""

    desde: datetime
    hasta: datetime
    limite: int


def _minuto_de(instante: datetime) -> datetime:
    return instante.astimezone(UTC).replace(second=0, microsecond=0)


def _truncar_a_ms(instante: datetime) -> datetime:
    return instante.replace(microsecond=instante.microsecond // 1000 * 1000)


def _invalido(campo: str, problema: str) -> ValidacionInvalida:
    return ValidacionInvalida(detalles=[{"campo": campo, "problema": problema}])


def cursor_valido(texto: str | None) -> Cursor | None:
    """Cursor antesDe "creadoEn|comentarioId" o 400 antes de consultar."""
    try:
        return parsear_cursor(texto)
    except ValueError as exc:
        raise _invalido("antesDe", str(exc)) from None


def _cursor_a_tupla(cursor: Cursor | None) -> tuple[datetime, str] | None:
    return (cursor.creado_en, cursor.comentario_id) if cursor else None


def _cursor_texto(siguiente: tuple[datetime, str] | None) -> str | None:
    return Cursor(*siguiente).texto() if siguiente else None


def huella(partido_id: str, usuario_id: str, contenido: str) -> str:
    """Huella de idempotencia de CU-09: misma ruta, mismo autor y mismo contenido."""
    datos = json.dumps([partido_id, usuario_id, contenido], ensure_ascii=False)
    return hashlib.sha256(datos.encode("utf-8")).hexdigest()


class ServicioComentarios:
    def __init__(self, repositorio: RepositorioComentarios, idempotencia: RegistroIdempotencia,
                 catalogo: Catalogo,
                 reloj: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._repo = repositorio
        self._idempotencia = idempotencia
        self._catalogo = catalogo
        self._reloj = reloj

    # CU-08

    def preparar_lectura(self, minuto: datetime | None, desde: datetime | None,
                         hasta: datetime | None, limite: int | None) -> LecturaPartido:
        """Valida el modo (minuto o ventana) antes de consultar Redis, el catálogo o Cassandra."""
        if minuto is not None and (desde is not None or hasta is not None):
            raise _invalido("minuto", "no se combina con desde/hasta: elegir un modo")
        if desde is not None or hasta is not None:
            if desde is None or hasta is None:
                raise _invalido("desde" if desde is None else "hasta",
                                "el modo ventana requiere desde y hasta")
            if desde >= hasta:
                raise _invalido("hasta", "debe ser posterior a desde")
            if hasta - desde > VENTANA_MAXIMA:
                raise _invalido("hasta", "la ventana no puede superar 5 minutos")
            return LecturaPartido(desde, hasta, LIMITE_VENTANA if limite is None else limite)
        if limite is not None and limite > LIMITE_MINUTO:
            raise _invalido("limite", f"en modo minuto y por defecto el máximo es {LIMITE_MINUTO}")
        limite = LIMITE_MINUTO if limite is None else limite
        if minuto is None:
            # Modo por defecto: últimos 60 s (como máximo 2 minutos, 8 particiones).
            ahora = self._reloj().astimezone(UTC)
            return LecturaPartido(ahora - VENTANA_POR_DEFECTO, ahora, limite)
        inicio = _minuto_de(minuto)
        return LecturaPartido(inicio, inicio + UN_MINUTO, limite)

    def leer_de_partido(self, partido_id: str, lectura: LecturaPartido, antes_de: Cursor | None,
                        sesion: Sesion | None) -> ComentariosPartido:
        """CU-08. APP (sin sesión o sin rol moderador) solo ve comentarios visibles."""
        self._catalogo.validar_partido(partido_id)
        solo_visibles = sesion is None or sesion.rol != ROL_MODERADOR
        filas, siguiente = self._repo.leer_por_partido(
            partido_id, lectura.desde, lectura.hasta,
            _cursor_a_tupla(antes_de), lectura.limite, solo_visibles,
        )
        return ComentariosPartido(
            partidoId=partido_id,
            items=[ComentarioPartido(
                comentarioId=f["comentario_id"], usuarioId=f["usuario_id"], creadoEn=f["creado_en"],
                contenido=f["contenido"], estado=f["estado"], likes=f["likes"],
            ) for f in filas],
            siguienteCursor=_cursor_texto(siguiente),
        )

    # CU-09

    def publicar(self, partido_id: str, clave: UUID, contenido: str,
                 sesion: Sesion) -> ComentarioCreado:
        """Creación idempotente: comentario_id = Idempotency-Key; reintento = mismo creado_en."""
        # 404 o 503 sin consumir la Idempotency-Key.
        self._catalogo.validar_partido(partido_id)
        comentario_id = str(clave)
        firma = huella(partido_id, sesion.usuario_id, contenido)
        creado_en = _truncar_a_ms(self._reloj().astimezone(UTC))

        previo = self._idempotencia.reservar_idempotencia(
            comentario_id, {"huella": firma, "creadoEn": iso_ms(creado_en)})
        if previo is not None:
            if previo.get("huella") != firma:
                raise Conflicto(
                    "IDEMPOTENCY_KEY_REUTILIZADA",
                    "La Idempotency-Key ya se usó con otro contenido.",
                    [{"campo": "Idempotency-Key", "problema": "ya se usó con otro body, partido o autor"}],
                )
            creado_en = datetime.fromisoformat(previo["creadoEn"])
            existente = self._repo.leer_comentario(partido_id, creado_en, comentario_id)
            if existente is not None:
                # Se devuelve tal cual: reescribirla desharía una moderación posterior (CU-20).
                return self._creado(existente)

        # minuto, segmento y dia los deriva el adaptador (modelo físico del Hito 6).
        fila = {
            "partido_id": partido_id, "creado_en": creado_en, "comentario_id": comentario_id,
            "usuario_id": sesion.usuario_id, "contenido": contenido,
            "estado": ESTADO_VISIBLE, "likes": 0,
        }
        try:
            self._repo.insertar_comentario(fila)
        except DependenciaTimeout as exc:
            raise DependenciaTimeout(exc.dependencia, MENSAJE_RESULTADO_INCIERTO) from exc
        return self._creado(fila)

    @staticmethod
    def _creado(fila: dict) -> ComentarioCreado:
        return ComentarioCreado(
            comentarioId=fila["comentario_id"], partidoId=fila["partido_id"],
            usuarioId=fila["usuario_id"], creadoEn=fila["creado_en"], contenido=fila["contenido"],
            estado=fila["estado"], likes=fila["likes"],
        )

    # CU-10

    def historial(self, usuario_id: str, dia: date, antes_de: Cursor | None,
                  limite: int) -> HistorialUsuario:
        filas, siguiente = self._repo.leer_por_usuario(
            usuario_id, dia, _cursor_a_tupla(antes_de), limite)
        return HistorialUsuario(
            usuarioId=usuario_id, dia=dia,
            items=[ComentarioUsuario(
                comentarioId=f["comentario_id"], partidoId=f["partido_id"], creadoEn=f["creado_en"],
                contenido=f["contenido"], estado=f["estado"], likes=f["likes"],
            ) for f in filas],
            siguienteCursor=_cursor_texto(siguiente),
        )

    # CU-20

    def moderar(self, partido_id: str, comentario_id: str, creado_en: datetime,
                estado: str) -> ComentarioModerado:
        """Lectura previa obligatoria: un UPDATE sobre una clave inexistente crearía la fila."""
        self._catalogo.validar_partido(partido_id)
        fila = self._repo.leer_comentario(partido_id, creado_en, comentario_id)
        if fila is None:
            raise NoEncontrado(
                "COMENTARIO_NO_ENCONTRADO",
                "No existe un comentario con esa clave en el partido indicado.",
                [{"campo": "comentarioId", "problema": f"{comentario_id} no existe con ese creadoEn"}],
            )
        anterior = fila["estado"]
        cambio = anterior != estado
        if cambio:
            try:
                self._repo.actualizar_estado(fila, estado)
            except DependenciaTimeout as exc:
                raise DependenciaTimeout(exc.dependencia, MENSAJE_MODERACION_INCIERTA) from exc
        return ComentarioModerado(
            comentarioId=comentario_id, partidoId=partido_id, usuarioId=fila["usuario_id"],
            creadoEn=fila["creado_en"], estadoAnterior=anterior, estado=estado, cambio=cambio,
        )


def obtener_servicio_comentarios(
    repositorio: Annotated[RepositorioComentarios, Depends(obtener_adaptador_cassandra)],
    idempotencia: Annotated[RegistroIdempotencia, Depends(obtener_adaptador_redis)],
    catalogo: Annotated[Catalogo, Depends(obtener_catalogo_partidos)],
) -> ServicioComentarios:
    return ServicioComentarios(repositorio, idempotencia, catalogo)
