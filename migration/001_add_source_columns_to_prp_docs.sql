-- Migration: Add source tracking columns to prp_docs
-- Required for Obsidian vault sync (archon_memory_sync.py)
-- Safe to run multiple times (uses IF NOT EXISTS)

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
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'prp_docs' AND column_name = 'source_type'
  ) THEN
    RAISE EXCEPTION 'Migration failed: source_type column not created';
  END IF;

  RAISE NOTICE 'Migration complete: source_type, source_path, updated_at columns added to prp_docs';
END $$;
