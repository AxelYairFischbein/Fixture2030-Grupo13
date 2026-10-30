"""Acotación del cursor con un doble de sesión. La conexión real se evalúa en Hito 12."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.adapters.cassandra_comentarios import CassandraComentarios, SEGMENTOS


def test_cursor_busca_empates_solo_en_su_minuto_y_completa_la_pagina():
    instante = datetime(2030, 6, 10, 18, 4, 3, tzinfo=timezone.utc)
    desde, hasta = instante.replace(minute=0, second=0), instante.replace(minute=5, second=0)
    minutos = [desde + timedelta(minutes=n) for n in range(5)]
    llamadas = []

    def ejecutar(sentencia, parametros):
        llamadas.append((sentencia, parametros))
        return [SimpleNamespace(comentario_id="B" if sentencia == "empate" else "A",
                                creado_en=instante if sentencia == "empate" else instante - timedelta(seconds=1),
                                usuario_id="USR-00001", contenido="prueba", estado="visible", likes=0)]

    a = CassandraComentarios(None)
    a._conectar = lambda: SimpleNamespace(execute=ejecutar)
    a._empate, a._ventana = "empate", "ventana"
    filas = a.listar("PAR-001", minutos, desde, hasta, 2, (instante, "A"))
    assert [f["comentarioId"] for f in filas] == ["B", "A"]
    assert llamadas[0][1] == ("PAR-001", [instante.replace(second=0)], SEGMENTOS, instante, "A", 2)
    assert llamadas[1][1] == ("PAR-001", minutos, SEGMENTOS, desde, instante, 1)

    llamadas.clear()
    a.listar("PAR-001", minutos, desde, hasta, 1, (instante, "A"))
    assert len(llamadas) == 1  # Los empates ya completaron la página.
    llamadas.clear()
    a.listar("PAR-001", minutos, desde, hasta, 2, None)
    assert llamadas == [("ventana", ("PAR-001", minutos, SEGMENTOS, desde, hasta, 2))]
