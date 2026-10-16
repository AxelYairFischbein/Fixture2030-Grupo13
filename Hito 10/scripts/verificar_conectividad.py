"""Verifica cada fuente con su adaptador, sin iniciar la API. No imprime hosts con credenciales ni secretos.

Uso: .venv\\Scripts\\python scripts\\verificar_conectividad.py   (código de salida 1 si alguna falla)
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config, contexto  # noqa: E402
from app.main import servicios_reales  # noqa: E402

logging.disable(logging.WARNING)
cfg = config.cargar()
destinos = {"mongodb": f"{cfg.mongo_host}:{cfg.mongo_port}/{cfg.mongo_db}",
            "neo4j": f"{cfg.neo4j_uri} (db {cfg.neo4j_database})",
            "cassandra": f"{','.join(cfg.cassandra_hosts)}:{cfg.cassandra_port}/{cfg.cassandra_keyspace}",
            "redis": f"{cfg.redis_host}:{cfg.redis_port} (prefijo {cfg.redis_prefix})",
            "influxdb": f"{cfg.influx_url} (db {cfg.influx_db}, token {'configurado' if cfg.influx_token else 'AUSENTE'})",
            "iris": f"{cfg.iris_host}:{cfg.iris_port}/{cfg.iris_namespace} (usuario {cfg.iris_user or 'AUSENTE'})"}
contexto.trazas.set([])
estados = servicios_reales(cfg).salud()
print(f"Timeout por operación: {cfg.timeout} s")
for e in estados:
    print(f"{e['estado']:<14} {e['ms']:>9.2f} ms  {e['fuente']:<10} {destinos[e['fuente']]}")
sys.exit(0 if all(e["estado"] == "ok" for e in estados) else 1)
