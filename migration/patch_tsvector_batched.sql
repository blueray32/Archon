-- Batched setup for text search on archon_crawled_pages without high maintenance_work_mem

-- 1) Ensure the tsvector column exists (non-generated to avoid heavy immediate compute)
ALTER TABLE archon_crawled_pages 
  ADD COLUMN IF NOT EXISTS content_search_vector tsvector;

-- 2) Backfill in small batches to avoid spikes
DO $$
DECLARE
  v_rows integer := 0;
BEGIN
  LOOP
    WITH batch AS (
      SELECT id
      FROM archon_crawled_pages
      WHERE content_search_vector IS NULL
      LIMIT 500
    )
    UPDATE archon_crawled_pages t
    SET content_search_vector = to_tsvector('english', t.content)
    FROM batch
    WHERE t.id = batch.id;

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    EXIT WHEN v_rows = 0;
  END LOOP;
END $$;

-- 3) Create the GIN index concurrently (avoid long locks). If memory still tight, this can be skipped safely.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_archon_crawled_pages_content_search
  ON archon_crawled_pages USING GIN (content_search_vector);

