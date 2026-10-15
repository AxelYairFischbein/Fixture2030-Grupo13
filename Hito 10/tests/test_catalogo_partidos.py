"""Catálogo de partidos en memoria (casos_de_uso.md §3.2) con una fuente falsa y un reloj falso."""

import time

import pytest

from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, NoEncontrado
from app.services.catalogo_partidos import CatalogoPartidos
from tests.falsos import Neo4jFalso


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


@pytest.fixture
def fuente() -> Neo4jFalso:
    return Neo4jFalso()


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def catalogo(fuente, reloj) -> CatalogoPartidos:
    return CatalogoPartidos(fuente, Settings(_env_file=None), reloj=reloj)


def _cargas(fuente: Neo4jFalso) -> int:
    return fuente.llamadas.count("cargar_catalogo_partidos")


def test_carga_correcta(catalogo):
    assert catalogo.cargar() is True
    estado = catalogo.estado()
    assert estado["estado"] == "cargado"
    assert estado["partidos"] == 3
    assert estado["ultimaCarga"] is not None
    assert catalogo.validar_partido("PAR-001") == ("EQ-001", "EQ-002")


def test_partido_fuera_del_catalogo_es_404(catalogo):
    catalogo.cargar()
    with pytest.raises(NoEncontrado) as exc:
        catalogo.validar_partido("PAR-999")
    assert exc.value.codigo == "PARTIDO_NO_ENCONTRADO"


def test_equipo_que_no_disputa_el_partido_es_404(catalogo):
    catalogo.cargar()
    catalogo.validar_participacion("PAR-001", "EQ-002")
    with pytest.raises(NoEncontrado) as exc:
        catalogo.validar_participacion("PAR-001", "EQ-003")
    assert exc.value.codigo == "EQUIPO_NO_PARTICIPA"
    with pytest.raises(NoEncontrado) as exc:
        catalogo.validar_participacion("PAR-999", "EQ-001")
    assert exc.value.codigo == "PARTIDO_NO_ENCONTRADO"


@pytest.mark.parametrize("falla", [DependenciaNoDisponible("neo4j"), DependenciaTimeout("neo4j")])
def test_neo4j_caido_al_iniciar_deja_no_cargado_y_responde_503(catalogo, fuente, falla):
    fuente.falla = falla
    assert catalogo.cargar() is False
    assert catalogo.estado() == {"estado": "no_cargado", "partidos": 0, "ultimaCarga": None}
    # Ni 200 ni 404: no se puede saber si el partido existe.
    with pytest.raises(DependenciaNoDisponible):
        catalogo.validar_partido("PAR-001")


def test_reintento_como_maximo_cada_30_s(catalogo, fuente, reloj):
    fuente.falla = DependenciaNoDisponible("neo4j")
    catalogo.cargar()
    assert _cargas(fuente) == 1

    reloj.ahora += 10
    with pytest.raises(DependenciaNoDisponible):
        catalogo.validar_partido("PAR-001")
    assert _cargas(fuente) == 1  # dentro de los 30 s no se reintenta

    reloj.ahora += 20
    with pytest.raises(DependenciaNoDisponible):
        catalogo.validar_partido("PAR-001")
    assert _cargas(fuente) == 2  # a los 30 s sí, y falla otra vez

    fuente.falla = None
    reloj.ahora += 5
    with pytest.raises(DependenciaNoDisponible):
        catalogo.validar_partido("PAR-001")
    assert _cargas(fuente) == 2

    reloj.ahora += 25
    assert catalogo.validar_partido("PAR-001") == ("EQ-001", "EQ-002")
    assert _cargas(fuente) == 3
    assert catalogo.estado()["estado"] == "cargado"


def test_sin_intento_previo_carga_en_la_primera_request(catalogo, fuente):
    assert catalogo.validar_partido("PAR-033") == ("EQ-001", "EQ-003")
    assert _cargas(fuente) == 1


def test_cargado_no_consulta_neo4j_por_request(catalogo, fuente):
    catalogo.cargar()
    fuente.falla = DependenciaNoDisponible("neo4j")
    for _ in range(5):
        catalogo.validar_partido("PAR-001")
    assert _cargas(fuente) == 1


def test_refresco_fallido_conserva_el_ultimo_catalogo(catalogo, fuente):
    catalogo.cargar()
    ultima = catalogo.estado()["ultimaCarga"]
    fuente.falla = DependenciaNoDisponible("neo4j")
    assert catalogo.cargar() is False
    assert catalogo.estado() == {"estado": "cargado", "partidos": 3, "ultimaCarga": ultima}
    assert catalogo.validar_partido("PAR-002") == ("EQ-003", "EQ-004")


def test_refresco_incorpora_partidos_nuevos(catalogo, fuente):
    catalogo.cargar()
    nuevo = dict(fuente.partidos[0], partidoId="PAR-064", local="EQ-004", visitante="EQ-005")
    fuente.partidos.append(nuevo)
    with pytest.raises(NoEncontrado):
        catalogo.validar_partido("PAR-064")
    catalogo.cargar()
    assert catalogo.validar_partido("PAR-064") == ("EQ-004", "EQ-005")


def test_iniciar_carga_y_refresca_en_segundo_plano(fuente):
    catalogo = CatalogoPartidos(fuente, Settings(_env_file=None, catalogo_refresco_s=0.01))
    catalogo.iniciar()
    try:
        assert catalogo.estado()["estado"] == "cargado"
        for _ in range(200):
            if _cargas(fuente) >= 3:
                break
            time.sleep(0.01)
        assert _cargas(fuente) >= 3
    finally:
        catalogo.detener()
    cargas = _cargas(fuente)
    time.sleep(0.05)
    assert _cargas(fuente) == cargas  # detener() frena el hilo


def test_iniciar_con_neo4j_caido_no_lanza(fuente):
    fuente.falla = DependenciaNoDisponible("neo4j")
    catalogo = CatalogoPartidos(fuente, Settings(_env_file=None))
    catalogo.iniciar()
    try:
        assert catalogo.estado()["estado"] == "no_cargado"
    finally:
        catalogo.detener()
