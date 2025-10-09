-- Keyword-only search functions to complement hybrid search

CREATE OR REPLACE FUNCTION keyword_search_archon_crawled_pages(
    query_text TEXT,
    match_count INT DEFAULT 10,
    filter JSONB DEFAULT '{}'::jsonb,
    source_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    url VARCHAR,
    chunk_number INTEGER,
    content TEXT,
    metadata JSONB,
    source_id TEXT,
    similarity FLOAT,
    match_type TEXT
)
LANGUAGE sql
AS $$
SELECT 
    cp.id,
    cp.url,
    cp.chunk_number,
    cp.content,
    cp.metadata,
    cp.source_id,
    ts_rank_cd(cp.content_search_vector, plainto_tsquery('english', query_text)) AS similarity,
    'keyword' AS match_type
FROM archon_crawled_pages cp
WHERE cp.metadata @> filter
  AND (source_filter IS NULL OR cp.source_id = source_filter)
  AND cp.content_search_vector @@ plainto_tsquery('english', query_text)
ORDER BY similarity DESC
LIMIT match_count;
$$;

