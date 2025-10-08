# Follow-up Execution Plan: DB Migration + Golden Set QA

## Overview

This plan addresses two issues from the production auto-tag run:

1. **DB sync error** - Missing `source_type` column in `prp_docs` table
2. **QA F1 = 0.00** - Need predictions for golden set (all notes were skipped as unchanged)

## Files Created

### 1. Database Migration
- `migrations/001_add_source_columns_to_prp_docs.sql`
- `scripts/apply_migration.sh` (helper script)

### 2. Prediction Script
- `python/src/scripts/predict_for_golden.py` (read-only predictions for golden set)

---

## Task 1: Apply Database Migration

### What It Does
Adds missing columns to `prp_docs` table:
- `source_type` (text) - identifies document type (obsidian_note, obsidian_vault_index, etc.)
- `source_path` (text) - stores vault-relative path for deduplication
- `updated_at` (timestamptz) - tracks last sync time

### Prerequisites
- `psql` installed (`brew install libpq`)
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`

### Execute Migration

**Option A: Using helper script (recommended)**
```bash
cd /Users/ciarancox/Archon
./scripts/apply_migration.sh
```

**Option B: Manual psql commands**
```bash
cd /Users/ciarancox/Archon

# Load .env
set -a && source .env && set +a

# Extract project ID from Supabase URL
PROJECT_ID=$(echo "$SUPABASE_URL" | grep -oE '[a-z0-9]{20}')

# Build connection string
DB_URL="postgres://postgres:${SUPABASE_SERVICE_KEY}@db.${PROJECT_ID}.supabase.co:5432/postgres"

# Apply migration
psql "$DB_URL" -v ON_ERROR_STOP=1 -f migrations/001_add_source_columns_to_prp_docs.sql

# Verify columns
psql "$DB_URL" -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'prp_docs' AND column_name IN ('source_type', 'source_path', 'updated_at');"
```

### Verify Migration Success
```bash
# Should show 3 rows: source_type, source_path, updated_at
psql "$DB_URL" -c "\d prp_docs" | grep -E "source_type|source_path|updated_at"
```

### Re-run Vault Sync (to populate DB)
```bash
cd /Users/ciarancox/Archon/python

uv run python src/scripts/orchestrate_obsidian_sync_production.py \
  --vault /Users/ciarancox/Documents/ArchonVault \
  --auto-tag \
  --concurrency 5 \
  --shard-size 2000
```

**Expected Result:**
- No more `source_type` column errors
- `manifest.json` should show `synced_notes: 6635` (or similar), `failed_notes: 0`

---

## Task 2: Generate Golden Set Predictions + QA

### What It Does
1. Reads `golden_set_archon.json` (204 notes)
2. For each note, generates predictions using Ollama (read-only, no vault modifications)
3. Saves predictions to `artifacts/predictions_golden.json`
4. Runs QA harness to evaluate F1 score

### Execute Prediction Generation

```bash
cd /Users/ciarancox/Archon/python

uv run python src/scripts/predict_for_golden.py \
  --vault /Users/ciarancox/Documents/ArchonVault \
  --golden golden_set_archon.json \
  --model qwen2.5:3b \
  --out artifacts/predictions_golden.json \
  --concurrency 5
```

**Expected Output:**
```
Loaded golden set: 204 notes
Using model: qwen2.5:3b
Generating predictions for 204 notes (concurrency=5)...
✓ Wrote artifacts/predictions_golden.json with 204 predictions
  Coverage: 204/204 (100.0%)
```

### Run QA Harness

```bash
cd /Users/ciarancox/Archon/python

uv run python src/scripts/qa_harness.py \
  --golden golden_set_archon.json \
  --predictions artifacts/predictions_golden.json \
  --threshold 0.90
```

**Expected Output:**
```
=== QA Evaluation Report ===

Overall Metrics:
  Precision: 0.XXX
  Recall:    0.XXX
  F1 Score:  0.XXX
  TP: XXX, FP: XXX, FN: XXX

Per-Label Metrics:
  [detailed breakdown by area/service/status]

Threshold: F1 >= 0.90
Status:    ✓ PASSED  (or ✗ FAILED with action items)
```

---

## Success Criteria

### Task 1: DB Migration
- [ ] Migration script runs without errors
- [ ] Columns `source_type`, `source_path`, `updated_at` exist in `prp_docs`
- [ ] Indexes created: `prp_docs_source_idx`, `prp_docs_updated_at_idx`
- [ ] Re-run vault sync shows `synced_notes > 0`, `failed_notes = 0`

### Task 2: Golden Set QA
- [ ] Predictions generated for all 204 golden set notes
- [ ] `artifacts/predictions_golden.json` exists and is valid JSON
- [ ] QA harness runs without errors
- [ ] **Target: F1 >= 0.90** (if below, review confusion matrix and adjust prompt/model)

---

## Rollback Plan

### Task 1: Rollback DB Migration
```bash
# Connect to DB
psql "$DB_URL"

# Remove added columns (if needed)
ALTER TABLE prp_docs DROP COLUMN IF EXISTS source_type;
ALTER TABLE prp_docs DROP COLUMN IF EXISTS source_path;
ALTER TABLE prp_docs DROP COLUMN IF EXISTS updated_at;

# Drop indexes
DROP INDEX IF EXISTS prp_docs_source_idx;
DROP INDEX IF EXISTS prp_docs_updated_at_idx;
```

**Note:** Only rollback if migration causes issues. The migration is additive and safe.

### Task 2: Rollback Predictions
```bash
# Simply delete the predictions file
rm -f artifacts/predictions_golden.json
```

**Note:** No vault changes are made by `predict_for_golden.py`, so no rollback needed for vault.

---

## Troubleshooting

### psql not found
```bash
brew install libpq
export PATH="/opt/homebrew/opt/libpq/bin:$PATH"
```

### DB connection fails
1. Check `.env` has `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`
2. Verify project ID extraction: `echo "$SUPABASE_URL" | grep -oE '[a-z0-9]{20}'`
3. Test connection: `psql "$DB_URL" -c "SELECT version();"`

### Ollama connection fails
```bash
# Check Ollama is running
curl -s http://localhost:11434/api/tags | jq .

# Pull model if missing
ollama pull qwen2.5:3b
```

### QA F1 below 0.90
1. Review confusion matrix in QA output
2. Check top misclassified examples
3. Options:
   - Tune prompt in `predict_for_golden.py`
   - Try larger model: `--model qwen2.5:7b` or `--model llama3.1:8b`
   - Expand golden set labels (manual review)

---

## Next Steps After Success

1. **Production Sync with DB enabled**
   - Run full vault sync with `--sync-to-db` flag enabled by default
   - Monitor `manifest.json` for `synced_notes` and `failed_notes` counts

2. **Golden Set Maintenance**
   - Review QA confusion matrix
   - Add more examples to golden set if needed
   - Re-run predictions after prompt/model changes

3. **Automation**
   - Consider adding DB migration check to `orchestrate_obsidian_sync_production.py`
   - Add QA step to CI/CD pipeline
   - Schedule periodic vault syncs (cron job)

---

## Summary

**Files Modified/Created:**
- ✓ `migrations/001_add_source_columns_to_prp_docs.sql`
- ✓ `scripts/apply_migration.sh`
- ✓ `python/src/scripts/predict_for_golden.py`
- ✓ `artifacts/obsidian_sync_latest/` (symlink)

**Commands to Run:**
1. `./scripts/apply_migration.sh`
2. Re-run vault sync with DB enabled
3. `uv run python src/scripts/predict_for_golden.py ...`
4. `uv run python src/scripts/qa_harness.py ...`

**Expected Outcome:**
- Database sync works without errors
- QA F1 score >= 0.90 (or action items identified)
- Production orchestration pipeline is fully operational
