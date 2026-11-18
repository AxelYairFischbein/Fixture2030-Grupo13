/* Prueba no destructiva: los documentos inválidos deben ser rechazados. */

"use strict";

const fixtureDb = db.getSiblingDB("fixture2030");

const tests = [];

function expectValidationFailure(name, collection, document) {
  if (collection.findOne({ _id: document._id })) {
    throw new Error("El identificador temporal ya existe. No se modifica.");
  }
  try {
    collection.insertOne(document);
    collection.deleteOne({ _id: document._id });
    throw new Error(`${name}: el documento inválido fue aceptado.`);
  } catch (error) {
    if (error.code !== 121) {
      throw error;
    }
    tests.push({ name, rejected: true, mongoErrorCode: error.code, reason: "Document failed validation" });
  } finally {
    collection.deleteOne({ _id: document._id });
  }
}

expectValidationFailure(
  "equipo_sin_campos_criticos_y_ranking_fuera_de_rango",
  fixtureDb.equipos,
  {
    _id: "equipo:EQ-998",
    equipoId: "EQ-998",
    codigo: "X98",
    rankingReferencia: 999
  }
);

expectValidationFailure(
  "jugador_con_posicion_invalida",
  fixtureDb.jugadores,
  {
    _id: "jugador:JUG-9998",
    jugadorId: "JUG-9998",
    equipoId: "EQ-001",
    nombre: "Prueba",
    apellido: "Invalida",
    fechaNacimiento: ISODate("2000-01-01T00:00:00.000Z"),
    nacionalidadCodigo: "F01",
    posicion: "LIBERO",
    numeroCamiseta: 98,
    pieHabil: "DERECHO",
    alturaCm: 180,
    estadoPlantel: "CONVOCADO",
    esDatoSintetico: true,
    origen: "demostracion-controlada",
    creadoEn: new Date(),
    actualizadoEn: new Date()
  }
);

const leftovers = {
  teams: fixtureDb.equipos.countDocuments({ _id: "equipo:EQ-998" }),
  players: fixtureDb.jugadores.countDocuments({ _id: "jugador:JUG-9998" })
};
if (leftovers.teams !== 0 || leftovers.players !== 0) {
  throw new Error(`La prueba dejó documentos temporales: ${EJSON.stringify(leftovers)}`);
}

print(EJSON.stringify({ script: "08_test_validation.js", tests, leftovers, status: "OK" }, null, 2));
