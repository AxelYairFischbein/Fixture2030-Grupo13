"""Contrato HTTP y aislamiento de etiquetas sin conexiones a las bases."""

from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from app.errors import DependenciaNoDisponible
from app.main import crear_app


def test_metricas_conservan_http_y_no_publican_identificadores():
    app = crear_app(servicios=object())

    @app.get("/api/v1/prueba/{identificador}")
    def prueba(identificador: int):
        if identificador == 503:
            raise DependenciaNoDisponible("redis")
        if identificador == 500:
            raise RuntimeError("detalle privado")
        return {"id": identificador}

    with TestClient(app) as cliente:
        for identificador, esperado in [(123456, 200), (987654, 200), (503, 503), (500, 500), ("invalido", 400)]:
            r = cliente.get(f"/api/v1/prueba/{identificador}", headers={"X-Request-ID": "peticion-privada"})
            assert r.status_code == esperado
            assert r.headers["X-Request-ID"] == "peticion-privada"
        assert cliente.get("/api/v1/desconocida-secreta").status_code == 404
        assert cliente.post("/api/v1/prueba/123456").status_code == 405
        # El chequeo de salud fallará con este doble, pero se clasifica aparte.
        assert cliente.get("/api/v1/salud").status_code == 500
        primero = cliente.get("/metrics")
        assert primero.status_code == 200 and "text/plain" in primero.headers["content-type"]
        assert cliente.get("/metrics").text == primero.text
        assert "/metrics" not in cliente.get("/openapi.json").json()["paths"]
    texto = primero.text
    assert all(v not in texto for v in ("123456", "987654", "peticion-privada", "secreta", "detalle privado"))
    muestras = [s for f in text_string_to_metric_families(texto) for s in f.samples]
    contadores = [s for s in muestras if s.name == "fixture_http_requests_total"]
    assert sum(s.value for s in contadores) == 8
    assert sum(s.value for s in contadores if s.labels["traffic"] == "negocio") == 7
    assert {s.labels["status"] for s in contadores} == {"200", "400", "404", "405", "500", "503"}
    assert sum(s.value for s in muestras if s.name == "fixture_http_request_duration_seconds_count") == 8
    # Una segunda aplicación no comparte ni duplica colectores.
    assert "fixture_http_requests_total{" not in TestClient(crear_app(servicios=object())).get("/metrics").text
