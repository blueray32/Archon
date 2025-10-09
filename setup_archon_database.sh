#!/usr/bin/env bash

set -euo pipefail

# =====================================================
# Archon Database Setup & Index Build Script
# =====================================================
# This script:
# 1. Runs the complete database migration
# 2. Builds HNSW or IVFFlat vector index for embeddings
# 3. Shows progress for long-running operations
# 4. Validates everything is working
# =====================================================

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Database URL from environment or first argument
DBURL="${DATABASE_URL:-${1:-}}"

if [ -z "$DBURL" ]; then
  echo -e "${RED}Error: DATABASE_URL not provided${NC}"
  echo ""
  echo "Usage:"
  echo "  DATABASE_URL='postgres://USER:PASSWORD@HOST:PORT/DATABASE' ./setup_archon_database.sh"
  echo "  or"
  echo "  ./setup_archon_database.sh 'postgres://USER:PASSWORD@HOST:PORT/DATABASE'"
  echo ""
  echo "For Supabase, get your direct connection string from:"
  echo "  https://supabase.com/dashboard/project/YOUR_PROJECT_ID/settings/database"
  echo ""
  echo "Use the 'Direct connection' string (port 5432), NOT the pooled connection."
  exit 1
fi

# Extract Supabase project reference from URL for helpful messages
PROJECT_REF=$(echo "$DBURL" | grep -oP '(?<=@)[^.]+(?=\.supabase)' || echo "unknown")

echo -e "${BLUE}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Archon Database Setup & Index Builder        ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Project:${NC} $PROJECT_REF"
echo -e "${YELLOW}Migration File:${NC} $SCRIPT_DIR/migration/complete_setup.sql"
echo ""

# Helper function to run SQL and capture errors
psql_exec() {
  local sql="$1"
  psql "$DBURL" -v ON_ERROR_STOP=1 -q -c "$sql"
}

# =====================================================
# STEP 1: Run Database Migration
# =====================================================
echo -e "${BLUE}[1/5]${NC} Running database migration..."
echo "      This creates all tables, extensions, and initial data"
echo ""

if [ ! -f "$SCRIPT_DIR/migration/complete_setup.sql" ]; then
  echo -e "${RED}Error: Migration file not found at $SCRIPT_DIR/migration/complete_setup.sql${NC}"
  exit 1
fi

if psql "$DBURL" -v ON_ERROR_STOP=1 -q -f "$SCRIPT_DIR/migration/complete_setup.sql"; then
  echo -e "${GREEN}✓ Database migration completed successfully${NC}"
else
  echo -e "${RED}✗ Migration failed. Check the error above.${NC}"
  exit 2
fi
echo ""

# =====================================================
# STEP 2: Verify Tables Created
# =====================================================
echo -e "${BLUE}[2/5]${NC} Verifying tables were created..."
echo ""

TABLE_COUNT=$(psql "$DBURL" -t -A -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'archon%';" || echo "0")

if [ "$TABLE_COUNT" -gt 0 ]; then
  echo -e "${GREEN}✓ Found $TABLE_COUNT Archon tables${NC}"
  psql "$DBURL" -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'archon%' ORDER BY table_name;"
else
  echo -e "${RED}✗ No Archon tables found. Migration may have failed.${NC}"
  exit 3
fi
echo ""

# =====================================================
# STEP 3: Configure Session for Index Build
# =====================================================
echo -e "${BLUE}[3/5]${NC} Configuring session for vector index build..."
echo "      Setting maintenance_work_mem=1GB, statement_timeout=0"
echo ""

psql_exec "SET statement_timeout = '0'; SET maintenance_work_mem = '1GB'; SET max_parallel_maintenance_workers = 2;"
echo -e "${GREEN}✓ Session configured${NC}"
echo ""

# =====================================================
# STEP 4: Build Vector Index (HNSW or IVFFlat)
# =====================================================
echo -e "${BLUE}[4/5]${NC} Building vector index on archon_crawled_pages.embedding..."
echo "      This may take 5-30 minutes depending on data volume"
echo ""

# Try HNSW first (faster, more accurate)
HNSW_SQL="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_archon_crawled_pages_embedding_hnsw ON public.archon_crawled_pages USING hnsw (embedding vector_cosine_ops);"

echo "      Attempting HNSW index (recommended)..."
if psql "$DBURL" -v ON_ERROR_STOP=0 -c "$HNSW_SQL" 2>/dev/null; then
  echo -e "${GREEN}✓ HNSW index creation started${NC}"
  INDEX_NAME="idx_archon_crawled_pages_embedding_hnsw"
else
  # Fallback to IVFFlat if HNSW not available
  echo -e "${YELLOW}⚠ HNSW not available, falling back to IVFFlat...${NC}"
  IVFFLAT_SQL="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_archon_crawled_pages_embedding_ivfflat ON public.archon_crawled_pages USING ivfflat (embedding vector_cosine_ops) WITH (lists = 128);"

  if psql "$DBURL" -v ON_ERROR_STOP=1 -c "$IVFFLAT_SQL"; then
    echo -e "${GREEN}✓ IVFFlat index creation started${NC}"
    INDEX_NAME="idx_archon_crawled_pages_embedding_ivfflat"
  else
    echo -e "${RED}✗ Both HNSW and IVFFlat index creation failed${NC}"
    exit 4
  fi
fi
echo ""

# Poll for index completion
echo "      Monitoring index build progress (polling every 10 seconds)..."
echo "      Press Ctrl+C to stop monitoring (index will continue building)"
echo ""

POLL_COUNT=0
while true; do
  # Check if index exists and is ready
  IDX_READY=$(psql "$DBURL" -t -A -c "SELECT 1 FROM pg_class WHERE relkind = 'i' AND relname = '$INDEX_NAME' LIMIT 1;" || echo "0")

  if [ "$IDX_READY" = "1" ]; then
    echo -e "${GREEN}✓ Index '$INDEX_NAME' is ready${NC}"
    break
  fi

  POLL_COUNT=$((POLL_COUNT + 1))

  # Show progress every 10 seconds
  if [ $((POLL_COUNT % 1)) -eq 0 ]; then
    echo "      [$(date '+%H:%M:%S')] Still building..."

    # Try to show progress (Postgres 12+)
    psql "$DBURL" -t -A -c "SELECT COALESCE(ROUND(100.0 * blocks_done / NULLIF(blocks_total, 0), 1), 0) || '% complete' FROM pg_stat_progress_create_index WHERE relid = 'public.archon_crawled_pages'::regclass;" 2>/dev/null || true
  fi

  sleep 10
done
echo ""

# =====================================================
# STEP 5: Validate and Show Results
# =====================================================
echo -e "${BLUE}[5/5]${NC} Validation and Summary"
echo ""

# Show all indexes on the table
echo "Indexes on archon_crawled_pages:"
psql "$DBURL" -c "SELECT indexrelid::regclass AS index_name, idx_scan AS scans, pg_size_pretty(pg_relation_size(indexrelid)) AS size FROM pg_stat_user_indexes WHERE schemaname = 'public' AND relname = 'archon_crawled_pages';"
echo ""

# Check row count
ROW_COUNT=$(psql "$DBURL" -t -A -c "SELECT COUNT(*) FROM public.archon_crawled_pages;" || echo "0")
echo -e "Rows in archon_crawled_pages: ${GREEN}$ROW_COUNT${NC}"
echo ""

# Final success message
echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✓ Setup Completed Successfully!         ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "  1. Restart Archon services: cd $SCRIPT_DIR && docker compose restart"
echo "  2. Verify health: curl http://localhost:8181/health"
echo "  3. Access UI: http://localhost:3737"
echo ""
echo "The vector index will improve semantic search performance."
echo "If you have no data yet, the index is ready for when you add documents."
echo ""
