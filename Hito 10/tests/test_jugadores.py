"""CU-04 con el adaptador MongoDB falso."""

import pytest

from app.errors import DependenciaNoDisponible, DependenciaTimeout


def test_ficha_de_jugador(client):
    respuesta = client.get("/api/v1/jugadores/JUG-0001")
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "jugadorId": "JUG-0001", "equipoId": "EQ-001", "nombre": "Nombre0001",
        "apellido": "Zeta", "fechaNacimiento": "1998-03-12", "nacionalidadCodigo": "S01",
        "posicion": "ARQUERO", "numeroCamiseta": 1, "pieHabil": "DERECHO", "alturaCm": 180,
        "partidosInternacionales": 10, "golesInternacionales": 1, "estadoPlantel": "CONVOCADO",
    }


def test_jugador_inexistente(client):
    respuesta = client.get("/api/v1/jugadores/JUG-9999")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "JUGADOR_NO_ENCONTRADO"


@pytest.mark.parametrize("jugador_id", ["JUG-12", "JUG-00001", "EQ-0001"])
def test_formato_invalido_no_consulta(client, mongo_falso, jugador_id):
    respuesta = client.get(f"/api/v1/jugadores/{jugador_id}")
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"
    assert mongo_falso.llamadas == []


@pytest.mark.parametrize("falla, http_status", [
    (DependenciaNoDisponible("mongodb"), 503), (DependenciaTimeout("mongodb"), 504),
])
def test_dependencia_caida(client, mongo_falso, falla, http_status):
    mongo_falso.falla = falla
    assert client.get("/api/v1/jugadores/JUG-0001").status_code == http_status
