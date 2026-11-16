"""Métricas HTTP por proceso, con rutas y métodos de cardinalidad acotada."""

from time import perf_counter

from prometheus_client import CollectorRegistry, Counter, Histogram


class Metricas:
    def __init__(self):
        self.registro = CollectorRegistry()
        self.requests = Counter(
            "fixture_http_requests_total", "Requests finalizados por estado HTTP.",
            ("method", "route", "status", "traffic"), registry=self.registro)
        self.duracion = Histogram(
            "fixture_http_request_duration_seconds", "Duración del procesamiento HTTP en segundos.",
            ("method", "route", "traffic"),
            buckets=(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10), registry=self.registro)


class MiddlewareMetricas:
    def __init__(self, app, metricas):
        self.app, self.metricas = app, metricas

    async def __call__(self, scope, receive, send):
        # Swagger, interfaz y scraping quedan fuera del tráfico de la API.
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/"):
            return await self.app(scope, receive, send)
        inicio, estado = perf_counter(), 500

        async def enviar(message):
            nonlocal estado
            if message["type"] == "http.response.start":
                estado = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, enviar)
        finally:
            ruta = getattr(scope.get("route"), "path", "__unmatched__")
            metodo = scope["method"]
            if metodo not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                metodo = "OTHER"
            trafico = "salud" if ruta == "/api/v1/salud" else "negocio"
            self.metricas.requests.labels(metodo, ruta, str(estado), trafico).inc()
            self.metricas.duracion.labels(metodo, ruta, trafico).observe(perf_counter() - inicio)
