# Manual Database Migration Instructions

## Quick Start (Supabase Dashboard - Recommended)

If you have network/connection issues with `psql`, use the Supabase SQL Editor:

### Step 1: Open Supabase SQL Editor

1. Go to https://supabase.com/dashboard
2. Select your project: `rpqlvsxsrezjqiymsewx`
3. Click **SQL Editor** in left sidebar
4. Click **New Query**

### Step 2: Copy-Paste Migration SQL

```sql
-- Migration: Add source tracking columns to prp_docs
-- Required for Obsidian vault sync (archon_memory_sync.py)

-- Add source_type column (stores 'obsidian_note', 'obsidian_vault_index', etc.)
ALTER TABLE prp_docs
  ADD COLUMN IF NOT EXISTS source_type text DEFAULT 'obsidian';

-- Add source_path column (stores vault-relative path for deduplication)
ALTER TABLE prp_docs
  ADD COLUMN IF NOT EXISTS source_path text;

-- Add updated_at column (for tracking last sync time)
ALTER TABLE prp_docs
  ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- Create index for efficient source lookups
CREATE INDEX IF NOT EXISTS prp_docs_source_idx
  ON prp_docs (source_type, source_path);

-- Create index for time-based queries
CREATE INDEX IF NOT EXISTS prp_docs_updated_at_idx
  ON prp_docs (updated_at DESC);

-- Verify columns exist
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'prp_docs'
  AND column_name IN ('source_type', 'source_path', 'updated_at')
ORDER BY column_name;
```

### Step 3: Run Query

Click **Run** (or press `Cmd+Enter` / `Ctrl+Enter`)

### Step 4: Verify Results

You should see output showing 3 rows:
```
column_name  | data_type                   | column_default
-------------+-----------------------------+------------------
source_path  | text                        | NULL
source_type  | text                        | 'obsidian'::text
updated_at   | timestamp with time zone    | now()
```

✓ Migration complete!

---

## Alternative: Command Line (if psql works)

If you have direct database access:

```bash
cd /Users/ciarancox/Archon
./scripts/apply_migration.sh
```

Or manually:

```bash
# Load environment
set -a && source .env && set +a

# Get project ID
PROJECT_ID=$(echo "$SUPABASE_URL" | grep -oE '[a-z0-9]{20}')

# Try pooler first (usually works better)
DB_URL="postgres://postgres.${PROJECT_ID}:${SUPABASE_SERVICE_KEY}@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

# Run migration
psql "$DB_URL" -f migrations/001_add_source_columns_to_prp_docs.sql

# Or direct connection if pooler fails
DB_URL="postgres://postgres:${SUPABASE_SERVICE_KEY}@db.${PROJECT_ID}.supabase.co:5432/postgres"
psql "$DB_URL" -f migrations/001_add_source_columns_to_prp_docs.sql
```

---

## Troubleshooting

### "relation prp_docs does not exist"

The table needs to be created first. Run this in Supabase SQL Editor:

```sql
-- Create prp_docs table if missing
CREATE TABLE IF NOT EXISTS prp_docs (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  kind text NOT NULL,
  content text NOT NULL,
  metadata jsonb DEFAULT '{}'::jsonb,
  embedding vector(768),
  created_at timestamptz DEFAULT now(),

  -- New columns
  source_type text DEFAULT 'obsidian',
  source_path text,
  updated_at timestamptz DEFAULT now()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS prp_docs_kind_idx ON prp_docs(kind);
CREATE INDEX IF NOT EXISTS prp_docs_source_idx ON prp_docs(source_type, source_path);
CREATE INDEX IF NOT EXISTS prp_docs_updated_at_idx ON prp_docs(updated_at DESC);
CREATE INDEX IF NOT EXISTS prp_docs_embedding_idx ON prp_docs USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### "type vector does not exist"

Enable pgvector extension first:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Then run the CREATE TABLE statement above.

---

## Next Steps

After migration succeeds, re-run vault sync:

```bash
cd /Users/ciarancox/Archon/python

uv run python src/scripts/orchestrate_obsidian_sync_production.py \
  --vault /Users/ciarancox/Documents/ArchonVault \
  --auto-tag \
  --concurrency 5 \
  --shard-size 2000
```

Check `artifacts/obsidian_sync_latest/manifest.json`:
- `synced_notes` should be > 0
- `failed_notes` should be 0
- No `source_type` errors in logs
