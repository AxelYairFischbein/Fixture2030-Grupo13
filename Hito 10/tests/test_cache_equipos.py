"""CU-01 con cache-aside: Redis (falso) delante de MongoDB (falso) y encabezado X-Cache."""

from app.errors import DependenciaNoDisponible, DependenciaTimeout

URL = "/api/v1/equipos/EQ-001"


def test_miss_y_despues_hit_sin_consultar_mongodb(client, mongo_falso, redis_falso):
    primera = client.get(URL)
    assert primera.status_code == 200
    assert primera.headers["X-Cache"] == "MISS"
    assert redis_falso.fichas["EQ-001"] == primera.json()

    mongo_falso.llamadas.clear()
    segunda = client.get(URL)
    assert segunda.status_code == 200
    assert segunda.headers["X-Cache"] == "HIT"
    assert segunda.json() == primera.json()
    assert mongo_falso.llamadas == []


def test_hit_responde_aunque_mongodb_este_caido(client, mongo_falso):
    client.get(URL)
    mongo_falso.falla = DependenciaNoDisponible("mongodb")
    respuesta = client.get(URL)
    assert respuesta.status_code == 200
    assert respuesta.headers["X-Cache"] == "HIT"


def test_redis_caido_responde_bypass_desde_mongodb(client, redis_falso):
    redis_falso.falla = DependenciaNoDisponible("redis")
    respuesta = client.get(URL)
    assert respuesta.status_code == 200
    assert respuesta.headers["X-Cache"] == "BYPASS"
    assert respuesta.json()["equipoId"] == "EQ-001"
    # En BYPASS no se intenta guardar la copia.
    assert redis_falso.llamadas == ["leer_ficha_cacheada"]


def test_redis_con_timeout_tambien_es_bypass(client, redis_falso):
    redis_falso.falla = DependenciaTimeout("redis")
    respuesta = client.get(URL)
    assert respuesta.status_code == 200
    assert respuesta.headers["X-Cache"] == "BYPASS"


def test_redis_y_mongodb_caidos_es_503(client, mongo_falso, redis_falso):
    redis_falso.falla = DependenciaNoDisponible("redis")
    mongo_falso.falla = DependenciaNoDisponible("mongodb")
    respuesta = client.get(URL)
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["codigo"] == "DEPENDENCIA_NO_DISPONIBLE"


def test_mongodb_con_timeout_y_miss_es_504(client, mongo_falso):
    mongo_falso.falla = DependenciaTimeout("mongodb")
    assert client.get(URL).status_code == 504


def test_falla_del_set_responde_igual_sin_confirmar_copia(client, redis_falso):
    redis_falso.falla_guardar = DependenciaTimeout("redis")
    respuesta = client.get(URL)
    assert respuesta.status_code == 200
    assert respuesta.headers["X-Cache"] == "MISS"
    assert "EQ-001" not in redis_falso.fichas


def test_equipo_inexistente_no_cachea_la_ausencia(client, redis_falso):
    respuesta = client.get("/api/v1/equipos/EQ-999")
    assert respuesta.status_code == 404
    assert "X-Cache" not in respuesta.headers
    assert redis_falso.fichas == {}
    assert "guardar_ficha_cacheada" not in redis_falso.llamadas


def test_formato_invalido_no_consulta_redis(client, redis_falso):
    assert client.get("/api/v1/equipos/EQ-1").status_code == 400
    assert redis_falso.llamadas == []


def test_invalidacion_hace_que_la_siguiente_lectura_sea_miss(client, mongo_falso, redis_falso):
    redis_falso.crear_sesion("SES-PRUEBA-OPER", rol="operador")
    client.get(URL)
    mongo_falso.equipos[0]["nombre"] = "Seleccion Sintetica 01 - ficha actualizada"
    assert client.get(URL).json()["nombre"] == "Seleccion Sintetica 01"  # copia vigente
    assert client.delete("/api/v1/cache/equipos/EQ-001",
                         headers={"X-Session-Id": "SES-PRUEBA-OPER"}).status_code == 204
    respuesta = client.get(URL)
    assert respuesta.headers["X-Cache"] == "MISS"
    assert respuesta.json()["nombre"] == "Seleccion Sintetica 01 - ficha actualizada"


def test_x_cache_declarado_en_openapi(client):
    operacion = client.get("/openapi.json").json()["paths"]["/api/v1/equipos/{equipoId}"]["get"]
    assert "X-Cache" in operacion["responses"]["200"]["headers"]
