#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RUN_ID="lean-native-ota-test-$(date +%s)-$$"
cleanup() {
  docker rm -f "$RUN_ID-pg" "$RUN_ID-redis" >/dev/null 2>&1 || true
  docker network rm "$RUN_ID" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker build -q -t lean-native-ota-tests -f "$ROOT/scripts/ci/Dockerfile.native-ota-tests" "$ROOT" >/dev/null
NETWORK_ARGS=()
if [[ -n "${LEAN_OTA_TEST_SUBNET:-}" ]]; then NETWORK_ARGS+=(--subnet "$LEAN_OTA_TEST_SUBNET"); fi
docker network create "${NETWORK_ARGS[@]}" "$RUN_ID" >/dev/null
docker run -d --name "$RUN_ID-pg" --network "$RUN_ID" --network-alias native-ota-pg --tmpfs /var/lib/postgresql/data -e POSTGRES_DB=atm_erp_lean -e POSTGRES_USER=atm_erp_lean -e POSTGRES_PASSWORD=native-ota-isolated-only postgres:15-alpine >/dev/null
docker run -d --name "$RUN_ID-redis" --network "$RUN_ID" --network-alias native-ota-redis redis:7-alpine >/dev/null
for ((i=0; i<60; i++)); do
  if docker exec "$RUN_ID-pg" pg_isready -U atm_erp_lean >/dev/null 2>&1; then break; fi
  sleep 1
done
docker run --rm --network "$RUN_ID" -v "$ROOT:/repo:ro" lean-native-ota-tests python scripts/tests/ota_native_smoke.py
