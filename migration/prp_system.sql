-- =====================================================
-- PRP (Product Requirement Prompt) System Setup
-- =====================================================
-- This migration adds support for PRP-driven agent chat
-- with persistent memory using pgvector for RAG retrieval
-- =====================================================

-- Enable vector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================
-- Chat Messages Table
-- =====================================================
-- Stores chat messages with embeddings for context retrieval
CREATE TABLE IF NOT EXISTS prp_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    agent_type TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    embedding VECTOR(1536)  -- text-embedding-3-small dimension
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_prp_messages_session ON prp_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_prp_messages_created_at ON prp_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_prp_messages_role ON prp_messages(role);
CREATE INDEX IF NOT EXISTS idx_prp_messages_agent_type ON prp_messages(agent_type);

-- Vector similarity search index (HNSW for fast approximate nearest neighbor)
CREATE INDEX IF NOT EXISTS idx_prp_messages_embedding ON prp_messages
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- =====================================================
-- PRP Documents Table
-- =====================================================
-- Stores PRP documents and supporting documentation
CREATE TABLE IF NOT EXISTS prp_docs (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('prp', 'doc', 'persona')),
    path TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    embedding VECTOR(1536)  -- text-embedding-3-small dimension
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_prp_docs_kind ON prp_docs(kind);
CREATE INDEX IF NOT EXISTS idx_prp_docs_path ON prp_docs(path);
CREATE INDEX IF NOT EXISTS idx_prp_docs_created_at ON prp_docs(created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_prp_docs_kind_path ON prp_docs(kind, path);

-- Vector similarity search index
CREATE INDEX IF NOT EXISTS idx_prp_docs_embedding ON prp_docs
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Create trigger to automatically update updated_at timestamp
CREATE TRIGGER update_prp_docs_updated_at
    BEFORE UPDATE ON prp_docs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- Persona Configurations Table
-- =====================================================
-- Stores agent persona configurations (system prompts, rules, etc.)
CREATE TABLE IF NOT EXISTS prp_personas (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    display_name TEXT,
    description TEXT,
    system_prompt TEXT NOT NULL,
    configuration JSONB DEFAULT '{}'::jsonb,  -- Store YAML/JSON config
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_prp_personas_name ON prp_personas(name);
CREATE INDEX IF NOT EXISTS idx_prp_personas_is_active ON prp_personas(is_active);

-- Create trigger to automatically update updated_at timestamp
CREATE TRIGGER update_prp_personas_updated_at
    BEFORE UPDATE ON prp_personas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- PRP Settings
-- =====================================================
-- Add PRP-specific settings to archon_settings
INSERT INTO archon_settings (key, value, is_encrypted, category, description) VALUES
('PRP_ENABLED', 'true', false, 'features', 'Enable PRP-driven agent chat with persistent memory'),
('PRP_RAG_TOP_K', '6', false, 'prp', 'Number of top context items to retrieve from memory'),
('PRP_MAX_CONTEXT_CHARS', '60000', false, 'prp', 'Maximum character limit for context injection'),
('PRP_DEFAULT_PERSONA', 'chat_gpt_like', false, 'prp', 'Default persona for PRP agent interactions'),
('PRP_EMBEDDING_MODEL', 'text-embedding-3-small', false, 'prp', 'Embedding model for PRP memory (OpenAI)'),
('PRP_CHAT_MODEL', 'gpt-4o-mini', false, 'prp', 'Chat model for PRP agent (OpenAI)'),
('PRP_STREAM_ENABLED', 'true', false, 'prp', 'Enable streaming responses for PRP chat')
ON CONFLICT (key) DO NOTHING;

-- =====================================================
-- Helper Functions
-- =====================================================

-- Function to search PRP messages by vector similarity
CREATE OR REPLACE FUNCTION search_prp_messages(
    query_embedding VECTOR(1536),
    session_filter TEXT DEFAULT NULL,
    match_count INT DEFAULT 10,
    similarity_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    id BIGINT,
    session_id TEXT,
    role TEXT,
    content TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.session_id,
        m.role,
        m.content,
        1 - (m.embedding <=> query_embedding) AS similarity
    FROM prp_messages m
    WHERE
        (session_filter IS NULL OR m.session_id = session_filter)
        AND 1 - (m.embedding <=> query_embedding) > similarity_threshold
    ORDER BY m.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Function to search PRP docs by vector similarity
CREATE OR REPLACE FUNCTION search_prp_docs(
    query_embedding VECTOR(1536),
    kind_filter TEXT DEFAULT NULL,
    match_count INT DEFAULT 5,
    similarity_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    id BIGINT,
    kind TEXT,
    path TEXT,
    title TEXT,
    content TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.kind,
        d.path,
        d.title,
        d.content,
        1 - (d.embedding <=> query_embedding) AS similarity
    FROM prp_docs d
    WHERE
        (kind_filter IS NULL OR d.kind = kind_filter)
        AND 1 - (d.embedding <=> query_embedding) > similarity_threshold
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- RLS Policies
-- =====================================================

-- Enable RLS
ALTER TABLE prp_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE prp_docs ENABLE ROW LEVEL SECURITY;
ALTER TABLE prp_personas ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY "Allow service role full access on prp_messages" ON prp_messages
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow service role full access on prp_docs" ON prp_docs
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow service role full access on prp_personas" ON prp_personas
    FOR ALL USING (auth.role() = 'service_role');

-- Allow authenticated users read access
CREATE POLICY "Allow authenticated read on prp_messages" ON prp_messages
    FOR SELECT TO authenticated USING (true);

CREATE POLICY "Allow authenticated read on prp_docs" ON prp_docs
    FOR SELECT TO authenticated USING (true);

CREATE POLICY "Allow authenticated read on prp_personas" ON prp_personas
    FOR SELECT TO authenticated USING (true);

-- =====================================================
-- Initial Data
-- =====================================================

-- Insert default ChatGPT-like persona
INSERT INTO prp_personas (name, display_name, description, system_prompt, configuration) VALUES
(
    'chat_gpt_like',
    'ChatGPT-Like Assistant',
    'A helpful engineering copilot with a warm, practical tone',
    'You are a helpful engineering copilot. Behave like ChatGPT:
- Clear, actionable explanations, minimal fluff.
- Numbered steps when appropriate.
- If unsure, state assumptions and proceed with best effort.
- Maintain continuity by recalling prior context from memory.

Use retrieved context from PRPs and previous conversations to provide informed responses.',
    '{
        "tone": "warm, practical, down-to-earth",
        "style": "friendly, concise, step-by-step",
        "goals": [
            "Be friendly, concise, step-by-step, and proactive",
            "Offer runnable commands and next actions when helpful",
            "Maintain continuity using retrieved memory"
        ],
        "constraints": [
            "Avoid fluff; keep answers scoped to the ask",
            "Use numbered steps for procedures; fenced code for commands"
        ],
        "safety": {
            "refuse": ["illegal/dangerous content", "medical/legal advice beyond general info"],
            "redactions": ["Never output secrets or raw tokens"]
        }
    }'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    system_prompt = EXCLUDED.system_prompt,
    configuration = EXCLUDED.configuration,
    updated_at = NOW();

-- =====================================================
-- Completion Message
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE 'PRP system setup complete!';
    RAISE NOTICE 'Tables created: prp_messages, prp_docs, prp_personas';
    RAISE NOTICE 'Helper functions created: search_prp_messages, search_prp_docs';
    RAISE NOTICE 'Default persona created: chat_gpt_like';
END $$;