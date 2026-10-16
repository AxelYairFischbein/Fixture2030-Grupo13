"""Adaptador de InfluxDB 3 Core (Hito 8): estadísticas temporales por equipo.

Consulta fixture2030_h8.estadisticas_equipo (tags partido_id, equipo_id, estadio_id;
fields posesion_pct, pases_acumulados, tiros_intervalo; una observación por paso) con
SQL por POST /api/v3/query_sql y token Bearer leído del archivo de INFLUX_TOKEN_FILE.

Las sentencias son fijas. Los valores que vienen del usuario (partido, equipo, fechas,
límite) viajan en "params" como placeholders $nombre, nunca dentro del texto SQL. Lo
único que se arma con texto es el paso de la serie (entero de configuración) y el
intervalo de DATE_BIN, tomado de un diccionario cerrado.

Las agregaciones son las del Hito 8 (scripts/comun.py, consultas_temporales.py y
agregaciones.py): AVG de posesión, SUM de las diferencias de pases con LAG incluyendo
la muestra anterior a la ventana, SUM de tiros, conteo de muestras e intervalos
inválidos. Nunca se registra el token, el SQL ni el cuerpo de una respuesta de error.
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from app.config.settings import RAIZ_HITO10, Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio

DEPENDENCIA = "influxdb"
TABLA = "estadisticas_equipo"

logger = logging.getLogger("app.adapters.influx")

# Resoluciones de CU-17: la clave es el valor validado de la API, el valor el literal SQL.
INTERVALOS_DATE_BIN = {"1m": "1 minute", "5m": "5 minutes"}

# CU-15 (Hito 8 P2): últimas observaciones de una serie dentro de [desde, hasta).
SEL_RECIENTES = f"""SELECT time, estadio_id, posesion_pct, pases_acumulados, tiros_intervalo
FROM {TABLA}
WHERE partido_id = $partido AND equipo_id = $equipo AND time >= $desde AND time < $hasta
ORDER BY time DESC LIMIT $limite"""


def _incrementos(paso_s: int, con_equipo: bool) -> str:
    """CTE del Hito 8 (comun.incrementos): incluye la muestra anterior a $desde
    ($previo = desde − paso) para calcular el primer incremento de la ventana."""
    filtro_equipo = " AND equipo_id = $equipo" if con_equipo else ""
    return f"""WITH diferencias AS (
  SELECT time, equipo_id, posesion_pct, tiros_intervalo,
    pases_acumulados - LAG(pases_acumulados) OVER (
      PARTITION BY partido_id, equipo_id, estadio_id ORDER BY time
    ) AS pases_nuevos,
    time - LAG(time) OVER (
      PARTITION BY partido_id, equipo_id, estadio_id ORDER BY time
    ) AS separacion
  FROM {TABLA}
  WHERE time >= $previo AND time < $hasta AND partido_id = $partido{filtro_equipo}
), ventana AS (
  SELECT * FROM diferencias WHERE time >= $desde AND time < $hasta
)
"""


def _medidas(paso_s: int) -> str:
    return f"""COUNT(*) AS muestras,
  ROUND(AVG(posesion_pct), 3) AS posesion_media,
  SUM(pases_nuevos) AS pases_nuevos, SUM(tiros_intervalo) AS tiros,
  SUM(CASE WHEN separacion = INTERVAL '{paso_s} seconds'
    AND pases_nuevos >= 0 THEN 0 ELSE 1 END) AS intervalos_invalidos"""


def _sql_comparacion(paso_s: int) -> str:
    # CU-16 (Hito 8 P3, consultas_temporales.py).
    return _incrementos(paso_s, False) + f"""SELECT equipo_id, {_medidas(paso_s)}
FROM ventana GROUP BY equipo_id ORDER BY equipo_id"""


def _sql_evolucion(paso_s: int, intervalo: str, con_equipo: bool) -> str:
    # CU-17 (Hito 8 P4, agregaciones.py). DATE_BIN alineado a la época: bins UTC exactos.
    return _incrementos(paso_s, con_equipo) + f"""SELECT
  DATE_BIN(INTERVAL '{intervalo}', time, TIMESTAMP '1970-01-01T00:00:00Z') AS inicio,
  equipo_id, {_medidas(paso_s)}
FROM ventana GROUP BY inicio, equipo_id ORDER BY equipo_id, inicio"""


def _texto_instante(instante: datetime) -> str:
    """Parámetro de fecha para InfluxDB: ISO-8601 en UTC con Z."""
    return instante.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _a_utc(texto: str) -> datetime:
    """El JSON de InfluxDB informa time sin zona, en UTC."""
    valor = datetime.fromisoformat(texto)
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor.astimezone(UTC)


def _leer_token(ruta: Path) -> str:
    ruta = ruta if ruta.is_absolute() else RAIZ_HITO10 / ruta
    try:
        token = ruta.read_text(encoding="utf-8").strip()
    except OSError:
        token = ""
    if not token:
        # Se nombra la variable, nunca la ruta resuelta ni el valor.
        raise RuntimeError(
            "Configuración incompleta: no se pudo leer el token de InfluxDB desde "
            "INFLUX_TOKEN_FILE. Revisar Hito 10/.env."
        )
    return token


class AdaptadorInflux:
    def __init__(self, settings: Settings, cliente: httpx.Client | None = None) -> None:
        self._db = settings.influx_database
        self._paso_s = settings.influx_paso_s
        self._paso = timedelta(seconds=self._paso_s)
        self._cliente = cliente or httpx.Client(
            base_url=settings.influx_url,
            timeout=settings.influx_timeout_s,
            headers={"Authorization": "Bearer " + _leer_token(settings.influx_token_file)},
        )
        self._sql_comparacion = _sql_comparacion(self._paso_s)
        self._sql_evolucion = {
            (resolucion, con_equipo): _sql_evolucion(self._paso_s, intervalo, con_equipo)
            for resolucion, intervalo in INTERVALOS_DATE_BIN.items()
            for con_equipo in (False, True)
        }

    def cerrar(self) -> None:
        self._cliente.close()

    @contextmanager
    def _traducir(self, operacion: str) -> Iterator[None]:
        """Traduce las excepciones de httpx y los códigos HTTP de InfluxDB a app.errors."""
        inicio = time.perf_counter()
        resultado = "ok"
        try:
            yield
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as exc:
            resultado = f"DEPENDENCIA_TIMEOUT tipo={type(exc).__name__}"
            raise DependenciaTimeout(DEPENDENCIA) from exc
        except (httpx.ConnectTimeout, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            # No se llegó a conectar o la conexión se cortó: la fuente no está disponible.
            resultado = f"DEPENDENCIA_NO_DISPONIBLE tipo={type(exc).__name__}"
            raise DependenciaNoDisponible(DEPENDENCIA) from exc
        except httpx.HTTPStatusError as exc:
            estado = exc.response.status_code
            if estado in (401, 403):
                # Token inválido o sin permiso: es configuración, no disponibilidad.
                resultado = f"ERROR_INTERNO http={estado} motivo=credencial_rechazada"
                raise ErrorDominio() from None
            if estado >= 500:
                resultado = f"DEPENDENCIA_NO_DISPONIBLE http={estado}"
                raise DependenciaNoDisponible(DEPENDENCIA) from None
            # 4xx restantes: base o tabla inexistente, SQL rechazado. Error propio, no del usuario.
            resultado = f"ERROR_INTERNO http={estado}"
            raise ErrorDominio() from None
        except (httpx.HTTPError, ValueError) as exc:
            # ValueError: cuerpo que no es el JSON esperado.
            resultado = f"ERROR_INTERNO tipo={type(exc).__name__}"
            raise ErrorDominio() from exc
        finally:
            duracion_ms = (time.perf_counter() - inicio) * 1000
            logger.info(
                "dependencia=%s operacion=%s resultado=%s duracion_ms=%.1f",
                DEPENDENCIA, operacion, resultado, duracion_ms,
            )

    def _consultar(self, operacion: str, sql: str, params: dict) -> list[dict]:
        with self._traducir(operacion):
            respuesta = self._cliente.post(
                "/api/v3/query_sql",
                json={"db": self._db, "q": sql, "params": params, "format": "json"},
            )
            respuesta.raise_for_status()
            filas = respuesta.json()
            if not isinstance(filas, list):
                raise ValueError("respuesta inesperada")
            return filas

    def _parametros_ventana(self, partido_id: str, desde: datetime, hasta: datetime) -> dict:
        return {
            "partido": partido_id,
            "previo": _texto_instante(desde - self._paso),
            "desde": _texto_instante(desde),
            "hasta": _texto_instante(hasta),
        }

    # CU-15

    def ultimas_observaciones(self, partido_id: str, equipo_id: str, desde: datetime,
                              hasta: datetime, limite: int) -> list[dict]:
        """Hasta `limite` puntos de una serie en [desde, hasta), del más reciente al más antiguo."""
        filas = self._consultar("ultimas_observaciones", SEL_RECIENTES, {
            "partido": partido_id, "equipo": equipo_id, "desde": _texto_instante(desde),
            "hasta": _texto_instante(hasta), "limite": int(limite),
        })
        return [{**f, "time": _a_utc(f["time"])} for f in filas]

    # CU-16

    def comparar(self, partido_id: str, desde: datetime, hasta: datetime) -> list[dict]:
        """Una fila por equipo con muestras, posesión media, pases nuevos, tiros e inválidos."""
        return self._consultar("comparar", self._sql_comparacion,
                               self._parametros_ventana(partido_id, desde, hasta))

    # CU-17

    def evolucion(self, partido_id: str, equipo_id: str | None, desde: datetime,
                  hasta: datetime, resolucion: str) -> list[dict]:
        """Una fila por equipo y bin (orden equipo_id, inicio) con las medidas de CU-16."""
        sql = self._sql_evolucion[(resolucion, equipo_id is not None)]
        params = self._parametros_ventana(partido_id, desde, hasta)
        if equipo_id is not None:
            params["equipo"] = equipo_id
        filas = self._consultar("evolucion", sql, params)
        return [{**f, "inicio": _a_utc(f["inicio"])} for f in filas]

    def ping(self) -> bool:
        try:
            with self._traducir("ping"):
                self._cliente.get("/health").raise_for_status()
            return True
        except ErrorDominio:
            return False
