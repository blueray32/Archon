#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
ARTIFACTS="$ROOT_DIR/artifacts"
mkdir -p "$ARTIFACTS"

AGENTS_PORT="${AGENTS_PORT:-8052}"
BRIDGE_PORT="${BRIDGE_PORT:-8787}"
WS_PORT="${WS_PORT:-7860}"
AGENT_TYPE="${AGENT_TYPE:-rag}"

echo "==> Starting Archon Agents (port $AGENTS_PORT)"
if ! command -v uv >/dev/null 2>&1; then
  echo "[warn] 'uv' not found. Install uv or start the agents via Docker Compose."
else
  (
    cd "$ROOT_DIR/python"
    # Kill existing
    if [ -f "$ARTIFACTS/agents_service.pid" ] && kill -0 "$(cat "$ARTIFACTS/agents_service.pid")" 2>/dev/null; then
      kill "$(cat "$ARTIFACTS/agents_service.pid")" || true
      sleep 1
    fi
    ARCHON_AGENTS_PORT="$AGENTS_PORT" uv run uvicorn src.agents.server:app --host 0.0.0.0 --port "$AGENTS_PORT" \
      > "$ARTIFACTS/agents_service.log" 2>&1 &
    echo $! > "$ARTIFACTS/agents_service.pid"
  )
fi

echo "==> Building + Starting HTTP Bridge (port $BRIDGE_PORT)"
(
  cd "$ROOT_DIR/plugin-obsidian-claude-code/http-bridge"
  if command -v pnpm >/dev/null 2>&1; then PKG=pnpm; else PKG=npm; fi
  $PKG install
  $PKG run build
  # Kill existing
  if [ -f "$ARTIFACTS/bridge.pid" ] && kill -0 "$(cat "$ARTIFACTS/bridge.pid")" 2>/dev/null; then
    kill "$(cat "$ARTIFACTS/bridge.pid")" || true
    sleep 1
  fi
  BRIDGE_PORT="$BRIDGE_PORT" BRIDGE_FORWARD_TO_AGENTS=1 BRIDGE_AGENT_TYPE="$AGENT_TYPE" BRIDGE_AGENTS_URL="http://localhost:$AGENTS_PORT" \
    $PKG start > "$ARTIFACTS/codex_http_bridge.log" 2>&1 &
  echo $! > "$ARTIFACTS/bridge.pid"
)

echo "==> Building + Starting SDK WS Server (port $WS_PORT, provider http)"
(
  cd "$ROOT_DIR/plugin-obsidian-claude-code/sdk-server"
  if command -v pnpm >/dev/null 2>&1; then PKG=pnpm; else PKG=npm; fi
  $PKG install
  $PKG run build
  # Kill existing
  if [ -f "$ARTIFACTS/sdk_ws.pid" ] && kill -0 "$(cat "$ARTIFACTS/sdk_ws.pid")" 2>/dev/null; then
    kill "$(cat "$ARTIFACTS/sdk_ws.pid")" || true
    sleep 1
  fi
  PROVIDER=http HTTP_PROVIDER_URL="http://localhost:$BRIDGE_PORT/chat" HTTP_PROVIDER_STREAM=1 SDK_WS_PORT="$WS_PORT" \
    $PKG start > "$ARTIFACTS/obsidian_sdk_ws.log" 2>&1 &
  echo $! > "$ARTIFACTS/sdk_ws.pid"
)

echo "==> All services started"
echo "  Agents:   http://localhost:$AGENTS_PORT/health"
echo "  Bridge:   http://localhost:$BRIDGE_PORT/chat"
echo "  SDK WS:   ws://localhost:$WS_PORT"
echo "Logs in:    $ARTIFACTS"
echo "To stop:    kill \$(cat $ARTIFACTS/sdk_ws.pid $ARTIFACTS/bridge.pid $ARTIFACTS/agents_service.pid 2>/dev/null) || true"

