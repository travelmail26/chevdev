#!/usr/bin/env bash
set -euo pipefail
SESSION=livecook_server
APP_DIR=/workspaces/chevdev/testscripts/livecook
LOG_FILE="$APP_DIR/logs/livecook-runtime.log"
if tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux kill-session -t "$SESSION"
fi
cd "$APP_DIR"
exec tmux new-session -d -s "$SESSION" "env HOST=0.0.0.0 PORT=4173 MONGODB_URI='${MONGODB_URI:-}' MONGODB_DB_NAME='${MONGODB_DB_NAME:-chef}' node server.js >> '$LOG_FILE' 2>&1"
