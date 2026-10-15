"""Caso de uso de salud: estado de cada dependencia.

En la Fase 1 no hay adaptadores, así que todas figuran "no_configurada". Cada
fase siguiente registra el chequeo de su adaptador (ping, catálogo, etc.).
"""

from app.schemas.salud import Dependencias, EstadoDependencia, RespuestaSalud

DEPENDENCIAS = ("mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris")


class ServicioSalud:
    def consultar(self) -> RespuestaSalud:
        estados = {nombre: EstadoDependencia.NO_CONFIGURADA for nombre in DEPENDENCIAS}
        degradado = EstadoDependencia.NO_DISPONIBLE in estados.values()
        return RespuestaSalud(
            estado="degradado" if degradado else "ok",
            dependencias=Dependencias(**estados),
        )


def obtener_servicio_salud() -> ServicioSalud:
    return ServicioSalud()
