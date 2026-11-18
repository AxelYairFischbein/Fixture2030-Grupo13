#!/usr/bin/env bash
set -euo pipefail

# Evita que Git Bash en Windows convierta rutas internas del contenedor.
export MSYS_NO_PATHCONV=1

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
evidence_dir="$project_dir/evidencias"
mkdir -p "$evidence_dir"
cd "$project_dir"

wait_mongo_healthy() {
  local attempt state
  for attempt in $(seq 1 60); do
    state="$(docker inspect --format '{{.State.Health.Status}}' fixture2030-mongodb 2>/dev/null || true)"
    printf 'Intento %s: health=%s\n' "$attempt" "$state"
    if [[ "$state" == "healthy" ]]; then
      return 0
    fi
    sleep 2
  done
  printf 'MongoDB no alcanzó el estado healthy.\n' >&2
  return 1
}

mongo_file() {
  local container_path="$1"
  docker compose exec -T mongodb sh -lc \
    'exec mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin fixture2030 --file "$1"' \
    sh "$container_path"
}

mongo_eval() {
  local expression="$1"
  docker compose exec -T mongodb sh -lc \
    'exec mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin fixture2030 --eval "$1"' \
    sh "$expression"
}

docker compose config --quiet >"$evidence_dir/01_docker_compose_config.txt" 2>&1
printf 'Configuracion Compose valida\n' >>"$evidence_dir/01_docker_compose_config.txt"

{
  docker version --format 'Client={{.Client.Version}} Server={{.Server.Version}}'
  docker compose version
  docker compose up -d
  wait_mongo_healthy
  docker compose ps
} >"$evidence_dir/02_inicio_y_estado_contenedor.txt" 2>&1

mongo_eval 'const ping = db.adminCommand({ ping: 1 }); print(EJSON.stringify({ database: db.getName(), ping, version: db.version() }, null, 2));' \
  >"$evidence_dir/03_disponibilidad_mongodb.txt" 2>&1

{
  mongo_file /workspace/scripts/init/01_collections.js
  mongo_file /workspace/scripts/validations/02_validators.js
  mongo_file /workspace/scripts/indexes/03_indexes.js
} >"$evidence_dir/04_inicializacion_e_indices.txt" 2>&1

mongo_file /workspace/scripts/data/02_seed.js >"$evidence_dir/05_carga_inicial.txt" 2>&1
mongo_file /workspace/scripts/data/02_seed.js >"$evidence_dir/06_segunda_carga_idempotente.txt" 2>&1
mongo_file /workspace/scripts/verification/07_verify_integrity.js >"$evidence_dir/07_integridad_validadores_indices.txt" 2>&1
mongo_file /workspace/scripts/verification/08_test_validation.js >"$evidence_dir/08_rechazo_datos_invalidos.txt" 2>&1
mongo_file /workspace/scripts/operations/04_demo_crud.js >"$evidence_dir/09_operaciones_crud_controladas.txt" 2>&1
mongo_file /workspace/scripts/queries/05_queries.js >"$evidence_dir/10_consultas_y_agregaciones.txt" 2>&1
mongo_file /workspace/scripts/performance/06_compare_index.js >"$evidence_dir/11_comparacion_rendimiento_indice.txt" 2>&1
mongo_file /workspace/scripts/verification/07_verify_integrity.js >"$evidence_dir/12_integridad_canonica_final.txt" 2>&1

{
  docker compose restart mongodb
  wait_mongo_healthy
  mongo_eval 'const ping = db.adminCommand({ ping: 1 }); print(EJSON.stringify({ afterRestart: true, ping, version: db.version() }, null, 2));'
  mongo_file /workspace/scripts/verification/07_verify_integrity.js
} >"$evidence_dir/13_persistencia_despues_reinicio.txt" 2>&1

{
  docker compose ps
  docker inspect --format 'name={{.Name}} status={{.State.Status}} health={{.State.Health.Status}} restartCount={{.RestartCount}}' fixture2030-mongodb
} >"$evidence_dir/14_estado_final_contenedor.txt" 2>&1

{
  printf 'Evidencias generadas: %s\n' "$(date -Iseconds)"
  printf 'Base: fixture2030\n'
  printf 'Estado: todas las etapas finalizaron sin error\n'
  printf 'Advertencia: este procedimiento nunca ejecuta docker compose down -v\n'
} >"$evidence_dir/00_resumen_ejecucion.txt"

printf 'Evidencias generadas correctamente en %s\n' "$evidence_dir"
