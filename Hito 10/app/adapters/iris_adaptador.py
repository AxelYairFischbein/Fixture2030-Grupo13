"""Adaptador de InterSystems IRIS (Hito 9): acta del partido y transiciones de estado.

Modelo del Hito 9 en el namespace USER (paquete FixtureH9): Partido (índice único
PorCodigo, Estado, EstadioCodigo, Arbitro) con Eventos hijos (Tipo, Minuto, Jugador);
Arbitro y Jugador heredan de Persona (Codigo, Nombre, Nacionalidad).

- CU-18 lee el acta con SQL proyectado y parámetros (?), nunca con texto concatenado.
  No se proyectan IDs internos (%ID, 1||1) ni la licencia del árbitro.
- CU-19 invoca FixtureH10.Servicio.Transicionar (Hito 10/iris/), que abre el Partido
  por PorCodigo con bloqueo y llama a CambiarEstado(). Nunca se usa UPDATE SQL.

La conexión se abre en el primer uso (la API arranca aunque IRIS esté caído) y se
comparte entre requests detrás de un lock, porque el SDK no es seguro entre hilos.
Ante una falla de comunicación se descarta y la próxima request reconecta. El SDK
informa los errores con mensajes del servidor (<COMMUNICATION LINK ERROR>, <CLASS
DOES NOT EXIST>…) y no con tipos distintos: la clasificación se hace por esos
marcadores. Nunca se registra el SQL, los parámetros, las credenciales ni el mensaje
crudo del driver.
"""

import logging
import math
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import iris
import iris.dbapi

from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio

DEPENDENCIA = "iris"
CLASE_SERVICIO = "FixtureH10.Servicio"

logger = logging.getLogger("app.adapters.iris")

# CU-18. Codigo usa COLLATION EXACT: la comparación distingue mayúsculas.
SEL_PARTIDO = """SELECT p.EstadioCodigo, p.Estado,
  p.Arbitro->Codigo, p.Arbitro->Nombre, p.Arbitro->Nacionalidad
FROM FixtureH9.Partido p WHERE p.Codigo = ?"""

# Cota defensiva: un acta real tiene pocas decenas de eventos. ID solo desempata el
# orden entre eventos del mismo minuto; no se proyecta.
MAX_EVENTOS = 500
SEL_EVENTOS = f"""SELECT TOP {MAX_EVENTOS} e.Tipo, e.Minuto,
  e.Jugador->Codigo, e.Jugador->Nombre, e.Jugador->Numero, e.Jugador->Posicion
FROM FixtureH9.Evento e WHERE e.Partido->Codigo = ? ORDER BY e.Minuto, e.ID"""

PING = "SELECT 1"

# Resultados que devuelve FixtureH10.Servicio.Transicionar ("RESULTADO|anterior|actual").
RESULTADOS_TRANSICION = {"OK", "SIN_CAMBIO", "NO_ENCONTRADO", "TRANSICION_NO_PERMITIDA"}

# Marcadores de los mensajes del SDK y del servidor, en mayúsculas.
_NO_DISPONIBLE = ("COMMUNICATION LINK ERROR", "COMMUNICATION ERROR", "ACCESS DENIED",
                  "CONNECTION", "SOCKET")
_TIMEOUT = ("TIMED OUT", "TIMEOUT")
_ENVOLTORIO_AUSENTE = ("CLASS DOES NOT EXIST", "METHOD DOES NOT EXIST")


def clasificar(exc: BaseException) -> str:
    """'no_disponible', 'timeout', 'envoltorio_ausente' o 'interno'.

    Un fallo al conectar (incluido el timeout de conexión y el login rechazado) es
    'no_disponible'; un timeout con la conexión ya establecida es 'timeout'.
    """
    texto = str(exc).upper()
    if "FAILED TO CONNECT" in texto:
        return "no_disponible"
    # TimeoutError hereda de OSError: se evalúa antes.
    if isinstance(exc, TimeoutError) or any(m in texto for m in _TIMEOUT):
        return "timeout"
    if isinstance(exc, OSError):
        return "no_disponible"
    if any(m in texto for m in _NO_DISPONIBLE):
        return "no_disponible"
    if any(m in texto for m in _ENVOLTORIO_AUSENTE):
        return "envoltorio_ausente"
    return "interno"


def interpretar_transicion(respuesta: str) -> dict:
    """Convierte "RESULTADO|anterior|actual" en un dict. BLOQUEADO → 504; ERROR o una
    respuesta desconocida → 500 (el detalle no sale de IRIS)."""
    partes = str(respuesta).split("|")
    resultado = partes[0] if len(partes) == 3 else ""
    if resultado == "BLOQUEADO":
        # Otro operador retiene el partido: no se aplicó nada y se puede reintentar.
        raise DependenciaTimeout(DEPENDENCIA)
    if resultado not in RESULTADOS_TRANSICION:
        raise ErrorDominio()
    return {"resultado": resultado, "anterior": partes[1] or None, "actual": partes[2] or None}


class AdaptadorIris:
    def __init__(self, settings: Settings,
                 conectar: Callable[[], tuple[object, object]] | None = None) -> None:
        """`conectar` devuelve (conexión DB-API, objeto nativo IRIS); las pruebas inyectan uno falso."""
        self._settings = settings
        self._conectar = conectar or self._conectar_sdk
        self._timeout_s = max(1, math.ceil(settings.iris_timeout_s))
        self._espera_bloqueo_s = settings.iris_espera_bloqueo_s
        self._conexion = None
        self._nativo = None
        self._lock = threading.Lock()

    # Conexión

    def _conectar_sdk(self) -> tuple[object, object]:
        s = self._settings
        conexion = iris.dbapi.connect(
            hostname=s.iris_host, port=s.iris_port, namespace=s.iris_namespace,
            username=s.iris_user, password=s.iris_password.get_secret_value(),
            timeout=self._timeout_s,
        )
        return conexion, iris.createIRIS(conexion)

    def _lista(self) -> None:
        """Conecta en el primer uso. Se llama con el lock tomado."""
        if self._conexion is None:
            self._conexion, self._nativo = self._conectar()

    def _descartar(self) -> None:
        conexion, self._conexion, self._nativo = self._conexion, None, None
        if conexion is not None:
            try:
                conexion.close()
            except Exception:  # noqa: BLE001 - la conexión ya estaba rota
                pass

    def cerrar(self) -> None:
        with self._lock:
            self._descartar()

    @contextmanager
    def _operar(self, operacion: str) -> Iterator[None]:
        """Serializa el uso de la conexión, traduce las excepciones y registra el resultado."""
        inicio = time.perf_counter()
        resultado = "ok"
        with self._lock:
            try:
                self._lista()
                yield
            except ErrorDominio as exc:
                resultado = exc.codigo
                raise
            except Exception as exc:  # noqa: BLE001 - el SDK no usa tipos específicos
                tipo = clasificar(exc)
                if tipo in ("no_disponible", "timeout"):
                    # La conexión puede haber quedado inutilizable: se reabre en el próximo uso.
                    self._descartar()
                if tipo == "no_disponible":
                    resultado = f"DEPENDENCIA_NO_DISPONIBLE tipo={type(exc).__name__}"
                    raise DependenciaNoDisponible(DEPENDENCIA) from exc
                if tipo == "timeout":
                    resultado = f"DEPENDENCIA_TIMEOUT tipo={type(exc).__name__}"
                    raise DependenciaTimeout(DEPENDENCIA) from exc
                if tipo == "envoltorio_ausente":
                    resultado = (f"ERROR_INTERNO motivo=falta cargar {CLASE_SERVICIO} "
                                 "(ver Hito 10/iris/README.md)")
                else:
                    resultado = f"ERROR_INTERNO tipo={type(exc).__name__}"
                raise ErrorDominio() from exc
            finally:
                duracion_ms = (time.perf_counter() - inicio) * 1000
                logger.info(
                    "dependencia=%s operacion=%s resultado=%s duracion_ms=%.1f",
                    DEPENDENCIA, operacion, resultado, duracion_ms,
                )

    def _filas(self, sql: str, parametros: list) -> list[tuple]:
        cursor = self._conexion.cursor()
        try:
            cursor.setQueryTimeout(self._timeout_s)
            cursor.execute(sql, parametros)
            return [tuple(fila) for fila in cursor.fetchall()]
        finally:
            cursor.close()

    # CU-18

    def leer_acta(self, partido_id: str) -> dict | None:
        """Acta con estado, árbitro y eventos ordenados por minuto. None si no hay Partido."""
        with self._operar("leer_acta"):
            partidos = self._filas(SEL_PARTIDO, [partido_id])
            if not partidos:
                return None
            estadio, estado, arb_codigo, arb_nombre, arb_nacionalidad = partidos[0]
            eventos = self._filas(SEL_EVENTOS, [partido_id])
        return {
            "partidoId": partido_id, "estadioId": estadio, "estado": estado,
            "arbitro": {"codigo": arb_codigo, "nombre": arb_nombre,
                        "nacionalidad": arb_nacionalidad},
            "eventos": [
                {"tipo": tipo, "minuto": int(minuto),
                 "jugador": {"codigo": codigo, "nombre": nombre, "numero": int(numero),
                             "posicion": posicion}}
                for tipo, minuto, codigo, nombre, numero, posicion in eventos
            ],
        }

    # CU-19

    def transicionar(self, partido_id: str, nuevo_estado: str) -> dict:
        """{"resultado", "anterior", "actual"} según FixtureH10.Servicio.Transicionar."""
        with self._operar("transicionar"):
            respuesta = self._nativo.classMethodString(
                CLASE_SERVICIO, "Transicionar", partido_id, nuevo_estado, self._espera_bloqueo_s)
            return interpretar_transicion(respuesta)

    def ping(self) -> bool:
        """Chequeo de salud: True si IRIS responde. Nunca lanza."""
        try:
            with self._operar("ping"):
                self._filas(PING, [])
            return True
        except ErrorDominio:
            return False
