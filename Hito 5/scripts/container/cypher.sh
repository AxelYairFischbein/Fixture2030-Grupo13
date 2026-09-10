#!/bin/sh
# Cliente incluido en la imagen. No imprime las credenciales.
set -eu
export NEO4J_USERNAME="${NEO4J_AUTH%%/*}"
export NEO4J_PASSWORD="${NEO4J_AUTH#*/}"
exec cypher-shell -a bolt://localhost:7687 -d neo4j --fail-fast "$@"
