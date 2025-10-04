# PRP — Archon PRP-Driven Agent System

**Owner:** Development Team
**Primary LLM:** OpenAI (GPT-4o-mini for chat; text-embedding-3-small for memory)
**Surfaces:** Web UI, REST API, Agents Service
**Goal:** Integrate PRP-driven conversational agents into Archon with persistent memory, RAG retrieval, and ChatGPT-like user experience.

## Problem & Intent

Archon needs a way to create conversational AI agents that:
1. Are driven by Product Requirement Prompts (PRPs) for structured context
2. Remember conversation history across sessions
3. Retrieve relevant context using RAG (Retrieval-Augmented Generation)
4. Provide a ChatGPT-like conversational experience
5. Support multiple personas for different use cases

## Outcomes (Success Criteria)

1. **PRP Binding**: Any `*.prp.md` file in `PRPs/` directory is indexed with embeddings and retrieved as context for agent responses.
2. **Persistent Memory**: All chat messages are stored with embeddings in `prp_messages` table for context retrieval.
3. **RAG Retrieval**: Top-K similarity search over PRPs and conversation history provides relevant context.
4. **Persona System**: Multiple agent personas defined in `prp_personas` table with customizable system prompts.
5. **ChatGPT-like UX**: Conversational, friendly, clear responses with numbered steps and actionable advice.
6. **Multi-surface**: Same agent behavior accessible via:
   - Agents Service REST API (`/agents/run`)
   - Main Server agent chat API (`/api/agent-chat`)
   - Future: Web UI integration

## Technical Architecture

### Database Schema

**Tables:**
- `prp_messages` - Chat messages with embeddings (1536-dim vectors)
- `prp_docs` - PRP documents and documentation with embeddings
- `prp_personas` - Agent persona configurations

**Functions:**
- `search_prp_messages(embedding, session_id, k)` - Vector similarity search for messages
- `search_prp_docs(embedding, kind, k)` - Vector similarity search for documents

### Components

1. **PRPAgent** (`python/src/agents/prp_agent.py`)
   - PydanticAI-based agent with RAG context retrieval
   - Supports streaming responses
   - Rate limiting and retry logic via BaseAgent

2. **PRPService** (`python/src/server/services/prp_service.py`)
   - RAG context retrieval combining PRPs + conversation history
   - Embedding generation via OpenAI
   - Message storage and persona management

3. **Embedding Sync Script** (`python/src/scripts/prp_embed_sync.py`)
   - Indexes PRP files (`PRPs/**/*.prp.md`)
   - Indexes documentation (`docs/**/*.md`)
   - Indexes personas (`personas/**/*.yaml`)
   - Run after adding/updating PRP files

### Usage Patterns

**From Agents Service:**
```bash
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is Archon and how do I use PRPs?",
    "context": {
      "session_id": "user-123",
      "persona_name": "chat_gpt_like"
    }
  }'
```

**From Python:**
```python
from agents.prp_agent import run_prp_agent

result = await run_prp_agent(
    prompt="How do I add a new PRP?",
    session_id="user-456",
    persona_name="chat_gpt_like",
    rag_retriever=prp_service.retrieve_context
)
print(result.output)
```

## Personas

### Default: ChatGPT-Like (`chat_gpt_like`)
- Warm, practical, down-to-earth tone
- Clear, actionable explanations
- Numbered steps for procedures
- Maintains continuity via memory recall
- Minimal fluff, scoped to the ask

### Creating New Personas

Add to `prp_personas` table:
```sql
INSERT INTO prp_personas (name, display_name, system_prompt, configuration)
VALUES (
  'technical_architect',
  'Technical Architect',
  'You are a senior technical architect...',
  '{"tone": "professional", "style": "detailed"}'::jsonb
);
```

## Maintenance

### Adding New PRPs
1. Create `PRPs/my_feature.prp.md` with structured content
2. Run embedding sync: `uv run python -m src.scripts.prp_embed_sync`
3. PRPs are now available as context for all agent interactions

### Updating Existing PRPs
1. Edit the PRP file
2. Re-run embedding sync to update embeddings
3. Old embedding is replaced (upsert on `kind,path`)

### Monitoring
- Check `prp_messages` table for conversation history
- Check `prp_docs` table for indexed PRPs
- Use Logfire for agent performance monitoring

## Settings

Configure via `archon_settings` table or environment variables:

- `PRP_ENABLED` - Enable/disable PRP system (default: true)
- `PRP_RAG_TOP_K` - Number of context items to retrieve (default: 6)
- `PRP_MAX_CONTEXT_CHARS` - Max context length (default: 60000)
- `PRP_DEFAULT_PERSONA` - Default persona name (default: chat_gpt_like)
- `PRP_EMBEDDING_MODEL` - OpenAI embedding model (default: text-embedding-3-small)
- `PRP_CHAT_MODEL` - Chat model for agent (default: gpt-4o-mini)
- `PRP_STREAM_ENABLED` - Enable streaming responses (default: true)

## Best Practices

1. **Keep PRPs Focused**: Each PRP should cover one feature or requirement
2. **Use Clear Structure**: Include Problem, Outcomes, Architecture sections
3. **Update PRPs**: When features change, update the PRP and re-embed
4. **Semantic File Names**: Use descriptive names like `feature_authentication.prp.md`
5. **Session Management**: Use consistent session IDs for conversation continuity
6. **Context Limits**: Keep PRPs under 10k characters for optimal retrieval

## Troubleshooting

**No context retrieved:**
- Check if embeddings were created: `SELECT COUNT(*) FROM prp_docs WHERE embedding IS NOT NULL`
- Verify OpenAI API key is set
- Re-run embedding sync script

**Agent not available:**
- Check agents service health: `curl http://localhost:8052/health`
- Verify "prp" is in `agents_available` list
- Check logs: `docker compose logs archon-agents`

**Poor context quality:**
- Increase `PRP_RAG_TOP_K` for more context
- Improve PRP structure and clarity
- Use more specific queries