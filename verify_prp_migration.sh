#!/bin/bash
# Verify PRP tables exist via Supabase REST (no Python deps)

set -euo pipefail

[ -f ".env" ] && set -o allexport && source .env && set +o allexport

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_KEY:-}" ]; then
  echo "❌ Need SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
  exit 1
fi

if [[ "${SUPABASE_URL}" == *"/rest/v1"* ]]; then
  REST_URL="$SUPABASE_URL"
else
  REST_URL="${SUPABASE_URL%/}/rest/v1"
fi

check() {
  local t="$1"
  code=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "apikey: ${SUPABASE_SERVICE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
    "${REST_URL}/${t}?select=id&limit=1")
  if [ "$code" -ge 200 ] && [ "$code" -lt 300 ]; then
    echo "✓ ${t}"
  else
    echo "✗ ${t} (HTTP $code)"
    return 1
  fi
}

ok=1
check prp_messages || ok=0
check prp_docs     || ok=0
check prp_personas || ok=0

[ "$ok" -eq 1 ] && echo "All good." || (echo "Apply migration/prp_system.sql first."; exit 1)