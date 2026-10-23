"""Pruebas unitarias de clasificación y correlación. No conectan a bases ni a Docker."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluar_conectividad import codigo_salida, estado_producto, evaluacion_completa, verificar_logs


class DiagnosticoTest(unittest.TestCase):
    def test_fallo_del_proceso_no_declara_caida(self):
        registros = [{"etapa": "ejecucion", "resultado": "FAIL"}]
        self.assertEqual(estado_producto(registros), "desconocido")
        self.assertEqual(codigo_salida({"iris": registros}, "completo"), 2)
        self.assertEqual(estado_producto([{"etapa": "ejecucion", "resultado": "SKIP"}]), "no probado")
        self.assertEqual(estado_producto([{"etapa": "tcp", "resultado": "FAIL",
                                          "diagnostico": "conexion_rechazada"}]), "no disponible")

    def test_disponibilidad_y_completitud_son_distintas(self):
        registros = [{"etapa": "lectura", "resultado": "OK"}, {"etapa": "ejecucion", "resultado": "FAIL"}]
        self.assertEqual(estado_producto(registros), "disponible")
        self.assertFalse(evaluacion_completa(registros, "completo"))
        registros.append({"etapa": "api", "resultado": "FAIL", "http": 503})
        self.assertEqual(estado_producto(registros), "degradado")

    def test_logs_faltantes_o_parciales_implican_evaluacion_incompleta(self):
        registros = [{"etapa": "configuracion", "resultado": "OK"},
                     {"etapa": "api", "resultado": "OK", "request_id": "h11-prueba-neo4j-0"}]
        http = "INFO req=h11-prueba-neo4j-0 metodo=GET ruta=/api/v1/partidos/PAR-001 estado=200 ms=4.2"
        dependencia = "INFO req=h11-prueba-neo4j-0 dep=neo4j op=partido resultado=ok ms=2.0"
        for texto in ("", http):
            with self.subTest(texto=texto):
                _, controles = verificar_logs(texto, "h11-prueba", registros, "neo4j")
                self.assertEqual(controles[0]["resultado"], "SKIP")
                self.assertEqual(estado_producto(registros + controles), "disponible")
                self.assertEqual(codigo_salida({"neo4j": registros + controles}, "api"), 2)
        logs, controles = verificar_logs(http + "\n" + dependencia + "\npassword=secreto", "h11-prueba", registros, "neo4j")
        self.assertEqual(len(logs), 2)
        self.assertEqual(codigo_salida({"neo4j": registros + controles}, "api"), 0)
        registros[1].update(resultado="FAIL", http=503)
        self.assertEqual(codigo_salida({"neo4j": registros + controles}, "api"), 1)


if __name__ == "__main__":
    unittest.main()
