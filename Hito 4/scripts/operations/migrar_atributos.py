"""Migración acotada de jugadores. Ejecutar con los drivers y configuración del Hito 10.

Primero exportar un respaldo fuera de Git y conservar una copia fuera del contenedor.
Aplicar retira solo dos atributos y sustituye su índice. Restaurar revierte esos cambios.
No carga muestras ni cambia identificadores, equipos o atributos restantes.
"""

import argparse
import hashlib
import json
from pathlib import Path

from bson import json_util
from pymongo import MongoClient
from app.config import cargar

CAMPOS = ("partidosInternacionales", "golesInternacionales")
ANTERIOR = "idx_jugadores_posicion_partidos"
NUEVO = "idx_jugadores_posicion_altura"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("accion", choices=("respaldar", "aplicar", "restaurar"))
    p.add_argument("respaldo", type=Path)
    a = p.parse_args()
    cfg = cargar()
    cliente = MongoClient(cfg.mongo_host, cfg.mongo_port, username=cfg.mongo_user,
                          password=cfg.mongo_password, authSource="admin")
    base = cliente[cfg.mongo_db]
    jugadores = base.jugadores
    if a.accion == "respaldar":
        contenido = {"documentos": list(jugadores.find().sort("_id", 1)),
                     "opciones": base.list_collections(filter={"name": "jugadores"}).next()["options"],
                     "indices": list(jugadores.list_indexes())}
        a.respaldo.parent.mkdir(parents=True, exist_ok=True)
        with a.respaldo.open("x", encoding="utf-8") as f:
            f.write(json_util.dumps(contenido))
        assert json_util.loads(a.respaldo.read_text(encoding="utf-8")) == contenido
    else:
        contenido = json_util.loads(a.respaldo.read_text(encoding="utf-8"))
        originales = contenido["documentos"]
        actuales = list(jugadores.find().sort("_id", 1))
        sin_estadisticas = lambda docs: [{k: v for k, v in d.items() if k not in CAMPOS} for d in docs]
        # Nunca sobrescribir modificaciones ajenas hechas después del respaldo.
        assert sin_estadisticas(actuales) == sin_estadisticas(originales), "Otros atributos cambiaron. Revisar antes de continuar."
        opciones = json_util.loads(json_util.dumps(contenido["opciones"]))
        if a.accion == "aplicar":
            esquema = opciones["validator"]["$jsonSchema"]
            esquema["required"] = [c for c in esquema["required"] if c not in CAMPOS]
            for c in CAMPOS:
                esquema["properties"].pop(c, None)
            base.command("collMod", "jugadores", **opciones)
            jugadores.update_many({}, {"$unset": {c: "" for c in CAMPOS}})
            if ANTERIOR in jugadores.index_information():
                jugadores.drop_index(ANTERIOR)
            jugadores.create_index([("posicion", 1), ("alturaCm", -1), ("jugadorId", 1)], name=NUEVO)
            assert list(jugadores.find().sort("_id", 1)) == sin_estadisticas(originales)
        else:
            base.command("collMod", "jugadores", **opciones)
            for d in originales:
                jugadores.replace_one({"_id": d["_id"]}, d)
            if NUEVO in jugadores.index_information():
                jugadores.drop_index(NUEVO)
            for indice in contenido["indices"]:
                if indice["name"] == ANTERIOR:
                    jugadores.create_index(list(indice["key"].items()), name=ANTERIOR)
            assert list(jugadores.find().sort("_id", 1)) == originales
    print(json.dumps({"accion": a.accion, "jugadores": jugadores.count_documents({}),
                      "respaldo_sha256": hashlib.sha256(a.respaldo.read_bytes()).hexdigest(),
                      "verificado": True}))
    cliente.close()


if __name__ == "__main__":
    main()
