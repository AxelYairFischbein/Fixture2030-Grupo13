"""Adaptador de objetos (Hito 9): clases FixtureH9.* en el namespace USER de InterSystems IRIS."""

import threading

import iris

from app.contexto import operacion
from app.errors import TransicionInvalida

# El driver nativo informa fallas de red y autenticación como RuntimeError.
ERRORES = (RuntimeError, OSError, ConnectionError)

Q_PARTIDO = """SELECT ID, Codigo, EstadioCodigo, Estado, Arbitro, Arbitro->Codigo, Arbitro->Nombre,
  Arbitro->Nacionalidad, Arbitro->Licencia FROM FixtureH9.Partido WHERE Codigo = ?"""
Q_EVENTOS = """SELECT TOP 100 ID, Tipo, Minuto, Jugador, Jugador->Codigo, Jugador->Nombre, Jugador->Numero,
  Jugador->Posicion FROM FixtureH9.Evento WHERE Partido = ? ORDER BY Minuto, ID"""
ERROR_TRANSICION = "5001"  # Código que devuelve Partido.CambiarEstado() ante una transición no permitida.


class IrisActas:
    nombre = "iris"

    def __init__(self, cfg):
        self._cfg = cfg
        self._conexion = None
        # ponytail: una conexión y un lock global; usar un pool si crece la concurrencia.
        self._lock = threading.Lock()

    def _conectar(self):
        if self._conexion is None:
            c = self._cfg
            self._conexion = iris.connect(c.iris_host, c.iris_port, c.iris_namespace, c.iris_user,
                                          c.iris_password, timeout=max(1, int(c.timeout)), sharedmemory=False)
        return self._conexion

    def _ejecutar(self, nombre: str, funcion):
        with self._lock, operacion(self.nombre, nombre, ERRORES):
            try:
                return funcion(self._conectar())
            except ERRORES:
                self._conexion = None  # se reconecta en la próxima operación
                raise

    def ping(self):
        def leer(conexion):
            cur = conexion.cursor()
            cur.setQueryTimeout(max(1, int(self._cfg.timeout)))
            cur.execute("SELECT 1")
        self._ejecutar("ping", leer)

    def acta(self, codigo: str) -> dict | None:
        def leer(conexion):
            cur = conexion.cursor()
            cur.setQueryTimeout(max(1, int(self._cfg.timeout)))
            cur.execute(Q_PARTIDO, [codigo])
            fila = cur.fetchone()
            if not fila:
                return None
            fila = tuple(fila)  # la fila del driver deja de ser legible al reutilizar el cursor
            cur.execute(Q_EVENTOS, [fila[0]])
            return fila, [tuple(e) for e in cur.fetchall()]

        resultado = self._ejecutar("leer_acta", leer)
        if resultado is None:
            return None
        p, eventos = resultado
        return {
            "id": str(p[0]), "codigo": p[1], "estadioCodigo": p[2], "estado": p[3],
            "arbitro": {"id": str(p[4]), "codigo": p[5], "nombre": p[6], "nacionalidad": p[7], "licencia": p[8]},
            "eventos": [{"id": str(e[0]), "tipo": e[1], "minuto": e[2],
                         "jugador": {"id": str(e[3]), "codigo": e[4], "nombre": e[5], "numero": e[6], "posicion": e[7]}}
                        for e in eventos],
        }

    def cambiar_estado(self, codigo: str, nuevo: str) -> bool:
        """Invoca el método de dominio Partido.CambiarEstado(); False si el partido no existe."""
        def transicionar(conexion):
            nativo = iris.createIRIS(conexion)
            partido = nativo.classMethodObject("FixtureH9.Partido", "PorCodigoOpen", codigo)
            if partido is None:
                return False
            sc = partido.invoke("CambiarEstado", nuevo)
            if nativo.classMethodValue("%SYSTEM.Status", "IsOK", sc) == 1:
                return True
            codigos = str(nativo.classMethodValue("%SYSTEM.Status", "GetErrorCodes", sc))
            if codigos == ERROR_TRANSICION:
                actual = partido.get("Estado")
                raise TransicionInvalida(f"Transición no permitida: {actual} -> {nuevo}.")
            raise ValueError(f"IRIS rechazó el guardado con códigos {codigos}")  # -> 500, detalle solo en logs

        return self._ejecutar("cambiar_estado", transicionar)
