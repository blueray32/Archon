# Product Requirement Prompts (PRPs)

This directory contains Product Requirement Prompts (PRPs) that drive Archon's AI agent behavior.

## What are PRPs?

PRPs are structured markdown documents that define:
- Product features and requirements
- System behaviors and constraints
- Technical architecture and patterns
- Best practices and guidelines

When you chat with Archon's PRP-driven agents, these documents are automatically retrieved and used as context, ensuring agents provide informed, consistent responses aligned with your product requirements.

## Structure

Each PRP file follows this naming convention:
```
NN_feature_name.prp.md
```

Where:
- `NN` - Two-digit number for ordering (00, 01, 02...)
- `feature_name` - Descriptive name using underscores
- `.prp.md` - Extension indicating this is a PRP markdown file

## PRP Format

A typical PRP includes:

```markdown
# PRP — Feature Name

**Owner:** Team/Person
**Primary LLM:** Model used (e.g., GPT-4o-mini)
**Surfaces:** Where this applies (Web UI, API, CLI)
**Goal:** One-sentence goal

## Problem & Intent
Description of what problem this solves and why.

## Outcomes (Success Criteria)
1. Measurable outcome 1
2. Measurable outcome 2
3. ...

## Technical Architecture
How this is implemented.

## Usage Patterns
Examples of how to use this feature.

## Best Practices
Guidelines for effective use.

## Troubleshooting
Common issues and solutions.
```

## How PRPs Work

1. **Indexing**: When you run the embedding sync script, all PRP files are:
   - Read from this directory
   - Converted to embeddings using OpenAI's text-embedding-3-small
   - Stored in the `prp_docs` table with kind='prp'

2. **Retrieval**: When you chat with a PRP agent:
   - Your message is converted to an embedding
   - Top-K most similar PRPs are retrieved via vector search
   - Retrieved PRPs are injected as context for the agent's response

3. **Context**: The agent uses PRP content to:
   - Understand system architecture
   - Follow established patterns
   - Provide accurate, context-aware responses
   - Maintain consistency across conversations

## Adding New PRPs

1. Create a new PRP file in this directory:
   ```bash
   touch PRPs/01_my_new_feature.prp.md
   ```

2. Write your PRP following the format above

3. Run the embedding sync script:
   ```bash
   cd python
   uv run python -m src.scripts.prp_embed_sync
   ```

4. Your PRP is now available as context for all agent interactions!

## Updating Existing PRPs

1. Edit the PRP file
2. Re-run the embedding sync script
3. The old embedding is automatically replaced (upsert on kind+path)

## Current PRPs

- `00_archon_prp_system.prp.md` - This PRP system itself

Add more PRPs as you build features!

## Best Practices

### DO:
- ✅ Keep PRPs focused on one feature/domain
- ✅ Use clear, concise language
- ✅ Include concrete examples and usage patterns
- ✅ Update PRPs when features change
- ✅ Use semantic file names

### DON'T:
- ❌ Create massive PRPs covering multiple features
- ❌ Include sensitive information (API keys, passwords)
- ❌ Duplicate information across multiple PRPs
- ❌ Leave PRPs stale when features evolve

## Configuration

PRP system settings (in `archon_settings` table):

- `PRP_ENABLED` - Enable/disable PRP system
- `PRP_RAG_TOP_K` - Number of PRPs to retrieve (default: 6)
- `PRP_MAX_CONTEXT_CHARS` - Max context length (default: 60000)
- `PRP_EMBEDDING_MODEL` - Embedding model (default: text-embedding-3-small)

## Database Tables

PRPs are stored in these tables:

- `prp_docs` - Indexed PRP documents with embeddings
- `prp_messages` - Chat history with embeddings
- `prp_personas` - Agent persona configurations

## Querying PRPs

You can query PRPs directly from PostgreSQL:

```sql
-- List all PRPs
SELECT id, path, title, created_at FROM prp_docs WHERE kind = 'prp';

-- Search PRPs by text (requires embedding)
SELECT * FROM search_prp_docs(
  (SELECT embedding FROM prp_docs WHERE path = 'reference.prp.md'),
  'prp',
  5
);
```

## Examples

### Example 1: Feature PRP
```markdown
# PRP — User Authentication

**Owner:** Security Team
**Primary LLM:** GPT-4o-mini
**Goal:** Implement secure JWT-based authentication

## Problem & Intent
Users need a secure way to authenticate and maintain sessions.

## Outcomes
1. JWT tokens with 1-hour expiry
2. Refresh token support
3. OAuth2 integration with Google/GitHub
...
```

### Example 2: Pattern PRP
```markdown
# PRP — API Error Handling Pattern

**Owner:** Backend Team
**Goal:** Standardize error responses across all APIs

## Problem & Intent
Inconsistent error responses make debugging difficult.

## Outcomes
1. All errors return { error: string, type: string, details?: object }
2. HTTP status codes follow REST conventions
3. Error types are documented
...
```

## Troubleshooting

**PRPs not appearing in context:**
- Check if file ends with `.prp.md`
- Verify embedding sync completed successfully
- Check `prp_docs` table: `SELECT * FROM prp_docs WHERE kind='prp'`

**Embeddings not created:**
- Ensure `OPENAI_API_KEY` is set in environment
- Check embedding sync logs for errors
- Verify file is valid UTF-8 encoded

**Old content still appearing:**
- Re-run embedding sync after editing
- Check `updated_at` timestamp in `prp_docs` table

## Resources

- **Embedding Sync Script**: `python/src/scripts/prp_embed_sync.py`
- **PRP Agent**: `python/src/agents/prp_agent.py`
- **PRP Service**: `python/src/server/services/prp_service.py`
- **Database Migration**: `migration/prp_system.sql`