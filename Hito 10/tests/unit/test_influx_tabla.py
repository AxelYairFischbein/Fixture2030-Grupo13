"""Una tabla de InfluxDB todavía no creada equivale a cero puntos, no a un error interno."""

from types import SimpleNamespace

import httpx
import pytest

from app.adapters.influx_estadisticas import InfluxEstadisticas


def _adaptador(respuesta: httpx.Response) -> InfluxEstadisticas:
    cfg = SimpleNamespace(influx_db="db", influx_url="http://influx", timeout=1, influx_token="t")
    a = InfluxEstadisticas(cfg)
    a._http = httpx.Client(base_url="http://influx", transport=httpx.MockTransport(lambda r: respuesta))
    return a


def test_tabla_inexistente_es_ventana_vacia():
    a = _adaptador(httpx.Response(400, text="Error during planning: table "
                                            "'public.iox.estadisticas_equipo_v2' not found"))
    assert a.ultimo_instante("PAR-001") is None


def test_otro_rechazo_sigue_siendo_error_interno():
    a = _adaptador(httpx.Response(400, text="Error during planning: syntax error"))
    with pytest.raises(RuntimeError):
        a.ultimo_instante("PAR-001")
