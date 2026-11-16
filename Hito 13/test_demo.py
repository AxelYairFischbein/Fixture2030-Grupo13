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


if __name__ == "__main__":
    unittest.main()
