"""Adaptador documental (Hito 4): colecciones equipos y jugadores de MongoDB."""

from datetime import datetime, timezone

from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError

from app.contexto import operacion

ERRORES = (PyMongoError,)

# Proyecciones explícitas: no se publican _id, origen ni marcas internas del documento.
PROY_EQUIPO = {"_id": 0, "equipoId": 1, "codigo": 1, "nombre": 1, "confederacion": 1, "region": 1,
               "rankingReferencia": 1, "sedeBase": 1, "participacionesMundiales": 1,
               "titulosMundiales": 1, "estado": 1, "actualizadoEn": 1}
PROY_EQUIPO_RESUMEN = {"_id": 0, "equipoId": 1, "codigo": 1, "nombre": 1, "confederacion": 1,
                       "rankingReferencia": 1, "estado": 1}
PROY_JUGADOR = {"_id": 0, "jugadorId": 1, "equipoId": 1, "nombre": 1, "apellido": 1, "posicion": 1,
                "numeroCamiseta": 1, "fechaNacimiento": 1, "alturaCm": 1, "pieHabil": 1,
                "partidosInternacionales": 1, "golesInternacionales": 1, "estadoPlantel": 1}


def _fechas_iso(doc: dict) -> dict:
    for clave, valor in doc.items():
        if isinstance(valor, datetime):
            doc[clave] = valor.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return doc


class MongoEquipos:
    nombre = "mongodb"

    def __init__(self, cfg):
        self._cliente = MongoClient(
            host=cfg.mongo_host, port=cfg.mongo_port, username=cfg.mongo_user or None,
            password=cfg.mongo_password or None, authSource="admin",
            serverSelectionTimeoutMS=int(cfg.timeout * 1000), connectTimeoutMS=int(cfg.timeout * 1000),
            socketTimeoutMS=int(cfg.timeout * 1000), appname="fixture2030-api-h10",
        )  # Conexión perezosa: la API inicia aunque MongoDB esté detenido.
        self._db = self._cliente[cfg.mongo_db]

    def ping(self):
        with operacion(self.nombre, "ping", ERRORES):
            self._db.command("ping")

    def listar_equipos(self, confederacion: str | None, salto: int, limite: int) -> tuple[list[dict], int]:
        filtro = {"confederacion": confederacion} if confederacion else {}
        with operacion(self.nombre, "listar_equipos", ERRORES):
            # Índice idx_equipos_confederacion_ranking: filtro + orden estable.
            cursor = (self._db.equipos.find(filtro, PROY_EQUIPO_RESUMEN)
                      .sort([("rankingReferencia", ASCENDING), ("equipoId", ASCENDING)])
                      .skip(salto).limit(limite))
            items = list(cursor)
            total = self._db.equipos.count_documents(filtro)
        return items, total

    def buscar_equipo(self, equipo_id: str) -> dict | None:
        with operacion(self.nombre, "buscar_equipo", ERRORES):
            doc = self._db.equipos.find_one({"equipoId": equipo_id}, PROY_EQUIPO)  # uq_equipos_equipoId
        return _fechas_iso(doc) if doc else None

    def existe_equipo(self, equipo_id: str) -> bool:
        with operacion(self.nombre, "existe_equipo", ERRORES):
            return self._db.equipos.count_documents({"equipoId": equipo_id}, limit=1) == 1

    def plantel(self, equipo_id: str, posicion: str | None, salto: int, limite: int) -> tuple[list[dict], int]:
        filtro = {"equipoId": equipo_id}
        if posicion:
            filtro["posicion"] = posicion
        with operacion(self.nombre, "plantel", ERRORES):
            # Índice uq_jugadores_equipo_camiseta: plantel ordenado por camiseta.
            cursor = (self._db.jugadores.find(filtro, PROY_JUGADOR)
                      .sort([("numeroCamiseta", ASCENDING)]).skip(salto).limit(limite))
            items = [_fechas_iso(d) for d in cursor]
            total = self._db.jugadores.count_documents(filtro)
        return items, total
