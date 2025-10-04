# PRP System Setup Guide

Complete guide for setting up and using Archon's PRP (Product Requirement Prompt) system.

## Prerequisites

- Archon installed and running
- PostgreSQL/Supabase database configured
- OpenAI API key (for embeddings and chat)
- Python 3.12+ with uv package manager

## Quick Start (5 minutes)

```bash
# 1. Apply database migration
# Copy the contents of migration/prp_system.sql
# Paste into your Supabase SQL Editor and execute

# 2. Run embedding sync to index PRPs
cd python
uv run python -m src.scripts.prp_embed_sync

# 3. Restart agents service
docker compose restart archon-agents

# 4. Test the PRP agent
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is Archon?",
    "context": {"session_id": "test-123"}
  }'
```

## Detailed Setup

### Step 1: Database Setup

#### Option A: Using Supabase Dashboard
1. Go to your Supabase project SQL Editor
2. Open `migration/prp_system.sql`
3. Copy and paste the entire contents
4. Click "Run" to execute the migration

#### Option B: Using psql
```bash
psql $SUPABASE_URL -f migration/prp_system.sql
```

This creates:
- `prp_messages` - Chat history with embeddings
- `prp_docs` - PRP documents with embeddings
- `prp_personas` - Agent persona configurations
- Helper functions for vector similarity search
- Default "chat_gpt_like" persona

Verify tables were created:
```sql
SELECT tablename FROM pg_tables
WHERE tablename LIKE 'prp_%';
```

### Step 2: Configure Environment

Ensure these environment variables are set in your `.env`:

```bash
# Required
OPENAI_API_KEY=sk-...                    # For embeddings and chat
SUPABASE_URL=https://....supabase.co     # Your Supabase URL
SUPABASE_SERVICE_KEY=eyJ...              # Service role key

# Optional (with defaults)
PRP_ENABLED=true                         # Enable PRP system
PRP_RAG_TOP_K=6                         # Context items to retrieve
PRP_MAX_CONTEXT_CHARS=60000             # Max context length
PRP_DEFAULT_PERSONA=chat_gpt_like       # Default persona
PRP_EMBEDDING_MODEL=text-embedding-3-small
PRP_CHAT_MODEL=gpt-4o-mini
PRP_STREAM_ENABLED=true
```

### Step 3: Index PRPs and Documentation

The embedding sync script indexes:
- `PRPs/**/*.prp.md` - Product requirement prompts
- `docs/**/*.md` - Documentation files
- `personas/**/*.yaml` - Persona configurations

Run the indexing:
```bash
cd python
uv run python -m src.scripts.prp_embed_sync
```

Expected output:
```
INFO - Starting PRP embedding sync...
INFO - Indexing PRP files...
INFO - ✓ Indexed prp: PRPs/00_archon_prp_system.prp.md
INFO - Indexing documentation files...
INFO - ✓ Indexed doc: docs/architecture.mdx
INFO - Indexing persona files...
INFO - ✓ Indexed persona: personas/chat_gpt_like.yaml
INFO - ============================================================
INFO - Embedding sync complete!
INFO -   PRPs indexed: 1
INFO -   Docs indexed: 15
INFO -   Personas indexed: 1
INFO -   Total: 17
INFO - ============================================================
```

Verify embeddings in database:
```sql
SELECT kind, COUNT(*) as count
FROM prp_docs
WHERE embedding IS NOT NULL
GROUP BY kind;
```

### Step 4: Restart Services

Restart the agents service to pick up the new agent:
```bash
# Using Docker Compose
docker compose restart archon-agents

# Or restart all services
docker compose restart
```

Check agent availability:
```bash
curl http://localhost:8052/health
```

Should include `"prp"` in `agents_available` list.

### Step 5: Test Integration

#### Test 1: Basic Chat
```bash
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is the PRP system?",
    "context": {
      "session_id": "test-session-1"
    }
  }' | jq .
```

Expected response:
```json
{
  "success": true,
  "result": {
    "output": "The PRP system is...",
    "sources": [...]
  }
}
```

#### Test 2: With Persona
```bash
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "How do I add a new PRP?",
    "context": {
      "session_id": "test-session-2",
      "persona_name": "chat_gpt_like"
    }
  }' | jq .
```

#### Test 3: Conversation Continuity
```bash
# First message
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "Tell me about Archon",
    "context": {"session_id": "continuity-test"}
  }' | jq .

# Follow-up (should remember context)
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What features does it have?",
    "context": {"session_id": "continuity-test"}
  }' | jq .
```

## Usage

### Adding New PRPs

1. **Create PRP file:**
   ```bash
   touch PRPs/01_my_feature.prp.md
   ```

2. **Write your PRP** following the template in `PRPs/README.md`

3. **Index the new PRP:**
   ```bash
   cd python
   uv run python -m src.scripts.prp_embed_sync
   ```

4. **Test it:**
   ```bash
   curl -X POST http://localhost:8052/agents/run \
     -H "Content-Type: application/json" \
     -d '{
       "agent_type": "prp",
       "prompt": "Tell me about [your feature]",
       "context": {"session_id": "test"}
     }'
   ```

### Creating Custom Personas

1. **Create persona YAML:**
   ```bash
   cat > personas/technical_architect.yaml << 'EOF'
   name: "Technical Architect"
   goals:
     - Provide detailed technical guidance
     - Focus on architecture and design patterns
   style:
     tone: professional, detailed
   prompt_blocks:
     - role: system
       content: |
         You are a senior technical architect specializing in...
   EOF
   ```

2. **Index persona:**
   ```bash
   cd python
   uv run python -m src.scripts.prp_embed_sync
   ```

3. **Add to database:**
   ```sql
   INSERT INTO prp_personas (name, display_name, system_prompt, configuration)
   VALUES (
     'technical_architect',
     'Technical Architect',
     'You are a senior technical architect...',
     '{"tone": "professional", "style": "detailed"}'::jsonb
   );
   ```

4. **Use it:**
   ```bash
   curl -X POST http://localhost:8052/agents/run \
     -H "Content-Type: application/json" \
     -d '{
       "agent_type": "prp",
       "prompt": "Design a microservices architecture",
       "context": {"persona_name": "technical_architect"}
     }'
   ```

### Updating Existing PRPs

1. Edit the PRP file
2. Re-run embedding sync
3. Test the changes

The system automatically replaces old embeddings (upsert on `kind,path`).

## Troubleshooting

### Problem: No PRPs retrieved in responses

**Check if PRPs are indexed:**
```sql
SELECT COUNT(*) FROM prp_docs WHERE kind = 'prp';
```

If count is 0:
- Verify PRP files end with `.prp.md`
- Check embedding sync logs for errors
- Ensure `OPENAI_API_KEY` is set

**Check embeddings:**
```sql
SELECT path,
       CASE WHEN embedding IS NULL THEN 'missing' ELSE 'present' END as embedding_status
FROM prp_docs
WHERE kind = 'prp';
```

### Problem: Agent not available

**Check health:**
```bash
curl http://localhost:8052/health
```

If `prp` not in `agents_available`:
- Check agents service logs: `docker compose logs archon-agents`
- Verify imports in `python/src/agents/server.py`
- Restart agents service

### Problem: Poor context quality

**Increase retrieval count:**
```bash
# Set environment variable
echo "PRP_RAG_TOP_K=10" >> .env

# Or in request
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "Your question",
    "context": {"top_k": 10}
  }'
```

**Improve PRP structure:**
- Use clear headings and sections
- Include concrete examples
- Keep content focused and relevant
- Use semantic file names

### Problem: Conversation doesn't remember context

**Verify message storage:**
```sql
SELECT COUNT(*) FROM prp_messages WHERE session_id = 'your-session-id';
```

If count is 0:
- Messages aren't being stored
- Check PRPService implementation
- Verify database permissions

**Check session ID:**
- Ensure consistent `session_id` across requests
- Session IDs are case-sensitive

### Problem: Embeddings failing

**Check OpenAI API key:**
```bash
echo $OPENAI_API_KEY
```

**Test OpenAI connection:**
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**Check rate limits:**
- OpenAI has rate limits for embeddings
- Script includes retry logic
- Check logs for rate limit errors

## Advanced Configuration

### Custom Embedding Model

To use a different embedding model:

1. Update settings:
   ```sql
   UPDATE archon_settings
   SET value = 'text-embedding-3-large'
   WHERE key = 'PRP_EMBEDDING_MODEL';
   ```

2. Update vector dimensions in migration:
   ```sql
   -- text-embedding-3-small = 1536 dimensions
   -- text-embedding-3-large = 3072 dimensions
   ALTER TABLE prp_messages ALTER COLUMN embedding TYPE VECTOR(3072);
   ALTER TABLE prp_docs ALTER COLUMN embedding TYPE VECTOR(3072);
   ```

3. Re-index all documents

### Database Performance

For large deployments with many PRPs:

1. **Increase HNSW index parameters** (better accuracy, slower build):
   ```sql
   DROP INDEX idx_prp_docs_embedding;
   CREATE INDEX idx_prp_docs_embedding ON prp_docs
     USING hnsw (embedding vector_cosine_ops)
     WITH (m = 32, ef_construction = 128);
   ```

2. **Add covering indexes** for common queries:
   ```sql
   CREATE INDEX idx_prp_messages_session_created
   ON prp_messages(session_id, created_at DESC);
   ```

3. **Partition by date** for very high message volume:
   ```sql
   -- Create partitions by month
   CREATE TABLE prp_messages_2024_01 PARTITION OF prp_messages
     FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
   ```

## Monitoring

### Query Performance
```sql
-- Slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE query LIKE '%prp_%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### Storage Usage
```sql
-- Table sizes
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename LIKE 'prp_%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Message Volume
```sql
-- Messages per day
SELECT
  DATE(created_at) as date,
  COUNT(*) as messages,
  COUNT(DISTINCT session_id) as sessions
FROM prp_messages
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 30;
```

## Next Steps

1. **Integrate with UI**: Add PRP agent option to agent chat interface
2. **Create more PRPs**: Document your features and architecture
3. **Custom personas**: Create personas for different use cases
4. **Monitor usage**: Track which PRPs are most retrieved
5. **Optimize**: Tune retrieval parameters based on user feedback

## Resources

- **PRP Documentation**: `PRPs/README.md`
- **Example PRP**: `PRPs/00_archon_prp_system.prp.md`
- **Agent Code**: `python/src/agents/prp_agent.py`
- **Service Code**: `python/src/server/services/prp_service.py`
- **Migration**: `migration/prp_system.sql`