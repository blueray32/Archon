Hybrid Search Migrations

Overview
- The hybrid search functions combine vector similarity with keyword (tsvector) ranking to improve result quality.
- We currently use balanced weighting (50% vector, 50% keyword) based on quick evaluation across representative queries.

Key files
- `migration/fix_hybrid_search_types.sql` — fixes PostgreSQL function result type mismatch (sets `url` to `TEXT`). Run this first if health reports a hybrid type error.
- `migration/tune_hybrid_weighting.sql` — sets the weighting used to combine vector and keyword signals in the hybrid functions.

When to run these
- Type fix: When `/health` returns `migration_required` with message about hybrid function type mismatch, or if searches return empty with DB error 42804 (structure does not match function result type). Run `fix_hybrid_search_types.sql`.
- Weight tuning: To adjust relevance bias between semantic (vector) and keyword matches. Run `tune_hybrid_weighting.sql`.

Current default (selected)
- Balanced weighting: `vector_weight = 0.5`, `text_weight = 0.5` in `tune_hybrid_weighting.sql`.

How to apply
1) Supabase Dashboard → SQL Editor → paste file contents.
2) Execute the SQL (safe to run multiple times; functions are dropped/recreated).

How to tune weights
- Edit `vector_weight` and `text_weight` inside `tune_hybrid_weighting.sql` (same for both functions):
  - More semantic bias: `vector_weight = 0.7`, `text_weight = 0.3`.
  - More keyword bias: `vector_weight = 0.4`, `text_weight = 0.6`.
- Re-run the file in the SQL Editor to apply.

Verification
- Health: `curl -s http://localhost:8181/health | jq '.'` → expect `"status": "healthy"` and `"search_schema_valid": true`.
- Query: `curl -s "http://localhost:8181/api/rag/query" -H "Content-Type: application/json" -d '{"query":"test","match_count":5}' | jq '.'`.

Optional recall threshold
- The backend filters vector results using `SEARCH_SIMILARITY_THRESHOLD` (default `0.10`). Lower for broader recall, e.g. `0.05`.
- Set the environment variable and restart `archon-server` to apply.

Notes
- Never store corrupted data or fallback zeros; failures should be logged with context (see logging in hybrid strategy).
- Keep DB and repo in sync: after settling on weights, ensure `tune_hybrid_weighting.sql` reflects the intended default.

