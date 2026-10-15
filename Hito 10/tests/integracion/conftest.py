"""Fixtures comunes de las pruebas de integración contra los contenedores.

Settings se arma desde Hito 10/.env de forma explícita: el conftest raíz reemplaza
las variables de entorno por valores ficticios para las pruebas unitarias.
"""

import pytest
from dotenv import dotenv_values

from app.config.settings import RAIZ_HITO10, Settings


@pytest.fixture(scope="session")
def settings_reales() -> Settings:
    archivo = RAIZ_HITO10 / ".env"
    if not archivo.exists():
        pytest.skip("Falta Hito 10/.env con las credenciales locales")
    valores = {k.lower(): v for k, v in dotenv_values(archivo).items() if v}
    if "completar_localmente" in (valores.get("mongo_user"), valores.get("mongo_password")):
        pytest.skip("MONGO_USER / MONGO_PASSWORD de Hito 10/.env tienen el valor de relleno")
    return Settings(_env_file=None, **valores)
