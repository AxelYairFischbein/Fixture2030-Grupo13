"""Adaptadores falsos en memoria para las pruebas unitarias (sin Docker)."""

from datetime import datetime, timezone


def _equipo(numero: int, confederacion: str, ranking: int) -> dict:
    return {
        "equipoId": f"EQ-{numero:03d}", "codigo": f"S{numero:02d}",
        "nombre": f"Seleccion Sintetica {numero:02d}", "confederacion": confederacion,
        "region": "AMERICAS", "rankingReferencia": ranking,
        "sedeBase": {"ciudad": f"Ciudad {numero:02d}", "pais": f"Pais {numero:02d}"},
        "participacionesMundiales": 3, "titulosMundiales": 0, "estado": "PRESELECCIONADO",
    }


def _jugador(numero: int, equipo_id: str, posicion: str, apellido: str) -> dict:
    return {
        "jugadorId": f"JUG-{numero:04d}", "equipoId": equipo_id,
        "nombre": f"Nombre{numero:04d}", "apellido": apellido,
        "fechaNacimiento": datetime(1998, 3, 12, tzinfo=timezone.utc).date(),
        "nacionalidadCodigo": "S01", "posicion": posicion, "numeroCamiseta": numero,
        "pieHabil": "DERECHO", "alturaCm": 180, "partidosInternacionales": 10,
        "golesInternacionales": 1, "estadoPlantel": "CONVOCADO",
    }


PLANTEL = ("jugadorId", "nombre", "apellido", "posicion", "numeroCamiseta", "estadoPlantel")
RESUMEN = ("equipoId", "codigo", "nombre", "rankingReferencia")


class MongoFalso:
    """Imita el contrato de AdaptadorMongo. EQ-003 existe y no tiene jugadores.

    `falla` es una excepción que lanza cualquier consulta (dependencia caída);
    `llamadas` registra cada consulta para verificar que un 400 no tocó la base.
    """

    def __init__(self) -> None:
        self.equipos = [
            _equipo(1, "CONMEBOL", 10), _equipo(2, "CONMEBOL", 4), _equipo(3, "UEFA", 7),
        ]
        self.jugadores = [
            _jugador(1, "EQ-001", "ARQUERO", "Zeta"),
            _jugador(2, "EQ-001", "DEFENSOR", "Alfa"),
            _jugador(3, "EQ-001", "DELANTERO", "Alfa"),
            _jugador(4, "EQ-002", "ARQUERO", "Beta"),
        ]
        self.falla: Exception | None = None
        self.llamadas: list[str] = []

    def _registrar(self, operacion: str) -> None:
        self.llamadas.append(operacion)
        if self.falla is not None:
            raise self.falla

    def obtener_equipo(self, equipo_id):
        self._registrar("obtener_equipo")
        return next((dict(e) for e in self.equipos if e["equipoId"] == equipo_id), None)

    def existe_equipo(self, equipo_id):
        self._registrar("existe_equipo")
        return any(e["equipoId"] == equipo_id for e in self.equipos)

    def listar_equipos(self, confederacion, ranking_max, pagina, limite):
        self._registrar("listar_equipos")
        filtrados = sorted(
            (e for e in self.equipos if e["confederacion"] == confederacion
             and (ranking_max is None or e["rankingReferencia"] <= ranking_max)),
            key=lambda e: (e["rankingReferencia"], e["equipoId"]),
        )
        inicio = (pagina - 1) * limite
        return [{k: e[k] for k in RESUMEN} for e in filtrados[inicio:inicio + limite]], len(filtrados)

    def listar_jugadores_de_equipo(self, equipo_id, posicion, pagina, limite):
        self._registrar("listar_jugadores_de_equipo")
        filtrados = sorted(
            (j for j in self.jugadores if j["equipoId"] == equipo_id
             and (posicion is None or j["posicion"] == posicion)),
            key=lambda j: (j["apellido"], j["nombre"], j["jugadorId"]),
        )
        inicio = (pagina - 1) * limite
        return [{k: j[k] for k in PLANTEL} for j in filtrados[inicio:inicio + limite]], len(filtrados)

    def obtener_jugador(self, jugador_id):
        self._registrar("obtener_jugador")
        return next((dict(j) for j in self.jugadores if j["jugadorId"] == jugador_id), None)

    def ping(self) -> bool:
        return self.falla is None

    def cerrar(self) -> None:
        pass


class RedisFalso:
    """Imita el contrato de AdaptadorRedis (sesiones y ficha cacheada) en memoria.

    `sesiones` guarda los campos del Hash del Hito 7 más "ttl" (segundos; -1 = sin
    vencimiento). `falla` hace fallar cualquier operación (Redis caído) y
    `falla_guardar` solo el SET de la ficha. `llamadas` registra cada operación.
    """

    def __init__(self) -> None:
        self.sesiones: dict[str, dict] = {}
        self.fichas: dict[str, dict] = {}
        self.falla: Exception | None = None
        self.falla_guardar: Exception | None = None
        self.llamadas: list[str] = []

    def crear_sesion(self, sesion_id: str, usuario_id: str = "USR-00001", rol: str = "lector",
                     ttl: int = 1800, estado: str = "activa") -> None:
        self.sesiones[sesion_id] = {
            "sesion_id": sesion_id, "usuario_id": usuario_id, "ultima_actividad": "1900000000",
            "estado": estado, "rol": rol, "ttl": ttl,
        }

    def _registrar(self, operacion: str) -> None:
        self.llamadas.append(operacion)
        if self.falla is not None:
            raise self.falla

    def leer_sesion(self, sesion_id):
        self._registrar("leer_sesion")
        sesion = self.sesiones.get(sesion_id)
        return dict(sesion) if sesion else None

    def renovar_sesion(self, sesion_id, rol_requerido=None):
        self._registrar("renovar_sesion")
        sesion = self.sesiones.get(sesion_id)
        if sesion is None or sesion["ttl"] <= 0 or sesion["estado"] != "activa":
            return {"resultado": "no_vigente"}
        if rol_requerido and sesion["rol"] != rol_requerido:
            return {"resultado": "rol_no_autorizado"}
        sesion["ttl"] = 1800
        sesion["ultima_actividad"] = str(int(sesion["ultima_actividad"]) + 1)
        return {"resultado": "ok", "usuario_id": sesion["usuario_id"], "rol": sesion["rol"],
                "ttl": sesion["ttl"]}

    def cerrar_sesion(self, sesion_id):
        self._registrar("cerrar_sesion")
        self.sesiones.pop(sesion_id, None)

    def leer_ficha_cacheada(self, equipo_id):
        self._registrar("leer_ficha_cacheada")
        ficha = self.fichas.get(equipo_id)
        return dict(ficha) if ficha else None

    def guardar_ficha_cacheada(self, equipo_id, ficha):
        self._registrar("guardar_ficha_cacheada")
        if self.falla_guardar is not None:
            raise self.falla_guardar
        self.fichas[equipo_id] = dict(ficha)

    def invalidar_ficha_cacheada(self, equipo_id):
        self._registrar("invalidar_ficha_cacheada")
        self.fichas.pop(equipo_id, None)

    def ping(self) -> bool:
        return self.falla is None

    def cerrar(self) -> None:
        pass
