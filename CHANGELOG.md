# Changelog

All notable changes to this project will be documented in this file.

## 2025-09-21

### Added
- Hybrid similarity weighting in PostgreSQL hybrid functions (final default 50/50 vector/keyword) for improved relevance.
- Embeddings maintenance APIs:
  - `GET /api/embeddings/health` — per‑table totals/missing/with_embedding.
  - `POST /api/embeddings/backfill` — batch re‑embedding with `dry_run`, `limit`, `batch_size`, optional `source_id`.
- MCP session helpers for debugging:
  - `POST /api/mcp/session/init` — initializes and returns a session ID.
  - `GET /api/mcp/session/info` — initializes then calls `session_info` tool.
- Lightweight retrieval evaluation script: `scripts/rag_eval.py`.
- Migration guide: `migration/README.md`.

### Fixed
- Hybrid RAG returned zero results due to PostgreSQL function result type mismatch (`url` declared `VARCHAR` vs. table `TEXT`).
  - Dropped and recreated functions with `url TEXT`: `migration/fix_hybrid_search_types.sql`.
- Health endpoint now detects hybrid function mismatch and returns `migration_required` with clear instructions.
- Hybrid search logging now includes full stack traces (no silent failures); fallback to vector search when hybrid yields zero results.

### Changed
- Default recall threshold via compose: `SEARCH_SIMILARITY_THRESHOLD=0.05` (can override in `.env`).
- Weighted hybrid similarity and final default locked in migration: `migration/tune_hybrid_weighting.sql` (50/50).

### Migration order
1. If `/health` indicates a hybrid type mismatch (error 42804), run `migration/fix_hybrid_search_types.sql`.
2. Run `migration/tune_hybrid_weighting.sql` to apply the 50/50 weighting.

