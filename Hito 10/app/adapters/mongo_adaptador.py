"""Adaptador de MongoDB (Hito 4): colecciones equipos y jugadores de fixture2030.

Encapsula el driver: crea el cliente con los timeouts de casos_de_uso.md §6.3,
ejecuta solo las consultas del catálogo del Hito 4 (Q01, Q02, Q03, Q06/Q07)
con proyección explícita, devuelve dicts sin _id ni campos de control y traduce
las excepciones de pymongo a las de app.errors. Nada de pymongo sale de acá.
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from pymongo import ASCENDING, MongoClient
from pymongo.errors import (
    ConnectionFailure,
    ExecutionTimeout,
    NetworkTimeout,
    PyMongoError,
)

from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio

DEPENDENCIA = "mongodb"

logger = logging.getLogger("app.adapters.mongo")

# Proyecciones fijas: excluyen _id, origen, esDatoSintetico, creadoEn, actualizadoEn.
PROY_FICHA_EQUIPO = {
    "_id": 0, "equipoId": 1, "codigo": 1, "nombre": 1, "confederacion": 1, "region": 1,
    "rankingReferencia": 1, "sedeBase": 1, "participacionesMundiales": 1,
    "titulosMundiales": 1, "estado": 1,
}
PROY_EQUIPO_RESUMEN = {"_id": 0, "equipoId": 1, "codigo": 1, "nombre": 1, "rankingReferencia": 1}
PROY_JUGADOR_PLANTEL = {
    "_id": 0, "jugadorId": 1, "nombre": 1, "apellido": 1, "posicion": 1,
    "numeroCamiseta": 1, "estadoPlantel": 1,
}
PROY_FICHA_JUGADOR = {
    "_id": 0, "jugadorId": 1, "equipoId": 1, "nombre": 1, "apellido": 1,
    "fechaNacimiento": 1, "nacionalidadCodigo": 1, "posicion": 1, "numeroCamiseta": 1,
    "pieHabil": 1, "alturaCm": 1, "partidosInternacionales": 1,
    "golesInternacionales": 1, "estadoPlantel": 1,
}

# Órdenes estables que coinciden con los índices del Hito 4.
ORDEN_EQUIPOS = [("rankingReferencia", ASCENDING), ("equipoId", ASCENDING)]
ORDEN_PLANTEL = [("apellido", ASCENDING), ("nombre", ASCENDING), ("jugadorId", ASCENDING)]


class AdaptadorMongo:
    def __init__(self, settings: Settings, cliente: MongoClient | None = None) -> None:
        # MongoClient conecta en segundo plano: la API arranca aunque MongoDB esté caído.
        self._cliente = cliente or MongoClient(
            host=settings.mongo_host,
            port=settings.mongo_port,
            username=settings.mongo_user,
            password=settings.mongo_password.get_secret_value(),
            authSource=settings.mongo_auth_db,
            serverSelectionTimeoutMS=int(settings.mongo_server_selection_timeout_s * 1000),
            connectTimeoutMS=int(settings.mongo_server_selection_timeout_s * 1000),
            socketTimeoutMS=int(settings.mongo_socket_timeout_s * 1000),
            appname="fixture2030-h10",
        )
        self._db = self._cliente[settings.mongo_db]

    def cerrar(self) -> None:
        self._cliente.close()

    @contextmanager
    def _traducir(self, operacion: str) -> Iterator[None]:
        """Traduce excepciones del driver y registra dependencia, resultado y duración."""
        inicio = time.perf_counter()
        resultado = "ok"
        try:
            yield
        except (NetworkTimeout, ExecutionTimeout) as exc:
            # NetworkTimeout hereda de ConnectionFailure: se evalúa antes.
            resultado = "DEPENDENCIA_TIMEOUT"
            raise DependenciaTimeout(DEPENDENCIA) from exc
        except ConnectionFailure as exc:
            # Incluye ServerSelectionTimeoutError y AutoReconnect.
            resultado = "DEPENDENCIA_NO_DISPONIBLE"
            raise DependenciaNoDisponible(DEPENDENCIA) from exc
        except PyMongoError as exc:
            # Autenticación u otra falla de configuración: 500 con el tipo solo en el log.
            resultado = f"ERROR_INTERNO tipo={type(exc).__name__}"
            raise ErrorDominio() from exc
        finally:
            duracion_ms = (time.perf_counter() - inicio) * 1000
            logger.info(
                "dependencia=%s operacion=%s resultado=%s duracion_ms=%.1f",
                DEPENDENCIA, operacion, resultado, duracion_ms,
            )

    # Q01 · índice uq_equipos_equipoId
    def obtener_equipo(self, equipo_id: str) -> dict | None:
        with self._traducir("obtener_equipo"):
            return self._db.equipos.find_one({"equipoId": equipo_id}, PROY_FICHA_EQUIPO)

    def existe_equipo(self, equipo_id: str) -> bool:
        with self._traducir("existe_equipo"):
            return self._db.equipos.find_one({"equipoId": equipo_id}, {"_id": 1}) is not None

    # Q03 · índice idx_equipos_confederacion_ranking
    def listar_equipos(
        self, confederacion: str, ranking_max: int | None, pagina: int, limite: int
    ) -> tuple[list[dict], int]:
        filtro: dict = {"confederacion": confederacion}
        if ranking_max is not None:
            filtro["rankingReferencia"] = {"$lte": ranking_max}
        with self._traducir("listar_equipos"):
            cursor = (
                self._db.equipos.find(filtro, PROY_EQUIPO_RESUMEN)
                .sort(ORDEN_EQUIPOS).skip((pagina - 1) * limite).limit(limite)
            )
            items = list(cursor)
            total = self._db.equipos.count_documents(filtro)
        return items, total

    # Q06/Q07 · índice idx_jugadores_equipo_nombre
    def listar_jugadores_de_equipo(
        self, equipo_id: str, posicion: str | None, pagina: int, limite: int
    ) -> tuple[list[dict], int]:
        filtro: dict = {"equipoId": equipo_id}
        if posicion is not None:
            filtro["posicion"] = posicion
        with self._traducir("listar_jugadores_de_equipo"):
            cursor = (
                self._db.jugadores.find(filtro, PROY_JUGADOR_PLANTEL)
                .sort(ORDEN_PLANTEL).skip((pagina - 1) * limite).limit(limite)
            )
            items = list(cursor)
            total = self._db.jugadores.count_documents(filtro)
        return items, total

    # Q02 · índice uq_jugadores_jugadorId
    def obtener_jugador(self, jugador_id: str) -> dict | None:
        with self._traducir("obtener_jugador"):
            jugador = self._db.jugadores.find_one({"jugadorId": jugador_id}, PROY_FICHA_JUGADOR)
        if jugador and isinstance(jugador.get("fechaNacimiento"), datetime):
            # El seed guarda la fecha a medianoche UTC: se expone como fecha ISO-8601.
            jugador["fechaNacimiento"] = jugador["fechaNacimiento"].date()
        return jugador

    def ping(self) -> bool:
        """Chequeo de salud: True si MongoDB responde. Nunca lanza."""
        try:
            with self._traducir("ping"):
                self._cliente.admin.command("ping")
            return True
        except ErrorDominio:
            return False
