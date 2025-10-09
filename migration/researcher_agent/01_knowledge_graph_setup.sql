-- Knowledge Graph Extensions for Researcher Agent
-- Adds support for entity extraction, relationships, and temporal analysis

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Entity types table
CREATE TABLE IF NOT EXISTS kg_entity_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default entity types
INSERT INTO kg_entity_types (name, description) VALUES
    ('PERSON', 'People, individuals, and persons'),
    ('ORGANIZATION', 'Companies, institutions, and organizations'),
    ('LOCATION', 'Places, cities, countries, and geographic locations'),
    ('TECHNOLOGY', 'Software, frameworks, tools, and technologies'),
    ('CONCEPT', 'Abstract concepts and ideas'),
    ('EVENT', 'Events, meetings, and occurrences'),
    ('PRODUCT', 'Products, services, and offerings'),
    ('DOCUMENT', 'Files, papers, and documentation')
ON CONFLICT (name) DO NOTHING;

-- Entities table for knowledge graph
CREATE TABLE IF NOT EXISTS kg_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    entity_type_id UUID REFERENCES kg_entity_types(id),
    description TEXT,
    aliases TEXT[], -- Alternative names for the entity
    confidence_score FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536), -- For semantic similarity
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for entities
CREATE INDEX IF NOT EXISTS idx_kg_entities_name ON kg_entities USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_kg_entities_type ON kg_entities(entity_type_id);
CREATE INDEX IF NOT EXISTS idx_kg_entities_embedding ON kg_entities USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_kg_entities_metadata ON kg_entities USING GIN (metadata);

-- Relationship types table
CREATE TABLE IF NOT EXISTS kg_relationship_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    directional BOOLEAN DEFAULT true, -- Whether the relationship has direction
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default relationship types
INSERT INTO kg_relationship_types (name, description, directional) VALUES
    ('WORKS_FOR', 'Person works for organization', true),
    ('LOCATED_IN', 'Entity is located in location', true),
    ('USES', 'Entity uses technology or tool', true),
    ('CREATED_BY', 'Product or concept created by entity', true),
    ('PART_OF', 'Entity is part of larger entity', true),
    ('RELATED_TO', 'General relationship between entities', false),
    ('MENTIONED_WITH', 'Entities mentioned together in documents', false),
    ('COLLABORATED_ON', 'Entities worked together on something', false),
    ('ACQUIRED_BY', 'Entity acquired by another entity', true),
    ('COMPETITOR_OF', 'Entities are competitors', false)
ON CONFLICT (name) DO NOTHING;

-- Entity relationships table
CREATE TABLE IF NOT EXISTS kg_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id UUID REFERENCES kg_entities(id) ON DELETE CASCADE,
    target_entity_id UUID REFERENCES kg_entities(id) ON DELETE CASCADE,
    relationship_type_id UUID REFERENCES kg_relationship_types(id),
    confidence_score FLOAT DEFAULT 1.0,
    context TEXT, -- Context where this relationship was discovered
    document_id UUID, -- Source document if applicable
    metadata JSONB DEFAULT '{}',
    start_date TIMESTAMP WITH TIME ZONE, -- When relationship started
    end_date TIMESTAMP WITH TIME ZONE, -- When relationship ended (null if ongoing)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT no_self_relationship CHECK (source_entity_id != target_entity_id)
);

-- Create indexes for relationships
CREATE INDEX IF NOT EXISTS idx_kg_relationships_source ON kg_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_relationships_target ON kg_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_relationships_type ON kg_relationships(relationship_type_id);
CREATE INDEX IF NOT EXISTS idx_kg_relationships_temporal ON kg_relationships(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_kg_relationships_document ON kg_relationships(document_id);

-- Entity mentions in documents
CREATE TABLE IF NOT EXISTS kg_entity_mentions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES kg_entities(id) ON DELETE CASCADE,
    document_id UUID NOT NULL, -- Reference to documents table
    mention_text TEXT NOT NULL,
    context TEXT, -- Surrounding context
    confidence_score FLOAT DEFAULT 1.0,
    start_position INTEGER, -- Character position in document
    end_position INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for entity mentions
CREATE INDEX IF NOT EXISTS idx_kg_mentions_entity ON kg_entity_mentions(entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_mentions_document ON kg_entity_mentions(document_id);
CREATE INDEX IF NOT EXISTS idx_kg_mentions_text ON kg_entity_mentions USING GIN (mention_text gin_trgm_ops);

-- Entity facts for temporal analysis
CREATE TABLE IF NOT EXISTS kg_entity_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES kg_entities(id) ON DELETE CASCADE,
    fact_type VARCHAR(100) NOT NULL, -- e.g., 'status_change', 'attribute_update'
    fact_text TEXT NOT NULL,
    confidence_score FLOAT DEFAULT 1.0,
    document_id UUID, -- Source document
    fact_date TIMESTAMP WITH TIME ZONE, -- When the fact occurred
    valid_from TIMESTAMP WITH TIME ZONE, -- When fact became valid
    valid_until TIMESTAMP WITH TIME ZONE, -- When fact stopped being valid
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for entity facts
CREATE INDEX IF NOT EXISTS idx_kg_facts_entity ON kg_entity_facts(entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_facts_type ON kg_entity_facts(fact_type);
CREATE INDEX IF NOT EXISTS idx_kg_facts_temporal ON kg_entity_facts(fact_date, valid_from, valid_until);
CREATE INDEX IF NOT EXISTS idx_kg_facts_document ON kg_entity_facts(document_id);

-- Function to find similar entities by name
CREATE OR REPLACE FUNCTION kg_find_similar_entities(
    query_name TEXT,
    similarity_threshold FLOAT DEFAULT 0.3,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    entity_id UUID,
    entity_name VARCHAR(255),
    entity_type VARCHAR(50),
    similarity_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.name,
        et.name as entity_type,
        similarity(e.name, query_name) as sim_score
    FROM kg_entities e
    JOIN kg_entity_types et ON e.entity_type_id = et.id
    WHERE similarity(e.name, query_name) > similarity_threshold
    ORDER BY sim_score DESC
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Function to get entity relationships with context
CREATE OR REPLACE FUNCTION kg_get_entity_relationships(
    entity_id_param UUID,
    max_depth INTEGER DEFAULT 2,
    max_results INTEGER DEFAULT 50
)
RETURNS TABLE (
    source_entity_name VARCHAR(255),
    relationship_type VARCHAR(100),
    target_entity_name VARCHAR(255),
    confidence_score FLOAT,
    context TEXT,
    relationship_depth INTEGER
) AS $$
WITH RECURSIVE entity_graph AS (
    -- Base case: direct relationships
    SELECT
        se.name as source_name,
        rt.name as rel_type,
        te.name as target_name,
        r.confidence_score,
        r.context,
        1 as depth,
        r.target_entity_id as next_entity_id
    FROM kg_relationships r
    JOIN kg_entities se ON r.source_entity_id = se.id
    JOIN kg_entities te ON r.target_entity_id = te.id
    JOIN kg_relationship_types rt ON r.relationship_type_id = rt.id
    WHERE r.source_entity_id = entity_id_param

    UNION ALL

    -- Recursive case: follow relationships
    SELECT
        se.name as source_name,
        rt.name as rel_type,
        te.name as target_name,
        r.confidence_score,
        r.context,
        eg.depth + 1,
        r.target_entity_id as next_entity_id
    FROM entity_graph eg
    JOIN kg_relationships r ON eg.next_entity_id = r.source_entity_id
    JOIN kg_entities se ON r.source_entity_id = se.id
    JOIN kg_entities te ON r.target_entity_id = te.id
    JOIN kg_relationship_types rt ON r.relationship_type_id = rt.id
    WHERE eg.depth < max_depth
)
SELECT
    source_name,
    rel_type,
    target_name,
    confidence_score,
    context,
    depth
FROM entity_graph
ORDER BY depth, confidence_score DESC
LIMIT max_results;
$$ LANGUAGE sql;

-- Function to get entity timeline
CREATE OR REPLACE FUNCTION kg_get_entity_timeline(
    entity_id_param UUID,
    start_date TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    end_date TIMESTAMP WITH TIME ZONE DEFAULT NULL
)
RETURNS TABLE (
    fact_date TIMESTAMP WITH TIME ZONE,
    fact_type VARCHAR(100),
    fact_text TEXT,
    confidence_score FLOAT,
    document_id UUID
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ef.fact_date,
        ef.fact_type,
        ef.fact_text,
        ef.confidence_score,
        ef.document_id
    FROM kg_entity_facts ef
    WHERE ef.entity_id = entity_id_param
        AND (start_date IS NULL OR ef.fact_date >= start_date)
        AND (end_date IS NULL OR ef.fact_date <= end_date)
    ORDER BY ef.fact_date DESC NULLS LAST, ef.confidence_score DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to search entities by embedding similarity
CREATE OR REPLACE FUNCTION kg_search_entities_by_embedding(
    query_embedding vector(1536),
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    entity_id UUID,
    entity_name VARCHAR(255),
    entity_type VARCHAR(50),
    similarity_score FLOAT,
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.name,
        et.name as entity_type,
        1 - (e.embedding <=> query_embedding) as similarity,
        e.description
    FROM kg_entities e
    JOIN kg_entity_types et ON e.entity_type_id = et.id
    WHERE e.embedding IS NOT NULL
        AND 1 - (e.embedding <=> query_embedding) > similarity_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Update triggers for timestamps
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add update triggers
DROP TRIGGER IF EXISTS update_kg_entities_modtime ON kg_entities;
CREATE TRIGGER update_kg_entities_modtime
    BEFORE UPDATE ON kg_entities
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS update_kg_relationships_modtime ON kg_relationships;
CREATE TRIGGER update_kg_relationships_modtime
    BEFORE UPDATE ON kg_relationships
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

-- Row Level Security (RLS) - Enable for multi-tenant support if needed
-- ALTER TABLE kg_entities ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE kg_relationships ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE kg_entity_mentions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE kg_entity_facts ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE kg_entities IS 'Knowledge graph entities extracted from documents';
COMMENT ON TABLE kg_relationships IS 'Relationships between entities in the knowledge graph';
COMMENT ON TABLE kg_entity_mentions IS 'References to entities found in documents';
COMMENT ON TABLE kg_entity_facts IS 'Temporal facts about entities for timeline analysis';