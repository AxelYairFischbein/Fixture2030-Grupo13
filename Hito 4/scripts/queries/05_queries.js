/* Consultas funcionales del módulo. Cada bloque declara su contrato. */

"use strict";

const fixtureDb = db.getSiblingDB("fixture2030");

function query(id, metadata, execute) {
  const result = execute();
  print(EJSON.stringify({ id, ...metadata, result }, null, 2));
}

query("Q01", {
  objective: "Recuperar un equipo por su identificador de negocio.",
  collection: "equipos",
  filter: { equipoId: "EQ-013" },
  returnedFields: ["equipoId", "codigo", "nombre", "confederacion", "rankingReferencia"],
  relatedIndex: "uq_equipos_equipoId",
  expected: "Un único equipo."
}, () => fixtureDb.equipos.findOne(
  { equipoId: "EQ-013" },
  { _id: 0, equipoId: 1, codigo: 1, nombre: 1, confederacion: 1, rankingReferencia: 1 }
));

query("Q02", {
  objective: "Recuperar un jugador por su identificador de negocio.",
  collection: "jugadores",
  filter: { jugadorId: "JUG-0313" },
  returnedFields: ["jugadorId", "nombre", "apellido", "equipoId", "posicion", "numeroCamiseta"],
  relatedIndex: "uq_jugadores_jugadorId",
  expected: "Un único jugador."
}, () => fixtureDb.jugadores.findOne(
  { jugadorId: "JUG-0313" },
  { _id: 0, jugadorId: 1, nombre: 1, apellido: 1, equipoId: 1, posicion: 1, numeroCamiseta: 1 }
));

query("Q03", {
  objective: "Filtrar equipos de CONMEBOL y ordenarlos por ranking.",
  collection: "equipos",
  filter: { confederacion: "CONMEBOL", rankingReferencia: { $lte: 50 } },
  returnedFields: ["equipoId", "nombre", "rankingReferencia"],
  relatedIndex: "idx_equipos_confederacion_ranking",
  expected: "Equipos que cumplen el filtro, en ranking ascendente."
}, () => fixtureDb.equipos.find(
  { confederacion: "CONMEBOL", rankingReferencia: { $lte: 50 } },
  { _id: 0, equipoId: 1, nombre: 1, rankingReferencia: 1 }
).sort({ rankingReferencia: 1, equipoId: 1 }).toArray());

query("Q04", {
  objective: "Buscar delanteros con altura desde 180 cm y ordenarlos por altura.",
  collection: "jugadores",
  filter: { posicion: "DELANTERO", alturaCm: { $gte: 180 } },
  returnedFields: ["jugadorId", "equipoId", "apellido", "alturaCm", "pieHabil"],
  relatedIndex: "idx_jugadores_posicion_altura",
  expected: "Los primeros diez delanteros por altura."
}, () => fixtureDb.jugadores.find(
  { posicion: "DELANTERO", alturaCm: { $gte: 180 } },
  { _id: 0, jugadorId: 1, equipoId: 1, apellido: 1, alturaCm: 1, pieHabil: 1 }
).sort({ alturaCm: -1, jugadorId: 1 }).limit(10).toArray());

query("Q05", {
  objective: "Proyectar una ficha resumida de equipos sintéticos.",
  collection: "equipos",
  filter: { esDatoSintetico: true },
  returnedFields: ["codigo", "nombre", "confederacion"],
  relatedIndex: "No se agrega índice: baja selectividad y colección de 64 documentos.",
  expected: "Cinco fichas resumidas, sin _id."
}, () => fixtureDb.equipos.find(
  { esDatoSintetico: true },
  { _id: 0, codigo: 1, nombre: 1, confederacion: 1 }
).sort({ equipoId: 1 }).limit(5).toArray());

query("Q06", {
  objective: "Paginar en forma estable el plantel de un equipo (página 2, tamaño 5).",
  collection: "jugadores",
  filter: { equipoId: "EQ-001" },
  returnedFields: ["jugadorId", "apellido", "nombre", "posicion", "numeroCamiseta"],
  relatedIndex: "idx_jugadores_equipo_nombre",
  expected: "Cinco jugadores después de omitir los primeros cinco."
}, () => fixtureDb.jugadores.find(
  { equipoId: "EQ-001" },
  { _id: 0, jugadorId: 1, apellido: 1, nombre: 1, posicion: 1, numeroCamiseta: 1 }
).sort({ apellido: 1, nombre: 1, jugadorId: 1 }).skip(5).limit(5).toArray());

query("Q07", {
  objective: "Recuperar todos los jugadores pertenecientes a un equipo.",
  collection: "jugadores",
  filter: { equipoId: "EQ-002" },
  returnedFields: ["jugadorId", "apellido", "nombre", "posicion", "numeroCamiseta"],
  relatedIndex: "idx_jugadores_equipo_nombre",
  expected: "Los 24 integrantes del plantel, ordenados por apellido y nombre."
}, () => fixtureDb.jugadores.find(
  { equipoId: "EQ-002" },
  { _id: 0, jugadorId: 1, apellido: 1, nombre: 1, posicion: 1, numeroCamiseta: 1 }
).sort({ apellido: 1, nombre: 1, jugadorId: 1 }).toArray());

query("Q08", {
  objective: "Agregar la composición y altura del plantel por posición.",
  collection: "jugadores",
  filter: { equipoId: "EQ-001" },
  returnedFields: ["posicion", "cantidad", "promedioAlturaCm"],
  relatedIndex: "idx_jugadores_equipo_nombre (prefijo equipoId)",
  expected: "Un resumen por cada posición presente en el plantel."
}, () => fixtureDb.jugadores.aggregate([
  { $match: { equipoId: "EQ-001" } },
  {
    $group: {
      _id: "$posicion",
      cantidad: { $sum: 1 },
      promedioAlturaCm: { $avg: "$alturaCm" }
    }
  },
  {
    $project: {
      _id: 0,
      posicion: "$_id",
      cantidad: 1,
      promedioAlturaCm: { $round: ["$promedioAlturaCm", 2] }
    }
  },
  { $sort: { posicion: 1 } }
]).toArray());

query("Q09", {
  objective: "Consolidar equipo y resumen de su plantel mediante $lookup.",
  collection: "equipos + jugadores",
  filter: { confederacion: "AFC" },
  returnedFields: ["equipoId", "nombre", "cantidadJugadores", "promedioAlturaCm"],
  relatedIndex: "idx_equipos_confederacion_ranking; idx_jugadores_equipo_nombre",
  expected: "Resumen de los primeros cinco equipos AFC."
}, () => fixtureDb.equipos.aggregate([
  { $match: { confederacion: "AFC" } },
  { $sort: { rankingReferencia: 1, equipoId: 1 } },
  { $limit: 5 },
  {
    $lookup: {
      from: "jugadores",
      localField: "equipoId",
      foreignField: "equipoId",
      as: "plantel"
    }
  },
  {
    $project: {
      _id: 0,
      equipoId: 1,
      nombre: 1,
      cantidadJugadores: { $size: "$plantel" },
      promedioAlturaCm: { $round: [{ $avg: "$plantel.alturaCm" }, 2] }
    }
  }
]).toArray());

query("Q10", {
  objective: "Detectar jugadores cuya referencia no corresponde a un equipo existente.",
  collection: "jugadores + equipos",
  filter: { "equipo vinculado": "inexistente" },
  returnedFields: ["jugadorId", "equipoId"],
  relatedIndex: "idx_jugadores_equipo_nombre; uq_equipos_equipoId",
  expected: "Arreglo vacío."
}, () => fixtureDb.jugadores.aggregate([
  {
    $lookup: {
      from: "equipos",
      localField: "equipoId",
      foreignField: "equipoId",
      as: "equipo"
    }
  },
  { $match: { equipo: { $size: 0 } } },
  { $project: { _id: 0, jugadorId: 1, equipoId: 1 } }
]).toArray());

query("Q11", {
  objective: "Detectar equipos cuyo plantel no tenga exactamente 24 jugadores.",
  collection: "equipos + jugadores",
  filter: { cantidadJugadores: { $ne: 24 } },
  returnedFields: ["equipoId", "cantidadJugadores"],
  relatedIndex: "uq_equipos_equipoId; idx_jugadores_equipo_nombre",
  expected: "Arreglo vacío para el conjunto canónico."
}, () => fixtureDb.equipos.aggregate([
  {
    $lookup: {
      from: "jugadores",
      localField: "equipoId",
      foreignField: "equipoId",
      as: "plantel"
    }
  },
  { $project: { _id: 0, equipoId: 1, cantidadJugadores: { $size: "$plantel" } } },
  { $match: { cantidadJugadores: { $ne: 24 } } }
]).toArray());

query("Q12", {
  objective: "Contar equipos y jugadores por confederación.",
  collection: "equipos + jugadores",
  filter: {},
  returnedFields: ["confederacion", "equipos", "jugadores"],
  relatedIndex: "idx_equipos_confederacion_ranking; idx_jugadores_equipo_nombre",
  expected: "Distribución consolidada de las seis confederaciones."
}, () => fixtureDb.equipos.aggregate([
  {
    $lookup: {
      from: "jugadores",
      localField: "equipoId",
      foreignField: "equipoId",
      as: "plantel"
    }
  },
  {
    $group: {
      _id: "$confederacion",
      equipos: { $sum: 1 },
      jugadores: { $sum: { $size: "$plantel" } }
    }
  },
  { $project: { _id: 0, confederacion: "$_id", equipos: 1, jugadores: 1 } },
  { $sort: { confederacion: 1 } }
]).toArray());

print(EJSON.stringify({ script: "05_queries.js", queriesExecuted: 12, status: "OK" }, null, 2));
