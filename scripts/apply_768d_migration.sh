#!/bin/bash
set -e

# Apply 768D embedding migration to Supabase
# This script reads SUPABASE_URL and SUPABASE_SERVICE_KEY from .env

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Check required variables
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_KEY" ]; then
    echo "Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
    exit 1
fi

# Extract project ref from Supabase URL
PROJECT_REF=$(echo $SUPABASE_URL | sed -E 's|https://([^.]+)\.supabase\.co|\1|')

echo "🔧 Applying 768D embedding migration to Supabase..."
echo "   Project: $PROJECT_REF"
echo ""

# Read the migration SQL file
SQL_FILE="migration/fix_embedding_dimensions_to_768.sql"

if [ ! -f "$SQL_FILE" ]; then
    echo "Error: Migration file not found: $SQL_FILE"
    exit 1
fi

# Apply migration using Supabase REST API
# Note: This uses the SQL endpoint which requires the service role key
curl -X POST "${SUPABASE_URL}/rest/v1/rpc/exec_sql" \
  -H "apikey: ${SUPABASE_SERVICE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"query\": $(jq -Rs . < $SQL_FILE)}" \
  --fail-with-body || {
    echo ""
    echo "❌ Migration failed via REST API."
    echo ""
    echo "Please apply the migration manually:"
    echo "1. Go to: https://supabase.com/dashboard/project/$PROJECT_REF/sql/new"
    echo "2. Copy the contents of: $SQL_FILE"
    echo "3. Paste into the SQL editor and click 'Run'"
    exit 1
}

echo ""
echo "✅ Migration applied successfully!"
echo ""
echo "⚠️  IMPORTANT: All embeddings have been cleared."
echo "   You need to re-index your knowledge sources from the UI."
echo ""
echo "Next steps:"
echo "1. Go to Knowledge Base in the UI"
echo "2. Delete the failed crawl"
echo "3. Start a new crawl - it should work now!"
