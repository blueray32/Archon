#!/bin/bash
# Automated Supabase free-tier cleanup.
# Usage: ./scripts/run_supabase_cleanup.sh [sql_file]
# Environment overrides:
#   MAX_CHUNKS_PER_SOURCE (default 400)
#   MAX_VERSIONS_PER_DOC (default 5)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SQL_FILE="${1:-$SCRIPT_DIR/supabase_free_tier_cleanup.sql}"

if [ ! -f "$SQL_FILE" ]; then
  echo "❌ SQL file not found: $SQL_FILE"
  exit 1
fi

# Load .env if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env"
  set +a
fi

PRIMARY_URL=""
FALLBACK_URL=""

detect_pooler_url() {
  local project_id="$1"
  local password="$2"
  local regions=(
    us-west-1
    us-west-2
    us-east-1
    us-east-2
    ca-central-1
    sa-east-1
    eu-west-1
    eu-central-1
    eu-north-1
    ap-south-1
    ap-southeast-1
    ap-southeast-2
    ap-northeast-1
    ap-northeast-2
  )
  local domains=(
    supabase.com
    supabase.net
  )

  export PGCONNECT_TIMEOUT=5

  for domain in "${domains[@]}"; do
    for region in "${regions[@]}"; do
      local candidate="postgres://postgres.${project_id}:${password}@aws-0-${region}.pooler.${domain}:6543/postgres?sslmode=require"
      if psql "$candidate" -tAc 'select 1' >/dev/null 2>&1; then
        echo "$candidate"
        return 0
      fi
    done
  done

  return 1
}

if [ -n "${DB_URL:-}" ] && [[ "$DB_URL" != *"localhost"* && "$DB_URL" != *"127.0.0.1"* ]]; then
  PRIMARY_URL="$DB_URL"
elif [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_SERVICE_KEY:-}" ]; then
  PROJECT_ID=$(echo "$SUPABASE_URL" | grep -oE '[a-z0-9]{20}')
  if [ -n "${SUPABASE_DB_HOST:-}" ]; then
    FALLBACK_URL="postgres://postgres:${SUPABASE_SERVICE_KEY}@${SUPABASE_DB_HOST}?sslmode=require"
  else
    FALLBACK_URL="postgres://postgres:${SUPABASE_SERVICE_KEY}@db.${PROJECT_ID}.supabase.co:5432/postgres?sslmode=require"
  fi

  if POOLER_URL=$(detect_pooler_url "$PROJECT_ID" "$SUPABASE_SERVICE_KEY"); then
    PRIMARY_URL="$POOLER_URL"
  else
    PRIMARY_URL="$FALLBACK_URL"
    FALLBACK_URL=""
  fi
else
  echo "❌ Missing database credentials. Provide DB_URL or (SUPABASE_URL + SUPABASE_SERVICE_KEY)."
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "❌ psql not found. Install with: brew install libpq"
  echo "   Then add to PATH: export PATH=\"/opt/homebrew/opt/libpq/bin:\$PATH\""
  exit 1
fi

MAX_CHUNKS_PER_SOURCE="${MAX_CHUNKS_PER_SOURCE:-400}"
MAX_VERSIONS_PER_DOC="${MAX_VERSIONS_PER_DOC:-5}"

echo "== Supabase Cleanup =="
echo "Project: ${SUPABASE_URL:-unknown}"
echo "SQL file: $SQL_FILE"
echo "Max chunks/source: $MAX_CHUNKS_PER_SOURCE"
echo "Max versions/doc: $MAX_VERSIONS_PER_DOC"
echo ""

run_cleanup() {
  local url="$1"
  psql "$url" \
    -v ON_ERROR_STOP=1 \
    -v max_chunks_per_source="$MAX_CHUNKS_PER_SOURCE" \
    -v max_versions_per_doc="$MAX_VERSIONS_PER_DOC" \
    -f "$SQL_FILE"
}

if run_cleanup "$PRIMARY_URL"; then
  echo ""
  echo "✓ Cleanup completed"
else
  if [ -n "$FALLBACK_URL" ]; then
    echo ""
    echo "⚠️  Primary connection failed, trying fallback..."
    run_cleanup "$FALLBACK_URL"
    echo ""
    echo "✓ Cleanup completed via fallback connection"
  else
    echo ""
    echo "❌ Cleanup failed using DB_URL"
    exit 1
  fi
fi
