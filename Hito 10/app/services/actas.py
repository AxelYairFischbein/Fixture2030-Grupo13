"""Casos de uso del acta del partido sobre IRIS (Hito 9): CU-18 y CU-19.

IRIS es la única fuente autoritativa del estado del partido (casos_de_uso.md §3.1):
la transición se escribe solo ahí, con CambiarEstado(), y nunca en Neo4j.
"""

from typing import Annotated, Protocol

from fastapi import Depends

from app.dependencias import obtener_adaptador_iris
from app.errors import Conflicto, ErrorDominio, NoEncontrado
from app.schemas.actas import (
    ActaPartido,
    ArbitroActa,
    EventoActa,
    ResultadoTransicion,
)


class RepositorioActas(Protocol):
    def leer_acta(self, partido_id: str) -> dict | None: ...
    def transicionar(self, partido_id: str, nuevo_estado: str) -> dict: ...


def acta_no_encontrada(partido_id: str) -> NoEncontrado:
    return NoEncontrado(
        "ACTA_NO_ENCONTRADA",
        "No existe un acta para el partido indicado.",
        [{"campo": "partidoId", "problema": f"{partido_id} no tiene acta"}],
    )


class ServicioActas:
    def __init__(self, repositorio: RepositorioActas) -> None:
        self._repo = repositorio

    def ver_acta(self, partido_id: str) -> ActaPartido:
        """CU-18. None del adaptador = sin Partido en IRIS (404), aunque exista en Neo4j."""
        acta = self._repo.leer_acta(partido_id)
        if acta is None:
            raise acta_no_encontrada(partido_id)
        return ActaPartido(
            partidoId=acta["partidoId"], estadioId=acta["estadioId"], estado=acta["estado"],
            arbitro=ArbitroActa(**acta["arbitro"]),
            eventos=[EventoActa(**e) for e in acta["eventos"]],
        )

    def transicionar(self, partido_id: str, nuevo_estado: str) -> ResultadoTransicion:
        """CU-19. Idempotente: si el estado ya es el pedido responde cambio=false sin
        llamar a CambiarEstado (lo decide IRIS bajo el bloqueo del partido)."""
        r = self._repo.transicionar(partido_id, nuevo_estado)
        if r["resultado"] == "NO_ENCONTRADO":
            raise acta_no_encontrada(partido_id)
        if r["resultado"] == "TRANSICION_NO_PERMITIDA":
            raise Conflicto(
                "TRANSICION_NO_PERMITIDA",
                "El estado actual del partido no admite la transición pedida.",
                [{"campo": "nuevoEstado",
                  "problema": f"no se permite {r['actual']} -> {nuevo_estado}; "
                              f"estado actual {r['actual']}"}],
            )
        if r["resultado"] not in ("OK", "SIN_CAMBIO"):
            raise ErrorDominio()
        return ResultadoTransicion(
            partidoId=partido_id, estadoAnterior=r["anterior"], estadoActual=r["actual"],
            cambio=r["resultado"] == "OK",
        )


def obtener_servicio_actas(
    repositorio: Annotated[RepositorioActas, Depends(obtener_adaptador_iris)],
) -> ServicioActas:
    return ServicioActas(repositorio)
