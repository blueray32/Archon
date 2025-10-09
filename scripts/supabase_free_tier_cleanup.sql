\if :{?max_chunks_per_source}
\else
\set max_chunks_per_source 400
\endif

\if :{?max_versions_per_doc}
\else
\set max_versions_per_doc 5
\endif

\echo '== Supabase Free-Tier Cleanup =='
\echo 'Inspecting largest relations in public schema...'

SELECT relname AS table_name,
       pg_size_pretty(pg_total_relation_size(oid)) AS total_size,
       pg_size_pretty(pg_relation_size(oid)) AS table_size,
       pg_size_pretty(pg_total_relation_size(oid) - pg_relation_size(oid)) AS index_size,
       reltuples::bigint AS estimated_rows
FROM pg_class
WHERE relkind = 'r'
  AND relnamespace = 'public'::regnamespace
ORDER BY pg_total_relation_size(oid) DESC
LIMIT 15;

\echo ''
\echo 'Chunk distribution by source (top 20 by text size)...'

SELECT source_id,
       count(*) AS chunk_count,
       pg_size_pretty(sum(pg_column_size(content))) AS content_bytes,
       pg_size_pretty(sum(pg_column_size(embedding))) AS embedding_bytes,
       max(created_at) AS last_chunk_at
FROM public.archon_crawled_pages
GROUP BY source_id
ORDER BY sum(pg_column_size(content)) DESC
LIMIT 20;

\echo ''
\echo 'Deleting expired crawl chunks older than 60 days...'

WITH expired AS (
  SELECT id
  FROM public.archon_crawled_pages
  WHERE created_at < now() - interval '60 days'
),
deleted AS (
  DELETE FROM public.archon_crawled_pages
  WHERE id IN (SELECT id FROM expired)
  RETURNING 1
)
SELECT count(*) AS deleted_rows FROM deleted;

\echo ''
\echo 'Capping crawl chunks per source (default max: :max_chunks_per_source)...'

WITH ranked AS (
  SELECT id,
         row_number() OVER (
           PARTITION BY source_id
           ORDER BY chunk_number
         ) AS rn
  FROM public.archon_crawled_pages
),
excess AS (
  SELECT id
  FROM ranked
  WHERE rn > :max_chunks_per_source
)
deleted AS (
  DELETE FROM public.archon_crawled_pages
  WHERE id IN (SELECT id FROM excess)
  RETURNING 1
)
SELECT count(*) AS deleted_rows FROM deleted;

\echo ''
\echo 'Pruning document versions (keeping latest :max_versions_per_doc per document/field)...'

WITH ranked AS (
  SELECT id,
         row_number() OVER (
           PARTITION BY project_id, field_name, document_id
           ORDER BY created_at DESC
         ) AS rn
  FROM public.archon_document_versions
),
stale AS (
  SELECT id
  FROM ranked
  WHERE rn > :max_versions_per_doc
)
deleted AS (
  DELETE FROM public.archon_document_versions
  WHERE id IN (SELECT id FROM stale)
  RETURNING 1
)
SELECT count(*) AS deleted_rows FROM deleted;

\echo ''
\echo 'Stats after pruning (top 15 tables)...'

SELECT relname AS table_name,
       pg_size_pretty(pg_total_relation_size(oid)) AS total_size,
       pg_size_pretty(pg_relation_size(oid)) AS table_size,
       pg_size_pretty(pg_total_relation_size(oid) - pg_relation_size(oid)) AS index_size,
       reltuples::bigint AS estimated_rows
FROM pg_class
WHERE relkind = 'r'
  AND relnamespace = 'public'::regnamespace
ORDER BY pg_total_relation_size(oid) DESC
LIMIT 15;

\echo ''
\echo 'Running VACUUM ANALYZE on affected tables...'

VACUUM (ANALYZE) public.archon_crawled_pages;
VACUUM (ANALYZE) public.archon_document_versions;

\echo ''
\echo 'Cleanup complete. Consider scheduling this script nightly to stay under the free-tier cap.'
