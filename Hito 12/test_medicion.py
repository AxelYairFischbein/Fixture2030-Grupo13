"""Pruebas unitarias del cálculo y del oráculo. No sustituyen la carga real."""

import copy
import io
import json
import unittest
from unittest.mock import patch

from datos import config, muestra, ordenados
from medir import caso, resumen, validar_respuesta, fuente, ejecutar


class MedicionTest(unittest.TestCase):
    def test_fuente_recibe_configuracion_efectiva(self):
        c = config()
        c["por_partido"] = 300
        with patch("medir.comando", return_value='{"integridad":"OK"}') as llamada:
            self.assertEqual(fuente(c)["integridad"], "OK")
        self.assertEqual(json.loads(llamada.call_args.kwargs["entrada"]), c)
        self.assertEqual(llamada.call_args.args[0][-2:], ["--config", "-"])

    def test_fallo_conserva_mediciones_parciales(self):
        fase_ok = {"fase": "calentamiento", "intentadas": 1, "fallidas": 0, "cliente": {"p95_ms": 2},
                   "interrumpida": False, "sin_resultado": 0, "recursos": [{"cpu_pct": 1}]}
        for fallo in ("fase", "validacion_final"):
            with self.subTest(fallo=fallo), patch("medir.comando", return_value="base"), \
                    patch("medir.entorno", return_value={}), patch("medir.integridad", return_value={}), \
                    patch("medir.fuente", side_effect=[{}, ValueError("dato privado")] if fallo == "validacion_final" else [{}, {}]), \
                    patch("medir.fase", side_effect=[(fase_ok, []), RuntimeError("dato privado")] if fallo == "fase" else [(fase_ok, [])]):
                archivo = io.StringIO()
                r = ejecutar(config(), "base", fallo == "validacion_final", archivo)
                self.assertFalse(r["completa"])
                self.assertEqual(len(r["fases"]), 1)
                self.assertTrue(r["fallos"])
                self.assertNotIn("dato privado", archivo.getvalue())
                self.assertEqual(json.loads(archivo.getvalue())["fases"][0]["intentadas"], 1)

    def test_percentiles_incluyen_extremos(self):
        r = resumen([1, 2, 3, 4, 1000])
        self.assertEqual(r, {"n": 5, "min_ms": 1, "promedio_ms": 202,
                             "p50_ms": 3, "p95_ms": 1000, "p99_ms": 1000})

    def test_muestra_reproducible_y_paginas_con_empates(self):
        c = config()
        a = list(muestra(c, "PAR-001"))
        self.assertEqual(a, list(muestra(c, "PAR-001")))
        self.assertEqual(len({r["comentarioId"] for r in a}), c["por_partido"])
        primera, segunda = caso(c, "PAR-001", 0), caso(c, "PAR-001", 1)
        self.assertEqual(primera["items"][-1]["creadoEn"], segunda["items"][0]["creadoEn"])
        todas = [fila for n in range(c["por_partido"] // c["limite"])
                 for fila in caso(c, "PAR-001", n)["items"]]
        self.assertEqual(todas, ordenados(c, "PAR-001"))

    def test_http_200_no_basta_para_integridad(self):
        c = config()
        prueba = caso(c, "PAR-001", 0)
        cuerpo = {"data": {"partidoId": "PAR-001", "items": prueba["items"], "particiones": 20,
                            "desde": c["desde"], "hasta": c["hasta"]},
                  "meta": {"requestId": "h12-test", "paginacion": {"siguienteCursor": prueba["siguiente"]}}}
        validar_respuesta(c, prueba, cuerpo, "h12-test", "h12-test")
        alterado = copy.deepcopy(cuerpo)
        alterado["data"]["items"][0]["contenido"] = "alterado"
        with self.assertRaises(ValueError):
            validar_respuesta(c, prueba, alterado, "h12-test", "h12-test")
        alterado = copy.deepcopy(cuerpo)
        alterado["meta"]["paginacion"]["siguienteCursor"] = None
        with self.assertRaises(ValueError):
            validar_respuesta(c, prueba, alterado, "h12-test", "h12-test")


if __name__ == "__main__":
    unittest.main()
