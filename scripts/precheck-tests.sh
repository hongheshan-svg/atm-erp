#!/usr/bin/env bash
# Fresh PostgreSQL per run; never reads application DB_* credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="${1:---all}"
case "$STAGE" in
  --all) STAGES=(checks platform business concurrency) ;;
  checks|platform|business|concurrency) STAGES=("$STAGE") ;;
  *) echo 'Usage: precheck-tests.sh [--all|checks|platform|business|concurrency]' >&2; exit 2 ;;
esac
RUN_ID="atm-lean-test-$(date +%s)-$$"
IMAGE="${LEAN_TEST_IMAGE:-atm-erp-lean-tests:current}"
cleanup() {
  docker rm -f "$RUN_ID-pg" >/dev/null 2>&1 || true
  docker network rm "$RUN_ID" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker info >/dev/null
docker build -q -t "$IMAGE" -f "$ROOT/scripts/ci/Dockerfile.tests" "$ROOT" >/dev/null
docker network create "$RUN_ID" >/dev/null
docker run -d --name "$RUN_ID-pg" --network "$RUN_ID" --tmpfs /var/lib/postgresql/data \
  -e POSTGRES_DB=lean_test_runner -e POSTGRES_USER=lean_test \
  -e POSTGRES_PASSWORD=isolated-test-only postgres:15-alpine >/dev/null
ready=false
for ((i=0; i<60; i++)); do
  if docker exec "$RUN_ID-pg" pg_isready -h 127.0.0.1 -U lean_test -d lean_test_runner >/dev/null 2>&1; then
    ready=true; break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then echo 'Test PostgreSQL did not become ready' >&2; exit 1; fi
for stage in "${STAGES[@]}"; do
  docker run --rm --network "$RUN_ID" -v "$ROOT:/repo:ro" -w /repo \
    -e DJANGO_SETTINGS_MODULE=config.test_settings -e PYTHONDONTWRITEBYTECODE=1 \
    -e RUFF_NO_CACHE=true -e PG_TEST_HOST="$RUN_ID-pg" -e PG_TEST_USER=lean_test \
    -e PG_TEST_PASSWORD=isolated-test-only "$IMAGE" python run_all_tests.py --stage "$stage"
done
