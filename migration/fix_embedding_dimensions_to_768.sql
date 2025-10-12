-- =====================================================
-- Fix Embedding Dimensions for Ollama (768D)
-- =====================================================
-- This migration updates the embedding columns from 1536D (OpenAI)
-- to 768D (Ollama nomic-embed-text) and recreates dependent functions
--
-- WARNING: This will delete all existing embeddings!
-- You'll need to re-index your knowledge base after running this.
-- =====================================================

BEGIN;

-- Drop dependent functions first (they reference the vector dimensions)
DROP FUNCTION IF EXISTS match_archon_crawled_pages(vector, int, jsonb, text);
DROP FUNCTION IF EXISTS match_archon_code_examples(vector, int, jsonb, text);
DROP FUNCTION IF EXISTS hybrid_search_archon_crawled_pages(vector, text, int, jsonb, text);
DROP FUNCTION IF EXISTS hybrid_search_archon_code_examples(vector, text, int, jsonb, text);

-- Drop the vector indexes (they're dimension-specific)
DROP INDEX IF EXISTS archon_crawled_pages_embedding_idx;
DROP INDEX IF EXISTS archon_code_examples_embedding_idx;

-- Clear existing embeddings (they're the wrong dimension)
UPDATE archon_crawled_pages SET embedding = NULL;
UPDATE archon_code_examples SET embedding = NULL;

-- Alter the embedding columns to 768 dimensions
ALTER TABLE archon_crawled_pages
  ALTER COLUMN embedding TYPE VECTOR(768);

ALTER TABLE archon_code_examples
  ALTER COLUMN embedding TYPE VECTOR(768);

-- Recreate the vector indexes with 768 dimensions
CREATE INDEX archon_crawled_pages_embedding_idx
  ON archon_crawled_pages USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX archon_code_examples_embedding_idx
  ON archon_code_examples USING ivfflat (embedding vector_cosine_ops);

-- Recreate match functions with 768 dimensions
CREATE OR REPLACE FUNCTION match_archon_crawled_pages (
  query_embedding VECTOR(768),
  match_count INT DEFAULT 10,
  filter JSONB DEFAULT '{}'::jsonb,
  source_filter TEXT DEFAULT NULL
) RETURNS TABLE (
  id BIGINT,
  url VARCHAR,
  chunk_number INTEGER,
  content TEXT,
  metadata JSONB,
  source_id TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column
BEGIN
  RETURN QUERY
  SELECT
    id,
    url,
    chunk_number,
    content,
    metadata,
    source_id,
    1 - (archon_crawled_pages.embedding <=> query_embedding) AS similarity
  FROM archon_crawled_pages
  WHERE metadata @> filter
    AND (source_filter IS NULL OR source_id = source_filter)
    AND embedding IS NOT NULL
  ORDER BY archon_crawled_pages.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

CREATE OR REPLACE FUNCTION match_archon_code_examples (
  query_embedding VECTOR(768),
  match_count INT DEFAULT 10,
  filter JSONB DEFAULT '{}'::jsonb,
  source_filter TEXT DEFAULT NULL
) RETURNS TABLE (
  id BIGINT,
  url VARCHAR,
  chunk_number INTEGER,
  content TEXT,
  summary TEXT,
  metadata JSONB,
  source_id TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column
BEGIN
  RETURN QUERY
  SELECT
    id,
    url,
    chunk_number,
    content,
    summary,
    metadata,
    source_id,
    1 - (archon_code_examples.embedding <=> query_embedding) AS similarity
  FROM archon_code_examples
  WHERE metadata @> filter
    AND (source_filter IS NULL OR source_id = source_filter)
    AND embedding IS NOT NULL
  ORDER BY archon_code_examples.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Recreate hybrid search functions with 768 dimensions
CREATE OR REPLACE FUNCTION hybrid_search_archon_crawled_pages(
    query_embedding vector(768),
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
LANGUAGE plpgsql
AS $$
DECLARE
    max_vector_results INT;
    max_text_results INT;
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
            COALESCE(v.vector_sim, t.text_sim, 0)::float8 AS similarity,
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

CREATE OR REPLACE FUNCTION hybrid_search_archon_code_examples(
    query_embedding vector(768),
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
            COALESCE(v.vector_sim, t.text_sim, 0)::float8 AS similarity,
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

-- Update settings to reflect 768 dimensions
UPDATE archon_settings
SET value = '768', description = 'Embedding dimensions - 768 for Ollama nomic-embed-text, 1536 for OpenAI'
WHERE key = 'EMBEDDING_DIMENSIONS';

-- Insert dimension setting if it doesn't exist
INSERT INTO archon_settings (key, value, is_encrypted, category, description)
VALUES ('EMBEDDING_DIMENSIONS', '768', false, 'rag_strategy', 'Embedding dimensions - 768 for Ollama nomic-embed-text, 1536 for OpenAI')
ON CONFLICT (key) DO UPDATE SET value = '768';

COMMIT;

-- =====================================================
-- Migration Complete
-- =====================================================
-- Next steps:
-- 1. Re-index all your knowledge sources from the UI
-- 2. Verify embeddings are being created correctly
-- =====================================================
