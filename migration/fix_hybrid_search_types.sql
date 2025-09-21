-- =====================================================
-- Fix Hybrid Search Function Type Mismatch
-- =====================================================
-- This migration fixes the PostgreSQL type mismatch error in the hybrid
-- search functions by updating VARCHAR to TEXT to match the actual
-- database schema.
-- =====================================================

BEGIN;

-- Drop existing functions first: PostgreSQL cannot change OUT parameter types via REPLACE
-- Existing signature from error hint: (vector, text, integer, jsonb, text)
DROP FUNCTION IF EXISTS hybrid_search_archon_crawled_pages(vector, text, integer, jsonb, text);
DROP FUNCTION IF EXISTS hybrid_search_archon_code_examples(vector, text, integer, jsonb, text);

-- Fix hybrid search function for archon_crawled_pages
CREATE FUNCTION hybrid_search_archon_crawled_pages(
    query_embedding vector(1536),
    query_text TEXT,
    match_count INT DEFAULT 10,
    filter JSONB DEFAULT '{}'::jsonb,
    source_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    url TEXT,  -- Changed from VARCHAR to TEXT
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
BEGIN
    -- Calculate how many results to fetch from each search type
    max_vector_results := match_count;
    max_text_results := match_count;

    RETURN QUERY
    WITH vector_results AS (
        -- Vector similarity search
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
        -- Full-text search with ranking
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
        -- Combine results from both searches
        SELECT
            COALESCE(v.id, t.id) AS id,
            COALESCE(v.url, t.url) AS url,
            COALESCE(v.chunk_number, t.chunk_number) AS chunk_number,
            COALESCE(v.content, t.content) AS content,
            COALESCE(v.metadata, t.metadata) AS metadata,
            COALESCE(v.source_id, t.source_id) AS source_id,
            -- Use vector similarity if available, otherwise text similarity
            COALESCE(v.vector_sim, t.text_sim, 0)::float8 AS similarity,
            -- Determine match type
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

-- Fix hybrid search function for archon_code_examples
CREATE FUNCTION hybrid_search_archon_code_examples(
    query_embedding vector(1536),
    query_text TEXT,
    match_count INT DEFAULT 10,
    filter JSONB DEFAULT '{}'::jsonb,
    source_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    url TEXT,  -- Changed from VARCHAR to TEXT
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
BEGIN
    -- Calculate how many results to fetch from each search type
    max_vector_results := match_count;
    max_text_results := match_count;

    RETURN QUERY
    WITH vector_results AS (
        -- Vector similarity search
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
        -- Full-text search with ranking (searches both content and summary)
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
        -- Combine results from both searches
        SELECT
            COALESCE(v.id, t.id) AS id,
            COALESCE(v.url, t.url) AS url,
            COALESCE(v.chunk_number, t.chunk_number) AS chunk_number,
            COALESCE(v.content, t.content) AS content,
            COALESCE(v.summary, t.summary) AS summary,
            COALESCE(v.metadata, t.metadata) AS metadata,
            COALESCE(v.source_id, t.source_id) AS source_id,
            -- Use vector similarity if available, otherwise text similarity
            COALESCE(v.vector_sim, t.text_sim, 0)::float8 AS similarity,
            -- Determine match type
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

-- Add comment to document the fix
COMMENT ON FUNCTION hybrid_search_archon_crawled_pages IS 'Fixed type mismatch: url column changed from VARCHAR to TEXT';
COMMENT ON FUNCTION hybrid_search_archon_code_examples IS 'Fixed type mismatch: url column changed from VARCHAR to TEXT';

COMMIT;
