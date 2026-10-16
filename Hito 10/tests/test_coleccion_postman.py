"""La colección de Postman cubre todas las operaciones del contrato y no lleva credenciales."""

import json
import re

import pytest

from app.config.settings import RAIZ_HITO10, Settings
from app.main import create_app

ARCHIVO = RAIZ_HITO10 / "postman" / "fixture2030_collection.json"
VARIABLES_DE_SESION = {"sesionLector", "sesionModerador", "sesionOperador"}


@pytest.fixture(scope="module")
def coleccion() -> dict:
    return json.loads(ARCHIVO.read_text(encoding="utf-8"))


def _requests(items):
    for item in items:
        if "item" in item:
            yield from _requests(item["item"])
        else:
            yield item


def _ruta(url: str) -> str:
    return url.removeprefix("{{baseUrl}}").split("?", 1)[0]


def test_cada_operacion_del_contrato_tiene_requests(coleccion):
    contrato = create_app(Settings(_env_file=None), iniciar_catalogo=False).openapi()
    enviadas = [(r["request"]["method"], _ruta(r["request"]["url"]))
                for r in _requests(coleccion["item"])]
    sin_cubrir = []
    for ruta, operaciones in contrato["paths"].items():
        patron = re.compile("^" + re.sub(r"\{[^}]+\}", r"[^/]+", ruta) + "$")
        for metodo in operaciones:
            if not any(m == metodo.upper() and patron.match(r) for m, r in enviadas):
                sin_cubrir.append(f"{metodo.upper()} {ruta}")
    assert sin_cubrir == []


def test_cada_caso_de_uso_tiene_exito_y_error(coleccion):
    for carpeta in coleccion["item"]:
        if not carpeta["name"].startswith("CU-"):
            continue
        esperados = set()
        for request in carpeta["item"]:
            prueba = "\n".join(e["script"]["exec"][0] for e in request["event"]
                               if e["listen"] == "test")
            esperados.add(int(re.search(r"HTTP (\d{3})", prueba).group(1)))
        assert any(c < 300 for c in esperados), f"{carpeta['name']} sin request exitosa"
        assert any(c >= 400 for c in esperados), f"{carpeta['name']} sin escenarios de error"


def test_no_contiene_ids_de_sesion(coleccion):
    texto = ARCHIVO.read_text(encoding="utf-8")
    assert not re.search(r"SES-PRUEBA-[0-9a-f]{8,}", texto)
    variables = {v["key"]: v["value"] for v in coleccion["variable"]}
    assert all(variables[nombre] == "" for nombre in VARIABLES_DE_SESION)
