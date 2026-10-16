"""Configuración de la API leída de variables de entorno y de Hito 10/.env.

Usuarios, contraseñas y la ruta del token no tienen valor por defecto: si faltan,
la API no arranca y el mensaje nombra la variable (nunca su valor). Los timeouts
usan como default los valores propuestos en casos_de_uso.md §6.3.
"""

from pathlib import Path

from pydantic import PositiveInt, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_HITO10 = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_HITO10 / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # MONGO_PASSWORD= vacío cuenta como faltante
        extra="ignore",
    )

    # General
    log_level: str = "INFO"

    # MongoDB (Hito 4)
    mongo_host: str = "127.0.0.1"
    mongo_port: int = 27017
    mongo_db: str = "fixture2030"
    mongo_user: str
    mongo_password: SecretStr
    mongo_auth_db: str = "admin"
    mongo_server_selection_timeout_s: float = 2.0
    mongo_socket_timeout_s: float = 3.0

    # Neo4j (Hito 5)
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_database: str = "neo4j"
    neo4j_user: str
    neo4j_password: SecretStr
    neo4j_connection_timeout_s: float = 2.0
    neo4j_tx_timeout_s: float = 3.0
    # Catálogo de partidos en memoria (casos_de_uso.md §3.2)
    catalogo_refresco_s: float = 600.0
    catalogo_reintento_s: float = 30.0

    # Cassandra (Hito 6): el contenedor no usa autenticación
    cassandra_hosts: str = "127.0.0.1"
    cassandra_port: int = 9042
    cassandra_keyspace: str = "fixture2030_comentarios"
    cassandra_dc: str = "datacenter1"
    cassandra_user: str | None = None
    cassandra_password: SecretStr | None = None
    cassandra_connect_timeout_s: float = 2.0
    cassandra_request_timeout_s: float = 2.0

    # Redis (Hito 7): el contenedor no usa contraseña
    redis_host: str = "127.0.0.1"
    redis_port: int = 16379
    redis_db: int = 0
    redis_prefijo: str = "fixture2030:h7:demo:"
    redis_password: SecretStr | None = None
    redis_connect_timeout_s: float = 0.5
    redis_socket_timeout_s: float = 0.5

    # InfluxDB 3 Core (Hito 8): se configura la ruta del token, no su valor
    influx_url: str = "http://127.0.0.1:8181"
    influx_database: str = "fixture2030_h8"
    influx_token_file: Path
    influx_timeout_s: float = 5.0
    # Cadencia de la serie del Hito 8 (una observación por segundo): define muestrasEsperadas
    # y la separación válida entre muestras consecutivas en CU-16 y CU-17.
    influx_paso_s: PositiveInt = 1

    # InterSystems IRIS (Hito 9)
    iris_host: str = "127.0.0.1"
    iris_port: int = 1972
    iris_namespace: str = "USER"
    iris_user: str
    iris_password: SecretStr
    iris_timeout_s: float = 3.0


def cargar_settings(**opciones) -> Settings:
    """Crea Settings o falla con un mensaje que nombra las variables con problemas."""
    try:
        return Settings(**opciones)
    except ValidationError as exc:
        problemas = []
        for error in exc.errors(include_input=False):
            variable = str(error["loc"][0]).upper() if error["loc"] else "?"
            if error["type"] == "missing":
                problemas.append(f"Falta la variable de entorno {variable}")
            else:
                problemas.append(f"La variable de entorno {variable} tiene un valor inválido")
        raise RuntimeError(
            "Configuración incompleta: " + "; ".join(problemas)
            + ". Copiar .env.example a .env y completarlo."
        ) from None
