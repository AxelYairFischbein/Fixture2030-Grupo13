/* Instala o actualiza los validadores estrictos de ambas colecciones. */

"use strict";

const fixtureDb = db.getSiblingDB("fixture2030");

const equipoValidator = {
  $jsonSchema: {
    bsonType: "object",
    title: "Equipo del Fixture 2030",
    additionalProperties: false,
    required: [
      "_id", "equipoId", "codigo", "nombre", "confederacion", "region",
      "rankingReferencia", "sedeBase", "anioFundacion", "participacionesMundiales",
      "titulosMundiales", "estado", "esDatoSintetico", "origen", "creadoEn", "actualizadoEn"
    ],
    properties: {
      _id: {
        bsonType: "string",
        pattern: "^equipo:EQ-[0-9]{3}$",
        description: "Identificador técnico estable."
      },
      equipoId: {
        bsonType: "string",
        pattern: "^EQ-[0-9]{3}$",
        description: "Identificador de negocio estable."
      },
      codigo: {
        bsonType: "string",
        pattern: "^[A-Z0-9]{3}$",
        description: "Código corto único del equipo."
      },
      nombre: { bsonType: "string", minLength: 3, maxLength: 100 },
      confederacion: { enum: ["AFC", "CAF", "CONCACAF", "CONMEBOL", "OFC", "UEFA"] },
      region: { enum: ["AFRICA", "AMERICAS", "ASIA_PACIFICO", "EUROPA"] },
      rankingReferencia: { bsonType: "int", minimum: 1, maximum: 250 },
      sedeBase: {
        bsonType: "object",
        additionalProperties: false,
        required: ["ciudad", "pais"],
        properties: {
          ciudad: { bsonType: "string", minLength: 2, maxLength: 100 },
          pais: { bsonType: "string", minLength: 2, maxLength: 100 }
        }
      },
      anioFundacion: { bsonType: "int", minimum: 1800, maximum: 2030 },
      participacionesMundiales: { bsonType: "int", minimum: 0, maximum: 50 },
      titulosMundiales: { bsonType: "int", minimum: 0, maximum: 10 },
      estado: { enum: ["PRESELECCIONADO", "CONFIRMADO", "RETIRADO"] },
      esDatoSintetico: { bsonType: "bool" },
      origen: { bsonType: "string", minLength: 3, maxLength: 80 },
      creadoEn: { bsonType: "date" },
      actualizadoEn: { bsonType: "date" }
    }
  }
};

const jugadorValidator = {
  $jsonSchema: {
    bsonType: "object",
    title: "Jugador del Fixture 2030",
    additionalProperties: false,
    required: [
      "_id", "jugadorId", "equipoId", "nombre", "apellido", "fechaNacimiento",
      "nacionalidadCodigo", "posicion", "numeroCamiseta", "pieHabil", "alturaCm",
      "estadoPlantel",
      "esDatoSintetico", "origen", "creadoEn", "actualizadoEn"
    ],
    properties: {
      _id: {
        bsonType: "string",
        pattern: "^jugador:JUG-[0-9]{4}$",
        description: "Identificador técnico estable."
      },
      jugadorId: {
        bsonType: "string",
        pattern: "^JUG-[0-9]{4}$",
        description: "Identificador de negocio estable."
      },
      equipoId: {
        bsonType: "string",
        pattern: "^EQ-[0-9]{3}$",
        description: "Referencia lógica a equipos.equipoId."
      },
      nombre: { bsonType: "string", minLength: 2, maxLength: 80 },
      apellido: { bsonType: "string", minLength: 2, maxLength: 80 },
      fechaNacimiento: { bsonType: "date" },
      nacionalidadCodigo: { bsonType: "string", pattern: "^[A-Z0-9]{3}$" },
      posicion: { enum: ["ARQUERO", "DEFENSOR", "MEDIOCAMPISTA", "DELANTERO"] },
      numeroCamiseta: { bsonType: "int", minimum: 1, maximum: 99 },
      pieHabil: { enum: ["DERECHO", "IZQUIERDO", "AMBIDIESTRO"] },
      alturaCm: { bsonType: "int", minimum: 150, maximum: 220 },
      estadoPlantel: { enum: ["CONVOCADO", "RESERVA", "LESIONADO", "SUSPENDIDO"] },
      esDatoSintetico: { bsonType: "bool" },
      origen: { bsonType: "string", minLength: 3, maxLength: 80 },
      creadoEn: { bsonType: "date" },
      actualizadoEn: { bsonType: "date" }
    }
  }
};

function installValidator(name, validator) {
  if (!fixtureDb.getCollectionNames().includes(name)) {
    throw new Error(`La colección ${name} no existe. Ejecutar primero 01_collections.js.`);
  }
  const result = fixtureDb.runCommand({
    collMod: name,
    validator,
    validationLevel: "strict",
    validationAction: "error"
  });
  if (!result.ok) {
    throw new Error(`No se pudo actualizar ${name}: ${EJSON.stringify(result)}`);
  }
  return { collection: name, action: "validator_updated" };
}

print(EJSON.stringify({
  script: "02_validators.js",
  database: fixtureDb.getName(),
  validationLevel: "strict",
  validationAction: "error",
  result: [
    installValidator("equipos", equipoValidator),
    installValidator("jugadores", jugadorValidator)
  ]
}, null, 2));
