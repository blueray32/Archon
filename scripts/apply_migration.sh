#!/bin/bash
# Apply database migration for prp_docs source columns
# Usage: ./scripts/apply_migration.sh [migration_file]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATION_FILE="${1:-$PROJECT_ROOT/migrations/001_add_source_columns_to_prp_docs.sql}"

# Load .env if exists
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env"
  set +a
fi

# Check for DB connection
if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_KEY:-}" ]; then
  echo "❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
  exit 1
fi

# Extract connection details from Supabase URL
# Format: https://[PROJECT_ID].supabase.co
PROJECT_ID=$(echo "$SUPABASE_URL" | grep -oE '[a-z0-9]{20}')

# Build postgres connection string
# Try transaction pooler first (port 6543) - better for serverless/network issues
DB_URL="postgres://postgres.${PROJECT_ID}:${SUPABASE_SERVICE_KEY}@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

# Fallback to direct connection
DB_URL_DIRECT="postgres://postgres:${SUPABASE_SERVICE_KEY}@db.${PROJECT_ID}.supabase.co:5432/postgres"

echo "=== Applying Database Migration ==="
echo "Migration: $MIGRATION_FILE"
echo "Target: ${SUPABASE_URL}"
echo ""

if [ ! -f "$MIGRATION_FILE" ]; then
  echo "❌ Migration file not found: $MIGRATION_FILE"
  exit 1
fi

# Check if psql is available
if ! command -v psql &> /dev/null; then
  echo "❌ psql not found. Install with: brew install libpq"
  echo "   Then add to PATH: export PATH=\"/opt/homebrew/opt/libpq/bin:\$PATH\""
  exit 1
fi

# Apply migration
echo "Running migration..."
if psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$MIGRATION_FILE"; then
  echo ""
  echo "✓ Migration applied successfully"

  # Verify columns exist
  echo ""
  echo "Verifying columns..."
  psql "$DB_URL" -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'prp_docs' AND column_name IN ('source_type', 'source_path', 'updated_at') ORDER BY column_name;"

  echo ""
  echo "✓ Migration complete"
else
  echo ""
  echo "❌ Migration failed"
  exit 1
fi
