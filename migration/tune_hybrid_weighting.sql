-- =====================================================
-- Hybrid Search Relevance Tuning (Weighted Similarity)
-- =====================================================
-- This migration updates the hybrid search functions to compute a weighted
-- combination of vector similarity and text rank when both signals exist.
--
-- Design goals:
-- - Keep function signatures unchanged (safe rollout)
-- - Weight vector vs. text contributions (defaults: 0.7 vs. 0.3)
-- - Clamp text rank to [0,1] to avoid dominating the score
-- - If only one signal exists, use just that signal (weighted)
-- =====================================================

BEGIN;

-- Tunable weights (adjust and re-run migration if needed)
-- NOTE: Kept inside SQL to avoid app-level signature changes.
--       Defaults chosen for semantic-first retrieval with keyword support.
--       If you want app-level tuning, create a follow-up migration adding
--       function parameters and pass weights from the backend service.

-- Recreate hybrid search for crawled pages with weighted similarity
DROP FUNCTION IF EXISTS hybrid_search_archon_crawled_pages(vector, text, integer, jsonb, text);
CREATE FUNCTION hybrid_search_archon_crawled_pages(
    query_embedding vector(1536),
    query_text TEXT,
    match_count INT DEFAULT 10,
    filter JSONB DEFAULT '{}'::jsonb,
    source_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    url TEXT,
    chunk_number INTEGER,
    content TEXT,
    metadata JSONB,
    source_id TEXT,
    similarity FLOAT,
    match_type TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    max_vector_results INT;
    max_text_results INT;
    vector_weight FLOAT := 0.5;
    text_weight   FLOAT := 0.5;
BEGIN
    max_vector_results := match_count;
    max_text_results := match_count;

    RETURN QUERY
    WITH vector_results AS (
        SELECT
            cp.id,
            cp.url,
            cp.chunk_number,
            cp.content,
            cp.metadata,
            cp.source_id,
            1 - (cp.embedding <=> query_embedding) AS vector_sim
        FROM archon_crawled_pages cp
        WHERE cp.metadata @> filter
          AND (source_filter IS NULL OR cp.source_id = source_filter)
          AND cp.embedding IS NOT NULL
        ORDER BY cp.embedding <=> query_embedding
        LIMIT max_vector_results
    ),
    text_results AS (
        SELECT
            cp.id,
            cp.url,
            cp.chunk_number,
            cp.content,
            cp.metadata,
            cp.source_id,
            ts_rank_cd(cp.content_search_vector, plainto_tsquery('english', query_text)) AS text_sim
        FROM archon_crawled_pages cp
        WHERE cp.metadata @> filter
          AND (source_filter IS NULL OR cp.source_id = source_filter)
          AND cp.content_search_vector @@ plainto_tsquery('english', query_text)
        ORDER BY text_sim DESC
        LIMIT max_text_results
    ),
    combined_results AS (
        SELECT
            COALESCE(v.id, t.id) AS id,
            COALESCE(v.url, t.url) AS url,
            COALESCE(v.chunk_number, t.chunk_number) AS chunk_number,
            COALESCE(v.content, t.content) AS content,
            COALESCE(v.metadata, t.metadata) AS metadata,
            COALESCE(v.source_id, t.source_id) AS source_id,
            -- Weighted combination (clamp text rank to [0,1])
            (
                (CASE WHEN v.id IS NOT NULL THEN vector_weight * GREATEST(0, v.vector_sim) ELSE 0 END)
              + (CASE WHEN t.id IS NOT NULL THEN text_weight * LEAST(1.0, t.text_sim) ELSE 0 END)
            )::float8 AS similarity,
            CASE
                WHEN v.id IS NOT NULL AND t.id IS NOT NULL THEN 'hybrid'
                WHEN v.id IS NOT NULL THEN 'vector'
                ELSE 'keyword'
            END AS match_type
        FROM vector_results v
        FULL OUTER JOIN text_results t ON v.id = t.id
    )
    SELECT * FROM combined_results
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

-- Recreate hybrid search for code examples with weighted similarity
DROP FUNCTION IF EXISTS hybrid_search_archon_code_examples(vector, text, integer, jsonb, text);
CREATE FUNCTION hybrid_search_archon_code_examples(
    query_embedding vector(1536),
    query_text TEXT,
    match_count INT DEFAULT 10,
    filter JSONB DEFAULT '{}'::jsonb,
    source_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    url TEXT,
    chunk_number INTEGER,
    content TEXT,
    summary TEXT,
    metadata JSONB,
    source_id TEXT,
    similarity FLOAT,
    match_type TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    max_vector_results INT;
    max_text_results INT;
    vector_weight FLOAT := 0.5;
    text_weight   FLOAT := 0.5;
BEGIN
    max_vector_results := match_count;
    max_text_results := match_count;

    RETURN QUERY
    WITH vector_results AS (
        SELECT
            ce.id,
            ce.url,
            ce.chunk_number,
            ce.content,
            ce.summary,
            ce.metadata,
            ce.source_id,
            1 - (ce.embedding <=> query_embedding) AS vector_sim
        FROM archon_code_examples ce
        WHERE ce.metadata @> filter
          AND (source_filter IS NULL OR ce.source_id = source_filter)
          AND ce.embedding IS NOT NULL
        ORDER BY ce.embedding <=> query_embedding
        LIMIT max_vector_results
    ),
    text_results AS (
        SELECT
            ce.id,
            ce.url,
            ce.chunk_number,
            ce.content,
            ce.summary,
            ce.metadata,
            ce.source_id,
            ts_rank_cd(ce.content_search_vector, plainto_tsquery('english', query_text)) AS text_sim
        FROM archon_code_examples ce
        WHERE ce.metadata @> filter
          AND (source_filter IS NULL OR ce.source_id = source_filter)
          AND ce.content_search_vector @@ plainto_tsquery('english', query_text)
        ORDER BY text_sim DESC
        LIMIT max_text_results
    ),
    combined_results AS (
        SELECT
            COALESCE(v.id, t.id) AS id,
            COALESCE(v.url, t.url) AS url,
            COALESCE(v.chunk_number, t.chunk_number) AS chunk_number,
            COALESCE(v.content, t.content) AS content,
            COALESCE(v.summary, t.summary) AS summary,
            COALESCE(v.metadata, t.metadata) AS metadata,
            COALESCE(v.source_id, t.source_id) AS source_id,
            (
                (CASE WHEN v.id IS NOT NULL THEN vector_weight * GREATEST(0, v.vector_sim) ELSE 0 END)
              + (CASE WHEN t.id IS NOT NULL THEN text_weight * LEAST(1.0, t.text_sim) ELSE 0 END)
            )::float8 AS similarity,
            CASE
                WHEN v.id IS NOT NULL AND t.id IS NOT NULL THEN 'hybrid'
                WHEN v.id IS NOT NULL THEN 'vector'
                ELSE 'keyword'
            END AS match_type
        FROM vector_results v
        FULL OUTER JOIN text_results t ON v.id = t.id
    )
    SELECT * FROM combined_results
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

COMMIT;
