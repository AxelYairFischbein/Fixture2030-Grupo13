/* Índices asociados a patrones concretos del catálogo de consultas. */

"use strict";

const fixtureDb = db.getSiblingDB("fixture2030");

const created = {
  equipos: [
    fixtureDb.equipos.createIndex(
      { equipoId: 1 },
      { name: "uq_equipos_equipoId", unique: true }
    ),
    fixtureDb.equipos.createIndex(
      { codigo: 1 },
      { name: "uq_equipos_codigo", unique: true }
    ),
    fixtureDb.equipos.createIndex(
      { confederacion: 1, rankingReferencia: 1, equipoId: 1 },
      { name: "idx_equipos_confederacion_ranking" }
    )
  ],
  jugadores: [
    fixtureDb.jugadores.createIndex(
      { jugadorId: 1 },
      { name: "uq_jugadores_jugadorId", unique: true }
    ),
    fixtureDb.jugadores.createIndex(
      { equipoId: 1, numeroCamiseta: 1 },
      { name: "uq_jugadores_equipo_camiseta", unique: true }
    ),
    fixtureDb.jugadores.createIndex(
      { equipoId: 1, apellido: 1, nombre: 1, jugadorId: 1 },
      { name: "idx_jugadores_equipo_nombre" }
    ),
    fixtureDb.jugadores.createIndex(
      { posicion: 1, alturaCm: -1, jugadorId: 1 },
      { name: "idx_jugadores_posicion_altura" }
    ),
    fixtureDb.jugadores.createIndex(
      { nacionalidadCodigo: 1, alturaCm: -1, jugadorId: 1 },
      { name: "idx_jugadores_nacionalidad_altura" }
    )
  ]
};

print(EJSON.stringify({
  script: "03_indexes.js",
  created,
  equipos: fixtureDb.equipos.getIndexes(),
  jugadores: fixtureDb.jugadores.getIndexes()
}, null, 2));
