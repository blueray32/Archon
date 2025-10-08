# fix: Obsidian vault sync infrastructure with critical upsert fix

## Summary
Adds production-ready Obsidian vault sync infrastructure with critical bug fix preventing duplicate key errors during sync operations.

## Key Changes

### Critical Fix
- **archon_memory_sync.py**: Changed `.insert()` to `.upsert(on_conflict="kind,path")`
  - Prevents 6635+ duplicate key violations on incremental syncs
  - Enables idempotent sync operations

### New Infrastructure
- **orchestrate_obsidian_sync_production.py**: Production orchestration script
  - Scans vault, auto-tags, creates embeddings, syncs to DB
  - Supports concurrency, sharding, resume, dry-run modes
  - `--sync-to-db` flag for DB-only operations

### Database Migration
- **migrations/001_add_source_columns_to_prp_docs.sql**
  - Adds `source_type`, `source_path`, `updated_at` columns
  - Creates indexes for efficient source lookups
  - Idempotent (safe to re-run)

### Additional Features
- Archon workflow automation
- BIM specialist persona with APS Data Exchange integration
- QA harness and prediction pipeline
- Weekly review infrastructure

## Test Results
✓ Full vault sync: **6635/6635 notes** synced successfully
✓ Duration: 6m 41s
✓ Zero failures

## Migration Required
Apply DB migration via Supabase SQL Editor:
```sql
-- See migrations/001_add_source_columns_to_prp_docs.sql
```

## Related Work
- Includes commits from feature-bim-demo, feature-weekly-review, and workflow automation
- Foundation for production Obsidian sync pipeline

🤖 Generated with [Claude Code](https://claude.com/claude-code)
