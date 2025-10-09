-- Memory Integration for Researcher Agent
-- Extends the existing memory system for advanced research capabilities

-- Memory categories for research context
CREATE TABLE IF NOT EXISTS researcher_memory_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    priority INTEGER DEFAULT 1, -- Higher priority memories are retrieved first
    retention_days INTEGER DEFAULT 365, -- How long to keep memories of this type
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default memory categories for research
INSERT INTO researcher_memory_categories (name, description, priority, retention_days) VALUES
    ('user_preferences', 'User research preferences and habits', 10, 365),
    ('research_context', 'Ongoing research topics and context', 8, 180),
    ('entity_interest', 'Entities the user frequently asks about', 7, 180),
    ('source_preferences', 'Preferred sources and domains', 6, 365),
    ('analysis_patterns', 'Types of analysis user typically requests', 5, 180),
    ('domain_expertise', 'Areas where user has shown expertise', 9, 365),
    ('research_methodology', 'User preferred research approaches', 7, 365),
    ('fact_corrections', 'Corrections or clarifications provided by user', 10, 730)
ON CONFLICT (name) DO NOTHING;

-- Enhanced memory entries for research
CREATE TABLE IF NOT EXISTS researcher_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL, -- User identifier
    category_id UUID REFERENCES researcher_memory_categories(id),
    memory_text TEXT NOT NULL,
    context JSONB DEFAULT '{}', -- Additional context like entity mentions, sources
    confidence_score FLOAT DEFAULT 1.0,
    importance_score FLOAT DEFAULT 0.5, -- How important this memory is (0-1)
    access_count INTEGER DEFAULT 0, -- How many times this memory was accessed
    last_accessed TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE, -- When this memory should be forgotten
    embedding vector(1536), -- For semantic retrieval
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for researcher memories
CREATE INDEX IF NOT EXISTS idx_researcher_memories_user ON researcher_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_researcher_memories_category ON researcher_memories(category_id);
CREATE INDEX IF NOT EXISTS idx_researcher_memories_importance ON researcher_memories(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_researcher_memories_embedding ON researcher_memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_researcher_memories_expires ON researcher_memories(expires_at);
CREATE INDEX IF NOT EXISTS idx_researcher_memories_accessed ON researcher_memories(last_accessed);

-- Research sessions to track research context
CREATE TABLE IF NOT EXISTS research_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    session_name VARCHAR(255),
    research_topic TEXT,
    research_goals TEXT[],
    entities_of_interest UUID[], -- References to kg_entities
    sources_used TEXT[],
    key_findings TEXT[],
    session_context JSONB DEFAULT '{}',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for research sessions
CREATE INDEX IF NOT EXISTS idx_research_sessions_user ON research_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_research_sessions_topic ON research_sessions USING GIN (to_tsvector('english', research_topic));
CREATE INDEX IF NOT EXISTS idx_research_sessions_entities ON research_sessions USING GIN (entities_of_interest);
CREATE INDEX IF NOT EXISTS idx_research_sessions_timeframe ON research_sessions(started_at, ended_at);

-- Function to retrieve relevant memories for research context
CREATE OR REPLACE FUNCTION get_research_memories_for_user(
    user_id_param VARCHAR(255),
    query_text TEXT DEFAULT NULL,
    query_embedding vector(1536) DEFAULT NULL,
    max_memories INTEGER DEFAULT 10,
    min_importance FLOAT DEFAULT 0.3
)
RETURNS TABLE (
    memory_id UUID,
    category_name VARCHAR(100),
    memory_text TEXT,
    confidence_score FLOAT,
    importance_score FLOAT,
    relevance_score FLOAT,
    context JSONB,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    similarity_threshold FLOAT := 0.5;
BEGIN
    -- Update access tracking
    UPDATE researcher_memories
    SET access_count = access_count + 1, last_accessed = NOW()
    WHERE user_id = user_id_param
        AND (expires_at IS NULL OR expires_at > NOW())
        AND importance_score >= min_importance;

    -- Return memories based on embedding similarity if provided
    IF query_embedding IS NOT NULL THEN
        RETURN QUERY
        SELECT
            rm.id,
            rmc.name,
            rm.memory_text,
            rm.confidence_score,
            rm.importance_score,
            CASE
                WHEN rm.embedding IS NOT NULL THEN
                    1 - (rm.embedding <=> query_embedding)
                ELSE 0.0
            END as relevance,
            rm.context,
            rm.created_at
        FROM researcher_memories rm
        JOIN researcher_memory_categories rmc ON rm.category_id = rmc.id
        WHERE rm.user_id = user_id_param
            AND (rm.expires_at IS NULL OR rm.expires_at > NOW())
            AND rm.importance_score >= min_importance
            AND rm.embedding IS NOT NULL
            AND 1 - (rm.embedding <=> query_embedding) > similarity_threshold
        ORDER BY
            rmc.priority DESC,
            (1 - (rm.embedding <=> query_embedding)) DESC,
            rm.importance_score DESC,
            rm.access_count DESC
        LIMIT max_memories;

    -- Text-based search if no embedding provided
    ELSIF query_text IS NOT NULL THEN
        RETURN QUERY
        SELECT
            rm.id,
            rmc.name,
            rm.memory_text,
            rm.confidence_score,
            rm.importance_score,
            CASE
                WHEN rm.memory_text ILIKE '%' || query_text || '%' THEN 1.0
                ELSE similarity(rm.memory_text, query_text)
            END as relevance,
            rm.context,
            rm.created_at
        FROM researcher_memories rm
        JOIN researcher_memory_categories rmc ON rm.category_id = rmc.id
        WHERE rm.user_id = user_id_param
            AND (rm.expires_at IS NULL OR rm.expires_at > NOW())
            AND rm.importance_score >= min_importance
            AND (
                rm.memory_text ILIKE '%' || query_text || '%'
                OR similarity(rm.memory_text, query_text) > 0.3
            )
        ORDER BY
            rmc.priority DESC,
            relevance DESC,
            rm.importance_score DESC,
            rm.access_count DESC
        LIMIT max_memories;

    -- Return general high-priority memories
    ELSE
        RETURN QUERY
        SELECT
            rm.id,
            rmc.name,
            rm.memory_text,
            rm.confidence_score,
            rm.importance_score,
            rm.importance_score as relevance, -- Use importance as relevance
            rm.context,
            rm.created_at
        FROM researcher_memories rm
        JOIN researcher_memory_categories rmc ON rm.category_id = rmc.id
        WHERE rm.user_id = user_id_param
            AND (rm.expires_at IS NULL OR rm.expires_at > NOW())
            AND rm.importance_score >= min_importance
        ORDER BY
            rmc.priority DESC,
            rm.importance_score DESC,
            rm.access_count DESC,
            rm.created_at DESC
        LIMIT max_memories;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to store research memory
CREATE OR REPLACE FUNCTION store_research_memory(
    user_id_param VARCHAR(255),
    category_name VARCHAR(100),
    memory_text_param TEXT,
    context_param JSONB DEFAULT '{}',
    confidence_param FLOAT DEFAULT 1.0,
    importance_param FLOAT DEFAULT 0.5,
    embedding_param vector(1536) DEFAULT NULL,
    retention_days_override INTEGER DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    category_uuid UUID;
    memory_uuid UUID;
    expiry_date TIMESTAMP WITH TIME ZONE;
    default_retention INTEGER;
BEGIN
    -- Get category ID and retention period
    SELECT id, retention_days INTO category_uuid, default_retention
    FROM researcher_memory_categories
    WHERE name = category_name;

    IF category_uuid IS NULL THEN
        RAISE EXCEPTION 'Memory category % not found', category_name;
    END IF;

    -- Calculate expiry date
    IF retention_days_override IS NOT NULL THEN
        expiry_date := NOW() + (retention_days_override || ' days')::INTERVAL;
    ELSIF default_retention IS NOT NULL THEN
        expiry_date := NOW() + (default_retention || ' days')::INTERVAL;
    ELSE
        expiry_date := NULL; -- Never expires
    END IF;

    -- Insert memory
    INSERT INTO researcher_memories (
        user_id,
        category_id,
        memory_text,
        context,
        confidence_score,
        importance_score,
        embedding,
        expires_at
    ) VALUES (
        user_id_param,
        category_uuid,
        memory_text_param,
        context_param,
        confidence_param,
        importance_param,
        embedding_param,
        expiry_date
    ) RETURNING id INTO memory_uuid;

    RETURN memory_uuid;
END;
$$ LANGUAGE plpgsql;

-- Function to update memory importance based on access patterns
CREATE OR REPLACE FUNCTION update_memory_importance()
RETURNS VOID AS $$
BEGIN
    -- Increase importance for frequently accessed memories
    UPDATE researcher_memories
    SET importance_score = LEAST(1.0, importance_score + (access_count * 0.01))
    WHERE access_count > 5
        AND last_accessed > NOW() - INTERVAL '30 days';

    -- Decrease importance for old, unused memories
    UPDATE researcher_memories
    SET importance_score = GREATEST(0.1, importance_score - 0.1)
    WHERE last_accessed < NOW() - INTERVAL '90 days'
        AND access_count < 3;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up expired memories
CREATE OR REPLACE FUNCTION cleanup_expired_memories()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM researcher_memories
    WHERE expires_at IS NOT NULL
        AND expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Add update trigger for researcher memories
DROP TRIGGER IF EXISTS update_researcher_memories_modtime ON researcher_memories;
CREATE TRIGGER update_researcher_memories_modtime
    BEFORE UPDATE ON researcher_memories
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

-- Scheduled cleanup of expired memories (requires pg_cron extension)
-- SELECT cron.schedule('cleanup-memories', '0 2 * * *', 'SELECT cleanup_expired_memories();');
-- SELECT cron.schedule('update-memory-importance', '0 3 * * 0', 'SELECT update_memory_importance();');

COMMENT ON TABLE researcher_memories IS 'Enhanced memories for research context and personalization';
COMMENT ON TABLE research_sessions IS 'Track research sessions and context for continuity';
COMMENT ON FUNCTION get_research_memories_for_user IS 'Retrieve relevant memories for research context';