"""Fallos de recuperación y evidencia parcial, sin detener servicios reales."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import demo


class FinalizacionTest(unittest.TestCase):
    def test_recuperacion_y_limpieza_fallan_pero_se_guarda_todo(self):
        resultado = {"completa": True, "fallos": [{"etapa": "ejecucion", "tipo": "ValueError"}]}
        guardar = Mock()
        with patch.object(demo, "recuperar_redis", side_effect=RuntimeError("dato privado")), \
                patch.object(demo, "http", side_effect=OSError("SES-secreto")) as http:
            demo.finalizar(resultado, "SES-secreto", True, guardar)
        http.assert_called_once()
        guardar.assert_called_once()
        self.assertFalse(resultado["completa"])
        self.assertEqual([e["etapa"] for e in resultado["fallos"]],
                         ["ejecucion", "recuperacion_final", "cierre_sesion"])
        self.assertNotIn("secreto", json.dumps(resultado))
        self.assertIn("fin", resultado)

    def test_cierre_no_exitoso_impide_completa(self):
        resultado = {"completa": True, "fallos": []}
        guardar = Mock()
        with patch.object(demo, "http", return_value={"status": 503}):
            demo.finalizar(resultado, "SES-secreto", False, guardar)
        self.assertFalse(resultado["completa"])
        self.assertEqual(resultado["fallos"], [{"etapa": "cierre_sesion", "status": 503}])
        guardar.assert_called_once()

    def test_recuperacion_confirmada_y_cierre_exitoso(self):
        resultado = {"completa": True, "fallos": []}
        with patch.object(demo, "recuperar_redis") as recuperar, \
                patch.object(demo, "http", return_value={"status": 204}):
            demo.finalizar(resultado, "SES-secreto", True, Mock())
        recuperar.assert_called_once()
        self.assertTrue(resultado["completa"])
        self.assertEqual(resultado["recuperacion_final"], "PONG")

    def test_no_se_reemplaza_el_error_original_y_se_guarda(self):
        original = ValueError("detalle que no debe publicarse")
        with tempfile.TemporaryDirectory() as carpeta, patch.object(demo, "verificar", side_effect=original):
            salida = Path(carpeta) / "intento"
            with self.assertRaises(ValueError) as obtenido:
                demo.ejecutar(salida, True)
            self.assertIs(obtenido.exception, original)
            resultado = json.loads((salida / "demostracion.json").read_text(encoding="utf-8"))
        self.assertFalse(resultado["completa"])
        self.assertEqual(resultado["fallos"], [{"etapa": "ejecucion", "tipo": "ValueError"}])
        self.assertNotIn("detalle", json.dumps(resultado))

    def test_redis_iniciado_sin_ping_no_cuenta_como_recuperado(self):
        with patch.object(demo.subprocess, "run", return_value=Mock(returncode=0, stdout="")), \
                patch.object(demo.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "no se recuperó"):
                demo.recuperar_redis()

    def test_series_presentes_no_demuestran_caida(self):
        fase = {"inesperados": [], "observacion": {
            "targets": [{"labels": {"job": j}, "health": "up"} for j in ("fixture-api", "mongodb", "redis", "prometheus")],
            "consultas": [{"panel": 2, "leyenda": base, "resultado": {"result": [{"value": [1, "1"]}]}}
                          for base in ("MongoDB", "Redis")]}}
        with self.assertRaisesRegex(RuntimeError, "exporter"):
            demo.comprobar_fase(fase, True)

    def test_espera_con_carga_hasta_activacion_o_resolucion(self):
        tramo = {"estados_http": {"200": 2}, "cache": {"HIT": 1}, "inesperados": [],
                 "ejemplos": {}, "errores_deliberados": [404]}
        for caida, motivo in [(True, "Las alertas esperadas no llegaron a firing"),
                              (False, "Quedan alertas pendientes o activas")]:
            with self.subTest(caida=caida), patch.object(demo, "carga", return_value=tramo) as carga, \
                    patch.object(demo, "estado", return_value={"alertas": []}), \
                    patch.object(demo, "comprobar_fase", side_effect=[demo.ObservacionPendiente(motivo), None]), \
                    patch.object(demo.time, "monotonic", side_effect=[0, 110]):
                fase, guardar = {}, Mock()
                demo.observar_fase(fase, "SES-secreto", caida, 105, 240, guardar)
            self.assertEqual([c.args[0] for c in carga.call_args_list], [105, 15])
            self.assertEqual(fase["estados_http"], {"200": 4})
            self.assertEqual(fase["evaluaciones"][-1]["motivo"], "Condiciones verificadas")
            self.assertGreaterEqual(guardar.call_count, 4)

    def test_pending_no_sustituye_firing(self):
        fase = {"inesperados": [], "ejemplos": {
            "/equipos/EQ-001": {"status": 200, "cache": "BYPASS"},
            "/sesiones/{sesionId}": {"status": 503}}, "observacion": {
            "targets": [{"labels": {"job": j}, "health": "up"}
                        for j in ("fixture-api", "mongodb", "redis", "prometheus")],
            "consultas": [{"panel": p, "leyenda": l, "resultado": {"result": [{"value": [1, str(v)]}]}}
                          for p, l, v in [(2, "MongoDB", 1), (2, "Redis", 0),
                              (3, "P95", .1), (4, "requests", 3), (5, "5xx", 1),
                              (6, "MongoDB · conexiones", 10)]],
            "salud": {"status": 503, "body": {"error": {"detalles": [
                {"fuente": f, "estado": "no_disponible" if f == "redis" else "ok"}
                for f in ("mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris")]}}},
            "alertas": [{"labels": {"alertname": "FuenteNoDisponible"}, "state": "firing"},
                        {"labels": {"alertname": "ErroresAPIAltos"}, "state": "pending"}]}}
        with self.assertRaisesRegex(demo.ObservacionPendiente, "firing"):
            demo.comprobar_fase(fase, True)
        fase["observacion"]["alertas"][1]["state"] = "firing"
        demo.comprobar_fase(fase, True)
        self.assertIn("OK", fase["comprobaciones"])

    def test_plazo_agotado_conserva_medicion_y_motivo(self):
        tramo = {"estados_http": {"503": 2}, "cache": {"BYPASS": 1}, "inesperados": [],
                 "ejemplos": {}, "errores_deliberados": [404, 503]}
        with patch.object(demo, "carga", return_value=tramo), \
                patch.object(demo, "estado", return_value={"alertas": []}), \
                patch.object(demo, "comprobar_fase", side_effect=demo.ObservacionPendiente("Alerta pendiente")), \
                patch.object(demo.time, "monotonic", side_effect=[0, 240]):
            fase, guardar = {}, Mock()
            with self.assertRaisesRegex(demo.EsperaAgotada, "240 s agotado: Alerta pendiente"):
                demo.observar_fase(fase, "SES-secreto", True, 105, 240, guardar)
        self.assertEqual(fase["estados_http"], {"503": 2})
        self.assertEqual(fase["evaluaciones"][-1]["motivo"], "Alerta pendiente")
        guardar.assert_called()


if __name__ == "__main__":
    unittest.main()
