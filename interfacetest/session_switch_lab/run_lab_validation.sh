#!/usr/bin/env bash
set -euo pipefail

LAB_ROOT="/workspaces/chevdev/interfacetest/session_switch_lab"
WEB_ROOT="$LAB_ROOT/perplexity_clone_lab"
RUNTIME_DIR="$LAB_ROOT/runtime"
LOG_DIR="$RUNTIME_DIR/logs"
mkdir -p "$LOG_DIR"

export LAB_SHARED_BACKEND_URL="${LAB_SHARED_BACKEND_URL:-http://127.0.0.1:9001}"
export LAB_WEB_BASE_URL="${LAB_WEB_BASE_URL:-http://127.0.0.1:5179}"
export LAB_CANONICAL_USER_ID="${LAB_CANONICAL_USER_ID:-demo_user_1}"

cleanup() {
  set +e
  if [[ -n "${WEB_PID:-}" ]]; then
    kill "$WEB_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

printf "[lab] starting shared backend...\n"
LAB_BACKEND_PORT=9001 python "$LAB_ROOT/shared_session_backend.py" >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

printf "[lab] starting web clone server...\n"
(
  cd "$WEB_ROOT"
  PORT=5179 LAB_SHARED_BACKEND_URL="$LAB_SHARED_BACKEND_URL" LAB_CANONICAL_USER_ID="$LAB_CANONICAL_USER_ID" npm run dev
) >"$LOG_DIR/web.log" 2>&1 &
WEB_PID=$!

printf "[lab] waiting for services...\n"
for i in {1..60}; do
  if curl -fsS "$LAB_SHARED_BACKEND_URL/health" >/dev/null 2>&1 && curl -fsS "$LAB_WEB_BASE_URL" >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [[ "$i" -eq 60 ]]; then
    echo "[lab] services did not become ready in time"
    echo "[lab] backend tail:"; tail -n 60 "$LOG_DIR/backend.log" || true
    echo "[lab] web tail:"; tail -n 60 "$LOG_DIR/web.log" || true
    exit 1
  fi
done

printf "[lab] running API continuity checks...\n"
python "$LAB_ROOT/test_lab_api.py"

printf "[lab] running telegram simulator sanity check...\n"
python "$LAB_ROOT/telegram_sim_cli.py" --user "$LAB_CANONICAL_USER_ID" --message "remind me what we researched"

printf "[lab] capturing screenshots...\n"
node "$LAB_ROOT/capture_lab_screenshots.mjs"

printf "[lab] done. logs in %s and screenshots in %s/screenshots\n" "$LOG_DIR" "$RUNTIME_DIR"
