"""Pruebas unitarias de clasificación y correlación. No conectan a bases ni a Docker."""

import sys
import unittest
import io
import json
from contextlib import redirect_stdout
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluar_conectividad import codigo_salida, estado_producto, evaluacion_completa, verificar_logs, seguridad


class DiagnosticoTest(unittest.TestCase):
    def test_lectura_no_acredita_identidad_ni_permisos(self):
        salida = io.StringIO()
        with redirect_stdout(salida):
            seguridad("cassandra", None, None, {})
        registros = [json.loads(linea) for linea in salida.getvalue().splitlines()]
        registros += [{"etapa": e, "resultado": "OK"} for e in ("configuracion", "protocolo", "lectura")]
        self.assertEqual(estado_producto(registros), "disponible")
        self.assertEqual(codigo_salida({"cassandra": registros}, "clientes"), 2)
        self.assertTrue(all(not r["verificada_independientemente"] for r in registros[:2]))

    def test_mongodb_identidad_y_permiso_son_independientes(self):
        class DB:
            def command(self, nombre, **opciones):
                return {"authInfo": {"authenticatedUsers": [{"user": "demo", "db": "admin"}],
                        "authenticatedUserPrivileges": [{"resource": {"db": "otra", "collection": "equipos"},
                                                         "actions": ["find"]}]}}
        salida = io.StringIO()
        with redirect_stdout(salida):
            seguridad("mongodb", SimpleNamespace(_db=DB()), SimpleNamespace(mongo_user="demo", mongo_db="fixture2030"), {})
        identidad, permiso = [json.loads(linea) for linea in salida.getvalue().splitlines()]
        self.assertTrue(identidad["verificada_independientemente"])
        self.assertFalse(permiso["verificada_independientemente"])
        self.assertEqual(permiso["resultado"], "WARN")

    def test_redis_sin_credencial_no_infiere_autenticacion(self):
        llamadas = []
        cliente = SimpleNamespace(acl_whoami=lambda: "default", execute_command=lambda *args: llamadas.append(args) or "OK")
        salida = io.StringIO()
        with redirect_stdout(salida):
            seguridad("redis", SimpleNamespace(_r=cliente), SimpleNamespace(redis_password=""),
                      {"redis_clave": "fixture2030:h11:demo:conectividad"})
        identidad, permiso = [json.loads(linea) for linea in salida.getvalue().splitlines()]
        self.assertFalse(identidad["verificada_independientemente"])
        self.assertTrue(permiso["verificada_independientemente"])
        self.assertEqual(llamadas, [("ACL", "DRYRUN", "default", "GET", "fixture2030:h11:demo:conectividad")])

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
