/*
 * Carga determinista e idempotente del conjunto canónico.
 * Los participantes son sintéticos porque las fuentes no definen los 64
 * clasificados reales de 2030.
 */

"use strict";

const fixtureDb = db.getSiblingDB("fixture2030");
const ORIGIN = "sintetico-grupo13-v1";
const CREATED_AT = ISODate("2026-09-02T00:00:00.000Z");
const EXPECTED_TEAMS = 64;
const PLAYERS_PER_TEAM = 24;
const EXPECTED_PLAYERS = EXPECTED_TEAMS * PLAYERS_PER_TEAM;

function pad(value, length) {
  return String(value).padStart(length, "0");
}

function assertCondition(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const confederations = ["AFC", "CAF", "CONCACAF", "CONMEBOL", "OFC", "UEFA"];
const regionByConfederation = {
  AFC: "ASIA_PACIFICO",
  CAF: "AFRICA",
  CONCACAF: "AMERICAS",
  CONMEBOL: "AMERICAS",
  OFC: "ASIA_PACIFICO",
  UEFA: "EUROPA"
};

const teams = [];
for (let teamNumber = 1; teamNumber <= EXPECTED_TEAMS; teamNumber += 1) {
  const equipoId = `EQ-${pad(teamNumber, 3)}`;
  const codigo = `F${pad(teamNumber, 2)}`;
  const confederacion = confederations[(teamNumber - 1) % confederations.length];
  teams.push({
    _id: `equipo:${equipoId}`,
    equipoId,
    codigo,
    nombre: `Seleccion Sintetica ${pad(teamNumber, 2)}`,
    confederacion,
    region: regionByConfederation[confederacion],
    rankingReferencia: teamNumber,
    sedeBase: {
      ciudad: `Ciudad Sintetica ${pad(teamNumber, 2)}`,
      pais: `Pais Sintetico ${pad(teamNumber, 2)}`
    },
    anioFundacion: 1900 + (teamNumber % 100),
    participacionesMundiales: teamNumber % 18,
    titulosMundiales: teamNumber % 5 === 0 ? teamNumber % 4 : 0,
    estado: "PRESELECCIONADO",
    esDatoSintetico: true,
    origen: ORIGIN,
    creadoEn: CREATED_AT,
    actualizadoEn: CREATED_AT
  });
}

const positions = [
  "ARQUERO", "ARQUERO", "ARQUERO",
  "DEFENSOR", "DEFENSOR", "DEFENSOR", "DEFENSOR",
  "DEFENSOR", "DEFENSOR", "DEFENSOR", "DEFENSOR",
  "MEDIOCAMPISTA", "MEDIOCAMPISTA", "MEDIOCAMPISTA", "MEDIOCAMPISTA",
  "MEDIOCAMPISTA", "MEDIOCAMPISTA", "MEDIOCAMPISTA", "MEDIOCAMPISTA",
  "DELANTERO", "DELANTERO", "DELANTERO", "DELANTERO", "DELANTERO"
];
const heightBase = {
  ARQUERO: 184,
  DEFENSOR: 178,
  MEDIOCAMPISTA: 170,
  DELANTERO: 175
};
const feet = ["DERECHO", "IZQUIERDO", "DERECHO", "AMBIDIESTRO"];

const players = [];
let globalPlayerNumber = 1;
for (const team of teams) {
  for (let squadNumber = 1; squadNumber <= PLAYERS_PER_TEAM; squadNumber += 1) {
    const jugadorId = `JUG-${pad(globalPlayerNumber, 4)}`;
    const posicion = positions[squadNumber - 1];
    const year = 1992 + ((globalPlayerNumber - 1) % 15);
    const month = (globalPlayerNumber - 1) % 12;
    const day = ((globalPlayerNumber * 5) % 28) + 1;

    players.push({
      _id: `jugador:${jugadorId}`,
      jugadorId,
      equipoId: team.equipoId,
      nombre: `Nombre${pad(globalPlayerNumber, 4)}`,
      apellido: `Apellido${pad(globalPlayerNumber, 4)}`,
      fechaNacimiento: new Date(Date.UTC(year, month, day)),
      nacionalidadCodigo: team.codigo,
      posicion,
      numeroCamiseta: squadNumber,
      pieHabil: feet[(globalPlayerNumber - 1) % feet.length],
      alturaCm: heightBase[posicion] + ((globalPlayerNumber * 3) % 13),
      estadoPlantel: "CONVOCADO",
      esDatoSintetico: true,
      origen: ORIGIN,
      creadoEn: CREATED_AT,
      actualizadoEn: CREATED_AT
    });
    globalPlayerNumber += 1;
  }
}

assertCondition(teams.length === EXPECTED_TEAMS, "El generador no produjo 64 equipos.");
assertCondition(players.length === EXPECTED_PLAYERS, "El generador no produjo 1.536 jugadores.");

// Limpieza acotada de una demostración interrumpida; nunca afecta datos ajenos.
fixtureDb.jugadores.deleteMany({ origen: "demostracion-controlada" });
fixtureDb.equipos.deleteMany({ origen: "demostracion-controlada" });

const expectedTeamIds = teams.map((team) => team._id);
const expectedPlayerIds = players.map((player) => player._id);
const prunedPlayers = fixtureDb.jugadores.deleteMany({
  origen: ORIGIN,
  _id: { $nin: expectedPlayerIds }
});
const prunedTeams = fixtureDb.equipos.deleteMany({
  origen: ORIGIN,
  _id: { $nin: expectedTeamIds }
});

const teamResult = fixtureDb.equipos.bulkWrite(
  teams.map((team) => ({
    replaceOne: {
      filter: { _id: team._id },
      replacement: team,
      upsert: true
    }
  })),
  { ordered: true }
);

const teamBusinessIds = new Set(
  fixtureDb.equipos.find({ equipoId: { $in: teams.map((team) => team.equipoId) } }, { equipoId: 1 })
    .toArray()
    .map((team) => team.equipoId)
);
assertCondition(teamBusinessIds.size === EXPECTED_TEAMS, "No están disponibles todos los equipos de referencia.");

const playerResult = fixtureDb.jugadores.bulkWrite(
  players.map((player) => ({
    replaceOne: {
      filter: { _id: player._id },
      replacement: player,
      upsert: true
    }
  })),
  { ordered: true }
);

const teamCount = fixtureDb.equipos.countDocuments({});
const playerCount = fixtureDb.jugadores.countDocuments({});
const orphanCount = fixtureDb.jugadores.aggregate([
  {
    $lookup: {
      from: "equipos",
      localField: "equipoId",
      foreignField: "equipoId",
      as: "equipo"
    }
  },
  { $match: { equipo: { $size: 0 } } },
  { $count: "total" }
]).toArray()[0]?.total ?? 0;

assertCondition(teamCount === EXPECTED_TEAMS, `Se esperaban 64 equipos y se obtuvieron ${teamCount}.`);
assertCondition(playerCount === EXPECTED_PLAYERS, `Se esperaban 1.536 jugadores y se obtuvieron ${playerCount}.`);
assertCondition(orphanCount === 0, `Se detectaron ${orphanCount} jugadores huérfanos.`);

print(EJSON.stringify({
  script: "02_seed.js",
  origin: ORIGIN,
  dataset: "sintetico_no_oficial",
  expected: { teams: EXPECTED_TEAMS, playersPerTeam: PLAYERS_PER_TEAM, players: EXPECTED_PLAYERS },
  pruned: { teams: prunedTeams.deletedCount, players: prunedPlayers.deletedCount },
  teamsBulk: {
    inserted: teamResult.insertedCount,
    matched: teamResult.matchedCount,
    modified: teamResult.modifiedCount,
    upserted: teamResult.upsertedCount
  },
  playersBulk: {
    inserted: playerResult.insertedCount,
    matched: playerResult.matchedCount,
    modified: playerResult.modifiedCount,
    upserted: playerResult.upsertedCount
  },
  final: { teams: teamCount, players: playerCount, orphans: orphanCount },
  status: "OK"
}, null, 2));
