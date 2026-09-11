#!/usr/bin/env bash
# End-to-end smoke test, starting from a fresh stack:
#   1. offline unit tests
#   2. Kafka + ClickHouse from scratch, checking every object in clickhouse/init/*.sql exists
#   3. the demo walkthrough, demo/01-04 (demo/04 only when ANTHROPIC_API_KEY is set); first, so
#      its unfiltered queries see only its own data
#   4. integration tests (sync + async detection; the live agent test when ANTHROPIC_API_KEY is set)
#
# Usage:  scripts/smoke_test.sh [--keep] [--no-ai]
#   --keep    leave the stack running afterwards
#   --no-ai   skip the live Claude steps even when ANTHROPIC_API_KEY is set
#
# WARNING: step 2 runs `compose down -v`, which wipes any existing stack data.
#
# Needs `pip install -e ".[ai,dev]"` and either Docker (running, with the compose plugin) or
# podman-compose. ANTHROPIC_API_KEY can come from the environment or a .env file at the repo
# root; with it, steps 3 and 4 make a few live Claude calls (cents). Overrides: PYTHON
# (default python3), COMPOSE (e.g. "podman-compose").
set -euo pipefail
cd "$(dirname "$0")/.."

keep=0
ai=1
for arg in "$@"; do
  case "$arg" in
    --keep) keep=1 ;;
    --no-ai) ai=0 ;;
    *) echo "usage: $0 [--keep] [--no-ai]" >&2; exit 2 ;;
  esac
done

step() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nSMOKE TEST FAILED: %s\n' "$*" >&2; exit 1; }
retry() {  # retry <attempts> <command...>: rerun every 2s until it succeeds
  local attempts=$1; shift
  for ((i = 1; i <= attempts; i++)); do "$@" >/dev/null 2>&1 && return 0; sleep 2; done
  return 1
}

python="${PYTHON:-python3}"
"$python" -c 'import instaclustr_sdk.agent' 2>/dev/null ||
  fail "$python can't import instaclustr_sdk.agent; run: pip install -e \".[ai,dev]\" (or set PYTHON)"

if [[ -z "${COMPOSE:-}" ]]; then
  if docker compose version >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    COMPOSE="docker compose"
  elif command -v podman-compose >/dev/null; then
    COMPOSE="podman-compose"
  else
    fail "need Docker (running, with the compose plugin) or podman-compose"
  fi
fi
read -ra compose <<<"$COMPOSE"
case "$COMPOSE" in *podman*) runtime=podman ;; *) runtime=docker ;; esac

if [[ -f .env ]]; then set -a; . ./.env; set +a; fi
if ((ai)) && [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  ai=0
  ai_skipped="no ANTHROPIC_API_KEY"
elif ((!ai)); then
  ai_skipped="--no-ai"
fi
((ai)) || unset ANTHROPIC_API_KEY  # so the live agent test skips too

step "1/4 Unit tests (offline; the integration tests skip here and run in step 4)"
"$python" -m pytest -q

step "2/4 Fresh stack: Kafka + ClickHouse via $COMPOSE"
"${compose[@]}" down -v >/dev/null 2>&1 || true
cleanup() {
  if ((keep)); then
    echo "Stack left running; remove it with: $COMPOSE down -v"
  else
    "${compose[@]}" down -v >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT
"${compose[@]}" up -d kafka clickhouse >/dev/null

retry 60 "$runtime" exec s2s-kafka \
  /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 ||
  fail "Kafka broker didn't become reachable"

for ((i = 1; ; i++)); do
  curl -sf --max-time 2 localhost:8123/ping >/dev/null && break
  # ClickHouse exits if an init script fails, so stop waiting as soon as it does.
  if [[ "$("$runtime" inspect -f '{{.State.Running}}' s2s-clickhouse 2>/dev/null)" == false ]] ||
     ((i == 60)); then
    "$runtime" logs --tail 30 s2s-clickhouse >&2 || true
    fail "ClickHouse didn't come up (an error in clickhouse/init/*.sql stops it; log above)"
  fi
  sleep 2
done

expected=$(sed -nE 's/^CREATE (TABLE|MATERIALIZED VIEW) IF NOT EXISTS ([a-z_]+).*/\2/p' clickhouse/init/*.sql)
tables=" $("$runtime" exec s2s-clickhouse clickhouse-client -q 'SHOW TABLES' | tr '\n' ' ')"
for t in $expected; do
  [[ "$tables" == *" $t "* ]] || fail "ClickHouse is missing '$t' (has:$tables)"
done
echo "ClickHouse objects:$tables"

step "3/4 Demo walkthrough"
demo() {  # demo <script> <marker>...: require exit 0 and every marker in its output
  local script=$1 out
  shift
  echo "--- demo/$script"
  out=$("$python" "demo/$script" 2>&1) || { printf '%s\n' "$out"; fail "demo/$script exited non-zero"; }
  printf '%s\n' "$out"
  for marker; do
    grep -qF -- "$marker" <<<"$out" || fail "demo/$script: no '$marker' in its output"
  done
}
demo 01_hello_publish.py "Stream side works"
demo 02_detect_sync.py "<-- the spike we injected"
demo 03_detect_async.py "[callback]" "[generator]"
if ((ai)); then
  demo 04_explain_with_ai.py "explain_anomaly ===" "investigate_anomaly ===" "Verdict:"
else
  echo "--- demo/04 skipped ($ai_skipped)"
fi

step "4/4 Integration tests"
((ai)) || echo "(the live agent test will be skipped: $ai_skipped)"
RUN_INTEGRATION=1 "$python" -m pytest -q -rs tests/test_end_to_end.py

if ((ai)); then
  step "SMOKE TEST PASSED"
else
  step "SMOKE TEST PASSED (AI steps skipped: $ai_skipped)"
fi
