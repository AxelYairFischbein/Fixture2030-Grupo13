/*
 * Demostración controlada e idempotente de INSERT, UPDATE y DELETE.
 * Los documentos temporales se limpian aun si una comprobación falla.
 */

"use strict";

const fixtureDb = db.getSiblingDB("fixture2030");
const DEMO_ORIGIN = "demostracion-controlada";
const TEAM_ID = "EQ-900";
const PLAYER_ID = "JUG-9000";

function emit(id, objective, collection, filter, returnedFields, index, result) {
  print(EJSON.stringify({
    id,
    objective,
    collection,
    filter,
    returnedFields,
    relatedIndex: index,
    result
  }, null, 2));
}

function assertCondition(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

assertCondition(!fixtureDb.jugadores.findOne({ jugadorId: PLAYER_ID }) &&
  !fixtureDb.equipos.findOne({ equipoId: TEAM_ID }), "Los identificadores temporales ya existen. No se borran datos previos.");

try {
  const now = new Date();
  const teamInsert = fixtureDb.equipos.insertOne({
    _id: `equipo:${TEAM_ID}`,
    equipoId: TEAM_ID,
    codigo: "D90",
    nombre: "Equipo Temporal de Demostracion",
    confederacion: "CONMEBOL",
    region: "AMERICAS",
    rankingReferencia: 200,
    sedeBase: { ciudad: "Ciudad Temporal", pais: "Pais Temporal" },
    anioFundacion: 2026,
    participacionesMundiales: 0,
    titulosMundiales: 0,
    estado: "PRESELECCIONADO",
    esDatoSintetico: true,
    origen: DEMO_ORIGIN,
    creadoEn: now,
    actualizadoEn: now
  });
  emit(
    "OP01",
    "Insertar un equipo temporal válido.",
    "equipos",
    { equipoId: TEAM_ID },
    ["acknowledged", "insertedId"],
    "uq_equipos_equipoId",
    teamInsert
  );

  assertCondition(
    fixtureDb.equipos.countDocuments({ equipoId: TEAM_ID }) === 1,
    "El equipo temporal no quedó disponible para referenciarlo."
  );

  const playerInsert = fixtureDb.jugadores.insertOne({
    _id: `jugador:${PLAYER_ID}`,
    jugadorId: PLAYER_ID,
    equipoId: TEAM_ID,
    nombre: "Jugador",
    apellido: "Temporal",
    fechaNacimiento: ISODate("2001-01-15T00:00:00.000Z"),
    nacionalidadCodigo: "D90",
    posicion: "DELANTERO",
    numeroCamiseta: 99,
    pieHabil: "DERECHO",
    alturaCm: 184,
    estadoPlantel: "CONVOCADO",
    esDatoSintetico: true,
    origen: DEMO_ORIGIN,
    creadoEn: now,
    actualizadoEn: now
  });
  emit(
    "OP02",
    "Insertar un jugador temporal luego de comprobar que su equipo existe.",
    "jugadores",
    { jugadorId: PLAYER_ID, equipoId: TEAM_ID },
    ["acknowledged", "insertedId"],
    "uq_jugadores_jugadorId; uq_jugadores_equipo_camiseta",
    playerInsert
  );

  const teamUpdate = fixtureDb.equipos.updateOne(
    { equipoId: TEAM_ID },
    { $set: { estado: "CONFIRMADO", actualizadoEn: new Date() } }
  );
  emit(
    "OP03",
    "Actualizar el estado del equipo temporal.",
    "equipos",
    { equipoId: TEAM_ID },
    ["matchedCount", "modifiedCount"],
    "uq_equipos_equipoId",
    teamUpdate
  );

  const playerUpdate = fixtureDb.jugadores.updateOne(
    { jugadorId: PLAYER_ID },
    {
      $set: { estadoPlantel: "RESERVA", actualizadoEn: new Date() }
    }
  );
  emit(
    "OP04",
    "Actualizar el estado del jugador sin cambiar su referencia al equipo.",
    "jugadores",
    { jugadorId: PLAYER_ID },
    ["matchedCount", "modifiedCount"],
    "uq_jugadores_jugadorId",
    playerUpdate
  );

  const linkedDocument = fixtureDb.jugadores.aggregate([
    { $match: { jugadorId: PLAYER_ID } },
    {
      $lookup: {
        from: "equipos",
        localField: "equipoId",
        foreignField: "equipoId",
        as: "equipo"
      }
    },
    { $unwind: "$equipo" },
    {
      $project: {
        _id: 0,
        jugadorId: 1,
        nombre: 1,
        apellido: 1,
        estadoPlantel: 1,
        equipoId: "$equipo.equipoId",
        equipoNombre: "$equipo.nombre",
        equipoEstado: "$equipo.estado"
      }
    }
  ]).toArray();
  emit(
    "OP05",
    "Comprobar las actualizaciones y la relación del jugador temporal.",
    "jugadores + equipos",
    { jugadorId: PLAYER_ID },
    ["jugadorId", "estadoPlantel", "equipoId", "equipoNombre", "equipoEstado"],
    "uq_jugadores_jugadorId; uq_equipos_equipoId",
    linkedDocument
  );

  assertCondition(linkedDocument.length === 1 && linkedDocument[0].estadoPlantel === "RESERVA" &&
    linkedDocument[0].equipoEstado === "CONFIRMADO", "No se pudo comprobar la actualización temporal.");
} finally {
  const playerDelete = fixtureDb.jugadores.deleteOne({ jugadorId: PLAYER_ID, origen: DEMO_ORIGIN });
  emit(
    "OP06",
    "Eliminar de forma controlada el jugador temporal.",
    "jugadores",
    { jugadorId: PLAYER_ID, origen: DEMO_ORIGIN },
    ["deletedCount"],
    "uq_jugadores_jugadorId",
    playerDelete
  );

  const teamDelete = fixtureDb.equipos.deleteOne({ equipoId: TEAM_ID, origen: DEMO_ORIGIN });
  emit(
    "OP07",
    "Eliminar el equipo temporal después de eliminar al jugador relacionado.",
    "equipos",
    { equipoId: TEAM_ID, origen: DEMO_ORIGIN },
    ["deletedCount"],
    "uq_equipos_equipoId",
    teamDelete
  );
}

const finalCounts = {
  teams: fixtureDb.equipos.countDocuments({}),
  players: fixtureDb.jugadores.countDocuments({}),
  temporaryTeams: fixtureDb.equipos.countDocuments({ origen: DEMO_ORIGIN }),
  temporaryPlayers: fixtureDb.jugadores.countDocuments({ origen: DEMO_ORIGIN })
};
assertCondition(finalCounts.teams === 64, `El recuento final de equipos es ${finalCounts.teams}.`);
assertCondition(finalCounts.players === 1536, `El recuento final de jugadores es ${finalCounts.players}.`);
assertCondition(finalCounts.temporaryTeams === 0, "Quedaron equipos temporales.");
assertCondition(finalCounts.temporaryPlayers === 0, "Quedaron jugadores temporales.");

print(EJSON.stringify({ script: "04_demo_crud.js", finalCounts, status: "OK" }, null, 2));
