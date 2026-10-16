"""Adaptadores falsos en memoria para las pruebas unitarias (sin Docker)."""

from datetime import datetime, timezone

from app.adapters.cassandra_adaptador import clave_de_orden, minuto_de, segmento


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
        self.idempotencia: dict[str, dict] = {}
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

    def reservar_idempotencia(self, clave, registro):
        self._registrar("reservar_idempotencia")
        if clave in self.idempotencia:
            return dict(self.idempotencia[clave])
        self.idempotencia[clave] = dict(registro)
        return None

    def ping(self) -> bool:
        return self.falla is None

    def cerrar(self) -> None:
        pass


def _participante(numero: int, equipo_id: str, rol: str) -> dict:
    return {"jugadorId": f"JUG-{numero:04d}", "nombre": f"Nombre{numero:04d}",
            "apellido": f"Apellido{numero:04d}", "equipoId": equipo_id, "rol": rol}


class Neo4jFalso:
    """Imita el contrato de AdaptadorNeo4j con una porción de la muestra del Hito 5.

    EQ-001 disputa PAR-001 (vs EQ-002) y PAR-033 (vs EQ-003), LOCAL en EST-01.
    PAR-002 (EQ-003 vs EQ-004, EST-02) no tiene eventos. EQ-005 existe sin partidos.
    `falla` hace fallar cualquier consulta y `llamadas` registra cada una.
    """

    EQUIPOS = {f"EQ-{n:03d}": f"F{n:02d}" for n in range(1, 6)}
    ESTADIOS = {f"EST-{n:02d}": {"estadioId": f"EST-{n:02d}", "nombre": f"Estadio Sintetico {n:02d}",
                                 "ciudad": f"Ciudad Sede {n:02d}"} for n in range(1, 9)}

    def __init__(self) -> None:
        dia = datetime(2030, 6, 10, 18, tzinfo=timezone.utc)
        self.partidos = [
            {"partidoId": "PAR-001", "inicio": dia, "grupo": "G01", "fase": "GRUPOS_MUESTRA",
             "local": "EQ-001", "visitante": "EQ-002", "estadioId": "EST-01"},
            {"partidoId": "PAR-002", "inicio": dia, "grupo": "G01", "fase": "GRUPOS_MUESTRA",
             "local": "EQ-003", "visitante": "EQ-004", "estadioId": "EST-02"},
            {"partidoId": "PAR-033", "inicio": dia.replace(day=14), "grupo": "G01",
             "fase": "GRUPOS_MUESTRA", "local": "EQ-001", "visitante": "EQ-003",
             "estadioId": "EST-01"},
        ]
        self.eventos = {
            "PAR-001": [
                {"eventoId": "EVT-PAR-001-LOCAL", "tipo": "SUSTITUCION", "minuto": 60,
                 "participantes": [_participante(20, "EQ-001", "SALE"),
                                   _participante(21, "EQ-001", "ENTRA")]},
                {"eventoId": "EVT-PAR-001-VISITANTE", "tipo": "SUSTITUCION", "minuto": 65,
                 "participantes": [_participante(44, "EQ-002", "SALE"),
                                   _participante(45, "EQ-002", "ENTRA")]},
            ],
        }
        self.falla: Exception | None = None
        self.llamadas: list[str] = []

    def _registrar(self, operacion: str) -> None:
        self.llamadas.append(operacion)
        if self.falla is not None:
            raise self.falla

    def _ordenados(self) -> list[dict]:
        return sorted(self.partidos, key=lambda p: (p["inicio"], p["partidoId"]))

    def agenda_equipo(self, equipo_id, limite):
        self._registrar("agenda_equipo")
        if equipo_id not in self.EQUIPOS:
            return None
        agenda = []
        for p in self._ordenados():
            if equipo_id not in (p["local"], p["visitante"]):
                continue
            local = p["local"] == equipo_id
            rival = p["visitante"] if local else p["local"]
            agenda.append({
                "partidoId": p["partidoId"], "inicio": p["inicio"], "grupo": p["grupo"],
                "fase": p["fase"], "rol": "LOCAL" if local else "VISITANTE",
                "rival": {"equipoId": rival, "codigo": self.EQUIPOS[rival],
                          "nombre": f"Seleccion Sintetica {rival[-2:]}"},
                "estadio": dict(self.ESTADIOS[p["estadioId"]]),
            })
        return agenda[:limite]

    def eventos_partido(self, partido_id, limite):
        self._registrar("eventos_partido")
        if partido_id not in {p["partidoId"] for p in self.partidos}:
            return None
        return [dict(e) for e in self.eventos.get(partido_id, [])][:limite]

    def partidos_por_fecha(self, desde, hasta, estadio_id, limite):
        self._registrar("partidos_por_fecha")
        return [
            {"partidoId": p["partidoId"], "inicio": p["inicio"], "grupo": p["grupo"],
             "fase": p["fase"], "estadio": dict(self.ESTADIOS[p["estadioId"]])}
            for p in self._ordenados()
            if desde <= p["inicio"] < hasta and estadio_id in (None, p["estadioId"])
        ][:limite]

    def cargar_catalogo_partidos(self):
        self._registrar("cargar_catalogo_partidos")
        return {p["partidoId"]: tuple(sorted((p["local"], p["visitante"]))) for p in self.partidos}

    def ping(self) -> bool:
        return self.falla is None

    def cerrar(self) -> None:
        pass


def _comentario(numero: int, partido_id: str, creado: str, usuario_id: str, estado: str,
                likes: int = 0) -> dict:
    creado_en = datetime.fromisoformat(creado)
    comentario_id = f"MUESTRA-{numero:03d}"
    return {
        "partido_id": partido_id, "minuto": minuto_de(creado_en),
        "segmento": segmento(comentario_id), "creado_en": creado_en,
        "comentario_id": comentario_id, "usuario_id": usuario_id, "dia": creado_en.date(),
        "contenido": f"Comentario de muestra {numero:03d}", "estado": estado, "likes": likes,
    }


class CassandraFalso:
    """Imita el contrato de AdaptadorCassandra con la muestra del Hito 6 (carga_muestra.cql).

    Las filas se indexan por clave primaria completa, así que una reescritura con la misma
    clave es un upsert (como en Cassandra). `filas_por_usuario` es la segunda representación.
    `falla` hace fallar cualquier operación y `llamadas` registra cada una.
    """

    def __init__(self) -> None:
        muestra = [
            _comentario(1, "PAR-001", "2030-06-10T18:00:20+00:00", "USR-00001", "visible", 2),
            _comentario(2, "PAR-001", "2030-06-10T18:00:30+00:00", "USR-00002", "pendiente"),
            _comentario(3, "PAR-001", "2030-06-10T18:00:55+00:00", "USR-00001", "visible", 4),
            _comentario(4, "PAR-001", "2030-06-10T18:01:05+00:00", "USR-00003", "oculto"),
            _comentario(5, "PAR-001", "2030-06-10T18:01:20+00:00", "USR-00001", "visible", 5),
            _comentario(6, "PAR-001", "2030-06-10T18:01:20+00:00", "USR-00002", "visible", 3),
            _comentario(7, "PAR-001", "2030-06-10T18:01:45+00:00", "USR-00003", "pendiente"),
            _comentario(8, "PAR-001", "2030-06-10T18:01:59+00:00", "USR-00001", "visible", 1),
            _comentario(9, "PAR-001", "2030-06-10T18:02:05+00:00", "USR-00002", "visible", 1),
            _comentario(10, "PAR-001", "2030-06-10T18:02:10+00:00", "USR-00001", "visible"),
            _comentario(11, "PAR-002", "2030-06-10T18:01:10+00:00", "USR-00001", "visible", 2),
        ]
        self.filas_por_partido: dict[tuple, dict] = {}
        self.filas_por_usuario: dict[tuple, dict] = {}
        for fila in muestra:
            self._guardar(fila)
        self.falla: Exception | None = None
        self.falla_escritura: Exception | None = None
        self.llamadas: list[str] = []

    def _guardar(self, fila: dict) -> None:
        self.filas_por_partido[(fila["partido_id"], fila["minuto"], fila["segmento"],
                                fila["creado_en"], fila["comentario_id"])] = dict(fila)
        self.filas_por_usuario[(fila["usuario_id"], fila["dia"], fila["creado_en"],
                                fila["comentario_id"])] = dict(fila)

    def _registrar(self, operacion: str) -> None:
        self.llamadas.append(operacion)
        if self.falla is not None:
            raise self.falla

    @staticmethod
    def _pagina(filas, antes_de, limite):
        filas = sorted(filas, key=lambda f: clave_de_orden(f["creado_en"], f["comentario_id"]))
        if antes_de is not None:
            tope = clave_de_orden(*antes_de)
            filas = [f for f in filas if clave_de_orden(f["creado_en"], f["comentario_id"]) > tope]
        if len(filas) > limite:
            ultima = filas[limite - 1]
            return [dict(f) for f in filas[:limite]], (ultima["creado_en"], ultima["comentario_id"])
        return [dict(f) for f in filas], None

    def leer_por_partido(self, partido_id, desde, hasta, antes_de, limite, solo_visibles):
        self._registrar("leer_por_partido")
        filas = [f for f in self.filas_por_partido.values()
                 if f["partido_id"] == partido_id and desde <= f["creado_en"] < hasta
                 and (not solo_visibles or f["estado"] == "visible")]
        return self._pagina(filas, antes_de, limite)

    def leer_por_usuario(self, usuario_id, dia, antes_de, limite):
        self._registrar("leer_por_usuario")
        filas = [f for (u, d, _, _), f in self.filas_por_usuario.items()
                 if u == usuario_id and d == dia]
        return self._pagina(filas, antes_de, limite)

    def leer_comentario(self, partido_id, creado_en, comentario_id):
        self._registrar("leer_comentario")
        fila = self.filas_por_partido.get((partido_id, minuto_de(creado_en), segmento(comentario_id),
                                           creado_en, comentario_id))
        return dict(fila) if fila else None

    def insertar_comentario(self, comentario):
        self._registrar("insertar_comentario")
        if self.falla_escritura is not None:
            raise self.falla_escritura
        creado_en = comentario["creado_en"]
        self._guardar({**comentario, "minuto": minuto_de(creado_en),
                       "segmento": segmento(comentario["comentario_id"]), "dia": creado_en.date()})

    def actualizar_estado(self, fila, estado):
        self._registrar("actualizar_estado")
        if self.falla_escritura is not None:
            raise self.falla_escritura
        self.filas_por_partido[(fila["partido_id"], fila["minuto"], fila["segmento"],
                                fila["creado_en"], fila["comentario_id"])]["estado"] = estado
        self.filas_por_usuario[(fila["usuario_id"], fila["dia"], fila["creado_en"],
                                fila["comentario_id"])]["estado"] = estado

    def escrituras(self) -> int:
        return sum(op in ("insertar_comentario", "actualizar_estado") for op in self.llamadas)

    def ping(self) -> bool:
        return self.falla is None

    def cerrar(self) -> None:
        pass