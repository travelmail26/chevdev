#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspaces/chevdev/testscripts/livecook/logs
PID_FILE=/workspaces/chevdev/testscripts/livecook/logs/livecook-runtime.pid
LOG_FILE=/workspaces/chevdev/testscripts/livecook/logs/livecook-runtime.log
if [[ -f "$PID_FILE" ]]; then
  old_pid=$(cat "$PID_FILE" || true)
  if [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" 2>/dev/null; then
    kill "$old_pid" || true
    sleep 0.5
  fi
fi
nohup env HOST=0.0.0.0 PORT=4173 MONGODB_URI="${MONGODB_URI:-}" MONGODB_DB_NAME="${MONGODB_DB_NAME:-chef}" \
  node /workspaces/chevdev/testscripts/livecook/server.js \
  > "$LOG_FILE" 2>&1 < /dev/null &
new_pid=$!
echo "$new_pid" > "$PID_FILE"
echo "$new_pid"
