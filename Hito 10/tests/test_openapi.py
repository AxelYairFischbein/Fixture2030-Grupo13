"""El contrato versionado (openapi/openapi.yaml) coincide con app.openapi() (RNF2).

Se construye una app propia en lugar del fixture `app`, que agrega las rutas /prueba de
los manejadores y no forma parte del contrato.
"""

import pytest
import yaml

from app.config.settings import RAIZ_HITO10, Settings
from app.main import create_app
from app.openapi import normalizar
from app.schemas.errores import EJEMPLOS_ERROR

ARCHIVO = RAIZ_HITO10 / "openapi" / "openapi.yaml"
METODOS = {"get", "post", "put", "patch", "delete"}
CODIGOS_404_409 = {
    "EQUIPO_NO_ENCONTRADO", "JUGADOR_NO_ENCONTRADO", "PARTIDO_NO_ENCONTRADO",
    "ACTA_NO_ENCONTRADA", "COMENTARIO_NO_ENCONTRADO", "EQUIPO_NO_PARTICIPA",
    "TRANSICION_NO_PERMITIDA", "IDEMPOTENCY_KEY_REUTILIZADA",
}


@pytest.fixture(scope="module")
def contrato() -> dict:
    return normalizar(create_app(Settings(_env_file=None), iniciar_catalogo=False).openapi())


def _operaciones(esquema: dict):
    for ruta, operaciones in esquema["paths"].items():
        for metodo, operacion in operaciones.items():
            if metodo in METODOS:
                yield f"{metodo.upper()} {ruta}", operacion


def _diferencias(versionado, actual, ruta="") -> list[str]:
    if isinstance(versionado, dict) and isinstance(actual, dict):
        salida = []
        for clave in sorted(set(versionado) | set(actual), key=str):
            if clave not in actual:
                salida.append(f"{ruta}/{clave}: sobra en openapi.yaml")
            elif clave not in versionado:
                salida.append(f"{ruta}/{clave}: falta en openapi.yaml")
            else:
                salida += _diferencias(versionado[clave], actual[clave], f"{ruta}/{clave}")
        return salida
    return [] if versionado == actual else [f"{ruta}: distinto valor"]


def test_openapi_versionado_coincide_con_la_app(contrato):
    assert ARCHIVO.exists(), "Falta openapi/openapi.yaml: ejecutar scripts/exportar_openapi.ps1"
    versionado = yaml.safe_load(ARCHIVO.read_text(encoding="utf-8"))
    diferencias = _diferencias(versionado, contrato)
    assert not diferencias, (
        "openapi/openapi.yaml está desactualizado; regenerarlo con scripts/exportar_openapi.ps1:\n  "
        + "\n  ".join(diferencias[:20])
    )


def test_ninguna_operacion_declara_422(contrato):
    con_422 = [nombre for nombre, op in _operaciones(contrato) if "422" in op["responses"]]
    assert con_422 == []
    assert "HTTPValidationError" not in contrato["components"]["schemas"]


def test_cada_operacion_tiene_tag_summary_y_500(contrato):
    for nombre, operacion in _operaciones(contrato):
        assert operacion.get("tags"), f"{nombre} sin tags"
        assert operacion.get("summary"), f"{nombre} sin summary"
        assert "500" in operacion["responses"], f"{nombre} no declara 500 ERROR_INTERNO"


def test_cada_error_declarado_tiene_ejemplos_con_codigos_del_contrato(contrato):
    codigos_validos = {codigo for codigo, _, _ in EJEMPLOS_ERROR.values()}
    for nombre, operacion in _operaciones(contrato):
        for status, respuesta in operacion["responses"].items():
            if int(status) < 400:
                continue
            ejemplos = respuesta["content"]["application/json"]["examples"]
            assert ejemplos, f"{nombre} {status} sin ejemplos"
            for ejemplo in ejemplos.values():
                codigo = ejemplo["value"]["error"]["codigo"]
                assert codigo in codigos_validos, f"{nombre} {status}: {codigo} no está en §6.2"
                if status in ("404", "409"):
                    assert codigo in CODIGOS_404_409, f"{nombre} {status}: {codigo} genérico"


def test_contrato_cubre_los_casos_de_uso(contrato):
    resumenes = " ".join(op["summary"] for _, op in _operaciones(contrato))
    faltantes = [f"CU-{n:02d}" for n in range(1, 21) if f"CU-{n:02d}" not in resumenes]
    assert faltantes == []
