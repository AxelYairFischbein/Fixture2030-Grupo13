"""Adaptador temporal (Hito 8): tabla estadisticas_equipo de InfluxDB 3 Core vía SQL HTTP."""

from datetime import datetime, timezone

import httpx

from app.contexto import operacion

ERRORES = (httpx.HTTPError,)
TABLA = "estadisticas_equipo"
# Lista cerrada: el intervalo nunca se toma literalmente del consumidor.
INTERVALOS_SQL = {"10s": "10 seconds", "30s": "30 seconds", "1m": "1 minute", "5m": "5 minutes"}


def _iso(valor: datetime) -> str:
    return valor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class InfluxEstadisticas:
    nombre = "influxdb"

    def __init__(self, cfg):
        self._db = cfg.influx_db
        self._http = httpx.Client(base_url=cfg.influx_url, timeout=cfg.timeout,
                                  headers={"Authorization": f"Bearer {cfg.influx_token}"})

    def _sql(self, consulta: str, params: dict | None = None) -> list[dict]:
        r = self._http.post("/api/v3/query_sql",
                            json={"db": self._db, "q": consulta, "params": params or {}, "format": "json"})
        if r.status_code == 400:
            raise RuntimeError("InfluxDB rechazó la consulta generada por la API")  # defecto propio: 500
        r.raise_for_status()  # 401/403/404/5xx: credencial, base o servicio no disponibles -> 503
        return r.json()

    def ping(self):
        with operacion(self.nombre, "ping", ERRORES):
            self._sql("SELECT 1")

    def ultimo_instante(self, partido_id: str) -> datetime | None:
        # Acotado por la retención de 7 días del Hito 8 y por el tag partido_id.
        with operacion(self.nombre, "ultimo_instante", ERRORES):
            filas = self._sql(f"SELECT MAX(time) AS ultimo FROM {TABLA} "
                              "WHERE partido_id = $partido AND time >= now() - INTERVAL '7 days'",
                              {"partido": partido_id})
        ultimo = filas[0].get("ultimo") if filas else None
        return datetime.fromisoformat(ultimo).replace(tzinfo=timezone.utc) if ultimo else None

    def resumen(self, partido_id: str, equipo_id: str | None, desde: datetime, hasta: datetime,
                intervalo: str, limite: int) -> list[dict]:
        params = {"partido": partido_id, "desde": _iso(desde), "hasta": _iso(hasta)}
        filtro_equipo = ""
        if equipo_id:
            filtro_equipo, params["equipo"] = "AND equipo_id = $equipo", equipo_id
        consulta = f"""SELECT DATE_BIN(INTERVAL '{INTERVALOS_SQL[intervalo]}', time) AS inicio, equipo_id,
            COUNT(*) AS muestras, ROUND(AVG(posesion_pct), 3) AS posesion_media,
            SUM(tiros_intervalo) AS tiros, MAX(pases_acumulados) AS pases_acumulados
          FROM {TABLA}
          WHERE partido_id = $partido AND time >= $desde AND time < $hasta {filtro_equipo}
          GROUP BY inicio, equipo_id ORDER BY inicio, equipo_id LIMIT {int(limite)}"""
        with operacion(self.nombre, "resumen_ventana", ERRORES):
            filas = self._sql(consulta, params)
        return [{"inicio": f["inicio"] + "Z", "equipoId": f["equipo_id"], "muestras": f["muestras"],
                 "posesionMedia": f["posesion_media"], "tiros": f["tiros"],
                 "pasesAcumulados": f["pases_acumulados"]} for f in filas]
