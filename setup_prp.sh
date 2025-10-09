#!/bin/bash
# PRP System Setup (Archon)
# Run this AFTER you apply migration/prp_system.sql in Supabase SQL Editor.

set -euo pipefail

echo "============================================================"
echo "PRP System Setup - Automated Steps"
echo "============================================================"
echo ""

# --- Sanity: must be in Archon repo root
if [ ! -d "python/src" ] || [ ! -f "docker-compose.yaml" ] && [ ! -f "docker-compose.yml" ]; then
  echo "❌ Please run from your Archon repo root (where docker-compose.* and python/src live)."
  exit 1
fi

# --- Load .env if present
if [ -f ".env" ]; then
  set -o allexport; source .env; set +o allexport
fi

# --- Required env
missing=()
[ -z "${OPENAI_API_KEY:-}" ] && missing+=("OPENAI_API_KEY")
[ -z "${SUPABASE_URL:-}" ] && missing+=("SUPABASE_URL")
[ -z "${SUPABASE_SERVICE_KEY:-}" ] && missing+=("SUPABASE_SERVICE_KEY")
if [ ${#missing[@]} -ne 0 ]; then
  echo "❌ Missing env vars: ${missing[*]}"
  echo "   Add them to .env then re-run."
  exit 1
fi

# --- Derive REST endpoint (PostgREST)
if [[ "${SUPABASE_URL}" == *"/rest/v1"* ]]; then
  REST_URL="$SUPABASE_URL"
else
  REST_URL="${SUPABASE_URL%/}/rest/v1"
fi

echo "Step 1: Verifying DB migration via Supabase REST…"
check_table () {
  local tbl="$1"
  # PostgREST will 200 even if empty; 404/400 if table missing or wrong
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "apikey: ${SUPABASE_SERVICE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
    "${REST_URL}/${tbl}?select=id&limit=1")
  if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    echo "  ✓ ${tbl} reachable"
    return 0
  else
    echo "  ✗ ${tbl} not reachable (HTTP $http_code)"
    return 1
  fi
}

ok=1
check_table "prp_messages" || ok=0
check_table "prp_docs"     || ok=0
check_table "prp_personas" || ok=0

if [ "$ok" -ne 1 ]; then
  echo ""
  echo "❌ Migration not applied yet."
  echo "   Open Supabase → SQL Editor, paste and run: migration/prp_system.sql"
  exit 1
fi
echo "✓ Migration verified."
echo ""

echo "Step 2: Indexing PRPs and docs…"
pushd python >/dev/null
# the script should already exist from your integration
uv run python -m src.scripts.prp_embed_sync || {
  echo "❌ Embedding sync failed. Check python/src/scripts/prp_embed_sync.py and logs."
  exit 1
}
popd >/dev/null
echo "✓ Embedding done."
echo ""

echo "Step 3: Restarting agents service…"
if [ -f "docker-compose.yml" ] || [ -f "docker-compose.yaml" ]; then
  docker compose restart archon-agents
else
  echo "⚠️  docker compose file not found; skip restart."
fi
echo "✓ Agents service restarted (or skipped)."
echo ""

echo "Step 4: Health check…"
sleep 3
HEALTH=$(curl -s http://localhost:8052/health || true)
if echo "$HEALTH" | grep -q '"prp"'; then
  echo "✓ PRP agent is registered."
else
  echo "⚠️  PRP agent not visible in health; continuing to smoke test anyway."
fi
echo ""

echo "Step 5: Smoke test…"
RESP=$(curl -s -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is the PRP system?",
    "context": {"session_id": "setup-test"}
  }' || true)

if echo "$RESP" | grep -q '"success":true'; then
  echo "✓ PRP agent responded successfully."
else
  echo "⚠️  Non-success response from agent:"
  echo "$RESP"
fi

echo ""
echo "============================================================"
echo "✅ PRP System Setup Complete!"
echo "Next:"
echo "• Add more PRPs into PRPs/"
echo "• Re-index anytime with:  cd python && uv run python -m src.scripts.prp_embed_sync"
echo "• Tail logs: docker compose logs archon-agents -f --tail=100"
echo "============================================================"