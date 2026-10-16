"""AdaptadorCassandra sin Docker: modelo del Hito 6, fusión de particiones y traducción de errores.

La sesión falsa ejecuta las sentencias preparadas del adaptador sobre filas en memoria
respetando lo que haría Cassandra: IN de particiones, rango de creado_en, orden de
clustering por partición y PER PARTITION LIMIT (sin orden global).
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from cassandra import (
    AuthenticationFailed,
    InvalidRequest,
    OperationTimedOut,
    ReadTimeout,
    Unavailable,
    WriteTimeout,
    WriteType,
)
from cassandra.cluster import NoHostAvailable
from cassandra.query import BatchType

from app.adapters import cassandra_adaptador
from app.adapters.cassandra_adaptador import (
    AdaptadorCassandra,
    clave_de_orden,
    minuto_de,
    minutos_que_intersectan,
    segmento,
)
from app.config.settings import Settings
from app.errors import DependenciaNoDisponible, DependenciaTimeout, ErrorDominio


def _t(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=UTC)


def _fila(comentario_id: str, creado: str, estado: str = "visible", partido_id: str = "PAR-001",
          usuario_id: str = "USR-00001", seg: int | None = None) -> dict:
    """Fila como la devuelve el driver: timestamps naive en UTC."""
    creado_en = _t(creado)
    return {
        "partido_id": partido_id, "minuto": minuto_de(creado_en).replace(tzinfo=None),
        "segmento": segmento(comentario_id) if seg is None else seg,
        "creado_en": creado_en.replace(tzinfo=None), "comentario_id": comentario_id,
        "usuario_id": usuario_id, "dia": creado_en.date(), "contenido": "texto",
        "estado": estado, "likes": 0,
    }


class Resultado(list):
    def one(self):
        return self[0] if self else None


class Ligada:
    def __init__(self, cql, parametros):
        self.cql, self.parametros, self.fetch_size = cql, parametros, None


class Preparada:
    def __init__(self, cql):
        self.cql = cql

    def bind(self, parametros):
        return Ligada(self.cql, parametros)


class BatchFalso:
    creados: list["BatchFalso"] = []

    def __init__(self, batch_type):
        self.batch_type = batch_type
        self.sentencias: list[tuple[str, tuple]] = []
        BatchFalso.creados.append(self)

    def add(self, preparada, parametros):
        self.sentencias.append((preparada.cql, parametros))


class SesionFalsa:
    def __init__(self, filas: list[dict] | None = None, falla: Exception | None = None):
        self.filas = filas or []
        self.falla = falla
        self.ejecutadas: list = []

    def prepare(self, cql):
        return Preparada(cql)

    @staticmethod
    def _utc(valor):
        return valor.replace(tzinfo=UTC)

    def execute(self, sentencia):
        self.ejecutadas.append(sentencia)
        if self.falla is not None:
            raise self.falla
        if isinstance(sentencia, (str, BatchFalso)):
            return Resultado()
        p = sentencia.parametros
        if sentencia.cql == cassandra_adaptador.SEL_PARTIDO:
            partido, minutos, segmentos, desde, tope, k = p
            por_particion: dict = {}
            for f in self.filas:
                if (f["partido_id"] == partido and self._utc(f["minuto"]) in minutos
                        and f["segmento"] in segmentos and desde <= self._utc(f["creado_en"]) < tope):
                    por_particion.setdefault((f["minuto"], f["segmento"]), []).append(f)
            resultado = Resultado()
            for filas in por_particion.values():  # orden de partición arbitrario
                filas.sort(key=lambda f: clave_de_orden(self._utc(f["creado_en"]), f["comentario_id"]))
                resultado.extend(dict(f) for f in filas[:k])
            return resultado
        if sentencia.cql == cassandra_adaptador.SEL_USUARIO:
            usuario, dia, tope = p
            filas = [dict(f) for f in self.filas if f["usuario_id"] == usuario and f["dia"] == dia
                     and self._utc(f["creado_en"]) < tope]
            filas.sort(key=lambda f: clave_de_orden(self._utc(f["creado_en"]), f["comentario_id"]))
            return Resultado(filas)
        if sentencia.cql == cassandra_adaptador.SEL_CLAVE_PARTIDO:
            partido, minuto, seg, creado_en, comentario_id = p
            return Resultado(dict(f) for f in self.filas if (
                f["partido_id"], self._utc(f["minuto"]), f["segmento"], self._utc(f["creado_en"]),
                f["comentario_id"]) == (partido, minuto, seg, creado_en, comentario_id))
        raise AssertionError(f"sentencia inesperada: {sentencia.cql}")

    def consultas(self, cql: str) -> list[Ligada]:
        return [s for s in self.ejecutadas if isinstance(s, Ligada) and s.cql == cql]


def _adaptador(sesion: SesionFalsa) -> AdaptadorCassandra:
    return AdaptadorCassandra(Settings(_env_file=None), sesion=sesion)


def _ids(filas: list[dict]) -> list[str]:
    return [f["comentario_id"] for f in filas]


# Muestra del Hito 6 (carga_muestra.cql) para PAR-001
MUESTRA = [
    _fila("MUESTRA-001", "2030-06-10T18:00:20", "visible"),
    _fila("MUESTRA-002", "2030-06-10T18:00:30", "pendiente", usuario_id="USR-00002"),
    _fila("MUESTRA-003", "2030-06-10T18:00:55", "visible"),
    _fila("MUESTRA-004", "2030-06-10T18:01:05", "oculto", usuario_id="USR-00003"),
    _fila("MUESTRA-005", "2030-06-10T18:01:20", "visible"),
    _fila("MUESTRA-006", "2030-06-10T18:01:20", "visible", usuario_id="USR-00002"),
    _fila("MUESTRA-007", "2030-06-10T18:01:45", "pendiente", usuario_id="USR-00003"),
    _fila("MUESTRA-008", "2030-06-10T18:01:59", "visible"),
    _fila("MUESTRA-009", "2030-06-10T18:02:05", "visible", usuario_id="USR-00002"),
    _fila("MUESTRA-010", "2030-06-10T18:02:10", "visible"),
]


# Modelo del Hito 6

def test_segmento_coincide_con_la_muestra_del_hito6():
    # carga_muestra.cql: MUESTRA-001 → 2, 002 → 0, 004 → 1, 005 → 3, 011 → 3, 012 → 1.
    esperados = {"MUESTRA-001": 2, "MUESTRA-002": 0, "MUESTRA-004": 1, "MUESTRA-005": 3,
                 "MUESTRA-011": 3, "MUESTRA-012": 1}
    assert {c: segmento(c) for c in esperados} == esperados


def test_minutos_que_intersectan_la_ventana():
    assert minutos_que_intersectan(_t("2030-06-10T18:00:30"), _t("2030-06-10T18:02:10")) == [
        _t("2030-06-10T18:00:00"), _t("2030-06-10T18:01:00"), _t("2030-06-10T18:02:00")]
    # Una ventana de 5 minutos desalineada toca como máximo 6 minutos (24 particiones).
    assert len(minutos_que_intersectan(_t("2030-06-10T18:00:30"), _t("2030-06-10T18:05:30"))) == 6
    # El extremo superior es excluido: [18:00, 18:01) es un solo minuto.
    assert minutos_que_intersectan(_t("2030-06-10T18:00:00"), _t("2030-06-10T18:01:00")) == [
        _t("2030-06-10T18:00:00")]


def test_sentencias_fijas_sin_allow_filtering_y_por_clave_de_particion():
    for cql in cassandra_adaptador.SENTENCIAS.values():
        assert "ALLOW FILTERING" not in cql.upper()
        assert "?" in cql
    assert "partido_id = ? AND minuto IN ? AND segmento IN ?" in cassandra_adaptador.SEL_PARTIDO
    assert "PER PARTITION LIMIT ?" in cassandra_adaptador.SEL_PARTIDO
    assert "usuario_id = ? AND dia = ?" in cassandra_adaptador.SEL_USUARIO


# CU-08: fusión de particiones

def test_q1_minuto_todos_los_estados_orden_global():
    sesion = SesionFalsa(MUESTRA)
    filas, siguiente = _adaptador(sesion).leer_por_partido(
        "PAR-001", _t("2030-06-10T18:01:00"), _t("2030-06-10T18:02:00"), None, 20, False)
    # consultas.cql Q1: creado_en DESC, comentario_id ASC (005 antes que 006 en el mismo ms).
    assert _ids(filas) == ["MUESTRA-008", "MUESTRA-007", "MUESTRA-005", "MUESTRA-006", "MUESTRA-004"]
    assert siguiente is None
    assert all(f["creado_en"].tzinfo is UTC for f in filas)
    (consulta,) = sesion.consultas(cassandra_adaptador.SEL_PARTIDO)
    assert consulta.parametros[1] == [_t("2030-06-10T18:01:00")]
    assert consulta.parametros[2] == [0, 1, 2, 3]
    assert consulta.parametros[5] == 21  # PER PARTITION LIMIT = limite + 1


def test_q1_solo_visibles():
    filas, _ = _adaptador(SesionFalsa(MUESTRA)).leer_por_partido(
        "PAR-001", _t("2030-06-10T18:01:00"), _t("2030-06-10T18:02:00"), None, 20, True)
    assert _ids(filas) == ["MUESTRA-008", "MUESTRA-005", "MUESTRA-006"]


def test_q2_ventana_entre_minutos_coincide_con_consultas_cql():
    filas, siguiente = _adaptador(SesionFalsa(MUESTRA)).leer_por_partido(
        "PAR-001", _t("2030-06-10T18:00:30"), _t("2030-06-10T18:02:10"), None, 50, False)
    assert _ids(filas) == ["MUESTRA-009", "MUESTRA-008", "MUESTRA-007", "MUESTRA-005",
                           "MUESTRA-006", "MUESTRA-004", "MUESTRA-003", "MUESTRA-002"]
    assert siguiente is None


def test_limite_global_y_cursor_con_empate_en_el_mismo_milisegundo():
    adaptador = _adaptador(SesionFalsa(MUESTRA))
    desde, hasta = _t("2030-06-10T18:01:00"), _t("2030-06-10T18:02:00")
    pagina1, cursor = adaptador.leer_por_partido("PAR-001", desde, hasta, None, 3, False)
    assert _ids(pagina1) == ["MUESTRA-008", "MUESTRA-007", "MUESTRA-005"]
    assert cursor == (_t("2030-06-10T18:01:20"), "MUESTRA-005")
    pagina2, cursor2 = adaptador.leer_por_partido("PAR-001", desde, hasta, cursor, 3, False)
    assert _ids(pagina2) == ["MUESTRA-006", "MUESTRA-004"]  # 006 comparte el ms con 005
    assert cursor2 is None


def test_cursor_acota_la_consulta_al_milisegundo_siguiente():
    sesion = SesionFalsa(MUESTRA)
    _adaptador(sesion).leer_por_partido(
        "PAR-001", _t("2030-06-10T18:01:00"), _t("2030-06-10T18:02:00"),
        (_t("2030-06-10T18:01:20"), "MUESTRA-005"), 3, False)
    (consulta,) = sesion.consultas(cassandra_adaptador.SEL_PARTIDO)
    assert consulta.parametros[4] == _t("2030-06-10T18:01:20") + timedelta(milliseconds=1)


def test_filtro_visible_hace_otra_ronda_si_una_particion_saturada_oculta_filas():
    # Partición A (segmento 0): dos ocultos recientes y un visible más viejo.
    # Partición B (segmento 1): un visible todavía más viejo. Con limite=1 (k=2) la primera
    # ronda solo es exacta hasta la segunda fila de A: devolver B sería un error de orden.
    filas = [
        _fila("A-50", "2030-06-10T18:01:50", "oculto", seg=0),
        _fila("A-40", "2030-06-10T18:01:40", "oculto", seg=0),
        _fila("A-30", "2030-06-10T18:01:30", "visible", seg=0),
        _fila("B-10", "2030-06-10T18:01:10", "visible", seg=1),
    ]
    sesion = SesionFalsa(filas)
    resultado, siguiente = _adaptador(sesion).leer_por_partido(
        "PAR-001", _t("2030-06-10T18:01:00"), _t("2030-06-10T18:02:00"), None, 1, True)
    assert _ids(resultado) == ["A-30"]
    assert siguiente == (_t("2030-06-10T18:01:30"), "A-30")
    # Varias rondas (la fila del cursor también ocupa lugar en el PER PARTITION LIMIT).
    assert 2 <= len(sesion.consultas(cassandra_adaptador.SEL_PARTIDO)) <= cassandra_adaptador.MAX_RONDAS


def test_rondas_agotadas_devuelven_cursor_de_la_frontera(monkeypatch):
    monkeypatch.setattr(cassandra_adaptador, "MAX_RONDAS", 1)
    filas = [
        _fila("A-50", "2030-06-10T18:01:50", "oculto", seg=0),
        _fila("A-40", "2030-06-10T18:01:40", "oculto", seg=0),
        _fila("A-30", "2030-06-10T18:01:30", "visible", seg=0),
    ]
    resultado, siguiente = _adaptador(SesionFalsa(filas)).leer_por_partido(
        "PAR-001", _t("2030-06-10T18:01:00"), _t("2030-06-10T18:02:00"), None, 1, True)
    assert resultado == []
    assert siguiente == (_t("2030-06-10T18:01:40"), "A-40")  # se sigue sin perder A-30


def test_particiones_vacias_son_lista_vacia():
    filas, siguiente = _adaptador(SesionFalsa(MUESTRA)).leer_por_partido(
        "PAR-001", _t("2030-06-10T19:00:00"), _t("2030-06-10T19:01:00"), None, 20, False)
    assert (filas, siguiente) == ([], None)


# CU-10

def test_q3_historial_de_una_particion_con_cursor():
    sesion = SesionFalsa(MUESTRA)
    adaptador = _adaptador(sesion)
    pagina1, cursor = adaptador.leer_por_usuario("USR-00001", date(2030, 6, 10), None, 2)
    # USR-00001 en PAR-001: 001, 003, 005, 008, 010
    assert _ids(pagina1) == ["MUESTRA-010", "MUESTRA-008"]
    assert cursor == (_t("2030-06-10T18:01:59"), "MUESTRA-008")
    pagina2, cursor2 = adaptador.leer_por_usuario("USR-00001", date(2030, 6, 10), cursor, 5)
    assert _ids(pagina2) == ["MUESTRA-005", "MUESTRA-003", "MUESTRA-001"]
    assert cursor2 is None
    primera, segunda = sesion.consultas(cassandra_adaptador.SEL_USUARIO)
    assert primera.fetch_size == 3
    assert primera.parametros == ("USR-00001", date(2030, 6, 10), _t("2030-06-11T00:00:00"))


# CU-09 y CU-20

def test_leer_comentario_por_clave_completa_deriva_minuto_y_segmento():
    sesion = SesionFalsa(MUESTRA)
    adaptador = _adaptador(sesion)
    fila = adaptador.leer_comentario("PAR-001", _t("2030-06-10T18:01:05"), "MUESTRA-004")
    assert (fila["estado"], fila["usuario_id"], fila["dia"]) == ("oculto", "USR-00003", date(2030, 6, 10))
    (consulta,) = sesion.consultas(cassandra_adaptador.SEL_CLAVE_PARTIDO)
    assert consulta.parametros == ("PAR-001", _t("2030-06-10T18:01:00"), 1,
                                   _t("2030-06-10T18:01:05"), "MUESTRA-004")
    assert adaptador.leer_comentario("PAR-001", _t("2030-06-10T18:01:06"), "MUESTRA-004") is None


def test_insertar_es_batch_registrado_sobre_las_dos_tablas(monkeypatch):
    monkeypatch.setattr(cassandra_adaptador, "BatchStatement", BatchFalso)
    BatchFalso.creados = []
    sesion = SesionFalsa()
    creado_en = datetime(2030, 6, 10, 21, 30, 15, 123000, tzinfo=UTC)
    _adaptador(sesion).insertar_comentario({
        "partido_id": "PAR-001", "creado_en": creado_en, "comentario_id": "MUESTRA-001",
        "usuario_id": "USR-00001", "contenido": "Hola", "estado": "visible", "likes": 0,
    })
    (batch,) = BatchFalso.creados
    assert batch.batch_type == BatchType.LOGGED
    assert [cql for cql, _ in batch.sentencias] == [cassandra_adaptador.INS_PARTIDO,
                                                    cassandra_adaptador.INS_USUARIO]
    esperado = ("PAR-001", datetime(2030, 6, 10, 21, 30, tzinfo=UTC), 2, creado_en, "MUESTRA-001",
                "USR-00001", date(2030, 6, 10), "Hola", "visible", 0)
    assert all(parametros == esperado for _, parametros in batch.sentencias)
    assert sesion.ejecutadas == [batch]


def test_actualizar_estado_usa_usuario_y_dia_de_la_fila_leida(monkeypatch):
    monkeypatch.setattr(cassandra_adaptador, "BatchStatement", BatchFalso)
    BatchFalso.creados = []
    sesion = SesionFalsa(MUESTRA)
    adaptador = _adaptador(sesion)
    fila = adaptador.leer_comentario("PAR-001", _t("2030-06-10T18:01:05"), "MUESTRA-004")
    adaptador.actualizar_estado(fila, "visible")
    (batch,) = BatchFalso.creados
    assert batch.batch_type == BatchType.LOGGED
    assert batch.sentencias == [
        (cassandra_adaptador.UPD_ESTADO_PARTIDO, ("visible", "PAR-001", _t("2030-06-10T18:01:00"), 1,
                                                  _t("2030-06-10T18:01:05"), "MUESTRA-004")),
        (cassandra_adaptador.UPD_ESTADO_USUARIO, ("visible", "USR-00003", date(2030, 6, 10),
                                                  _t("2030-06-10T18:01:05"), "MUESTRA-004")),
    ]


# Traducción de excepciones

@pytest.mark.parametrize("falla, esperada", [
    (NoHostAvailable("sin nodos", {}), DependenciaNoDisponible),
    (Unavailable("sin réplicas"), DependenciaNoDisponible),
    (ReadTimeout("lectura"), DependenciaTimeout),
    (WriteTimeout("escritura", write_type=WriteType.BATCH), DependenciaTimeout),
    (OperationTimedOut("cliente"), DependenciaTimeout),
    (InvalidRequest("keyspace inexistente"), ErrorDominio),
    (NoHostAvailable("auth", {"127.0.0.1": AuthenticationFailed("credenciales")}), ErrorDominio),
])
def test_traduce_excepciones_del_driver(falla, esperada):
    adaptador = _adaptador(SesionFalsa(falla=falla))
    with pytest.raises(esperada) as exc:
        adaptador.leer_por_usuario("USR-00001", date(2030, 6, 10), None, 20)
    assert type(exc.value) is esperada
    if esperada is not ErrorDominio:
        assert exc.value.dependencia == "cassandra"
    assert "credenciales" not in exc.value.mensaje and "keyspace" not in exc.value.mensaje
    assert adaptador.ping() is False


def test_servidor_inaccesible_es_dependencia_no_disponible():
    # Driver real contra un puerto cerrado: NoHostAvailable al conectar → 503.
    settings = Settings(_env_file=None, cassandra_port=1, cassandra_connect_timeout_s=0.5)
    adaptador = AdaptadorCassandra(settings)
    try:
        with pytest.raises(DependenciaNoDisponible):
            adaptador.leer_por_usuario("USR-00001", date(2030, 6, 10), None, 20)
        # El siguiente uso vuelve a intentar con un Cluster nuevo (no queda roto).
        assert adaptador.ping() is False
    finally:
        adaptador.cerrar()
