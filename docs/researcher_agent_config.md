# Researcher Agent Configuration

The Researcher Agent is an advanced PydanticAI agent that provides comprehensive research capabilities including RAG, web search, image analysis, code execution, and knowledge graph integration.

## Environment Variables

### Core Configuration

```bash
# LLM Configuration (shared with other agents)
LLM_CHOICE=gpt-4o-mini
LLM_API_KEY=your_openai_api_key_here
VISION_LLM_CHOICE=gpt-4o-mini

# Embedding Configuration
EMBEDDING_MODEL_CHOICE=text-embedding-3-small
OPENAI_API_KEY=your_openai_api_key_here

# Supabase Configuration (for RAG and knowledge graph)
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_service_key
```

### Web Search Configuration

```bash
# Brave API (recommended for web search)
BRAVE_API_KEY=your_brave_api_key_here

# OR SearXNG (alternative search engine)
SEARXNG_BASE_URL=http://localhost:8080
```

### Knowledge Graph Configuration (Optional)

```bash
# Neo4j Database for knowledge graph features
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Or use Graphiti with compatible database
GRAPHITI_DATABASE_URL=postgresql://user:pass@host:port/db
```

## Features Configuration

The Researcher Agent can be configured per request to enable/disable specific features:

### Request Context Options

```json
{
  "agent_type": "researcher",
  "prompt": "Your research query here",
  "context": {
    "project_id": "optional-project-id",
    "source_filter": "docs.example.com",
    "match_count": 5,
    "enable_web_search": true,
    "enable_image_analysis": true,
    "enable_code_execution": true,
    "enable_knowledge_graph": true,
    "user_memories": "Previous context about user preferences"
  }
}
```

### Context Parameters

- **project_id**: Filter results to specific project
- **source_filter**: Limit search to specific domains/sources
- **match_count**: Number of RAG results to retrieve (default: 5)
- **enable_web_search**: Allow web search when local knowledge insufficient
- **enable_image_analysis**: Enable vision-based image analysis
- **enable_code_execution**: Allow safe Python code execution
- **enable_knowledge_graph**: Use entity relationships and temporal analysis
- **user_memories**: Previous context for personalized responses

## Database Setup

### Required Database Migrations

Run these SQL scripts to set up the knowledge graph and memory features:

```bash
# From the Archon root directory
psql -d your_database < migration/researcher_agent/01_knowledge_graph_setup.sql
psql -d your_database < migration/researcher_agent/02_researcher_memory_integration.sql
```

### Vector Dimensions

Ensure your embedding dimensions match your model:
- OpenAI text-embedding-3-small: 1536 dimensions
- OpenAI text-embedding-ada-002: 1536 dimensions
- Ollama nomic-embed-text: 768 dimensions

Update the SQL scripts if using different embedding models.

## Tool Capabilities

### Document Retrieval & RAG
- Semantic search through knowledge base
- Hybrid search with knowledge graph enhancement
- Document listing and full content retrieval
- Source filtering and relevance scoring

### Web Search
- Real-time web search via Brave API or SearXNG
- Integrated with local knowledge for completeness
- Automatic fallback when local knowledge insufficient

### Image Analysis
- Vision model analysis of images in knowledge base
- Context-aware image understanding
- Support for various image formats

### Code Execution
- Safe Python code execution using RestrictedPython
- Sandboxed environment with limited scope
- Access to math, json, datetime libraries
- Output capture and error handling

### Knowledge Graph
- Entity extraction and relationship mapping
- Temporal analysis and entity timelines
- Graph traversal for complex queries
- Relationship depth analysis

### Memory Integration
- User preference tracking
- Research context persistence
- Personalized response generation
- Memory categorization and importance scoring

## Security Considerations

### Code Execution Safety
- Uses RestrictedPython for sandboxed execution
- Limited library access (math, json, datetime only)
- No file system or network access from code
- Output capture prevents system access

### SQL Query Safety
- Read-only SQL execution only
- Query validation against dangerous operations
- Parameterized query support
- Database connection isolation

### Knowledge Graph Security
- Optional feature - can be disabled entirely
- Local Neo4j instance recommended for sensitive data
- Graph data isolation per project/user

## Performance Optimization

### RAG Performance
- Vector index optimization with ivfflat
- Similarity threshold tuning
- Result count balancing (5-10 recommended)
- Source filtering for focused search

### Memory Performance
- Automatic memory importance scoring
- Expired memory cleanup
- Access pattern optimization
- Embedding-based memory retrieval

### Knowledge Graph Performance
- Relationship depth limiting (2-3 levels max)
- Entity similarity caching
- Graph query optimization
- Selective feature enabling

## Troubleshooting

### Common Issues

1. **Vector dimension mismatch**
   - Check embedding model vs database schema
   - Update SQL scripts for different models

2. **Knowledge graph not available**
   - Verify Neo4j connection
   - Check if feature is enabled in context
   - Graceful fallback to vector-only search

3. **Web search failing**
   - Verify API keys (Brave or SearXNG URL)
   - Check network connectivity
   - Review rate limiting

4. **Code execution errors**
   - RestrictedPython compilation issues
   - Library access restrictions
   - Output capture problems

5. **Memory retrieval issues**
   - Embedding generation failures
   - Memory expiration cleanup
   - User context missing

### Debug Mode

Enable debug logging:

```bash
LOG_LEVEL=DEBUG
```

This provides detailed information about:
- Tool execution steps
- RAG query performance
- Knowledge graph operations
- Memory retrieval decisions
- Web search results

## Integration Examples

### Basic Research Query
```python
import httpx

async def research_query():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8052/agents/run",
            json={
                "agent_type": "researcher",
                "prompt": "What are the latest developments in AI safety?",
                "context": {
                    "enable_web_search": True,
                    "match_count": 5
                }
            }
        )
        return response.json()
```

### Streaming Research
```python
async def stream_research():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8052/agents/researcher/stream",
            json={
                "agent_type": "researcher",
                "prompt": "Analyze the technical architecture of modern web frameworks",
                "context": {
                    "enable_code_execution": True,
                    "enable_knowledge_graph": True
                }
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    print(data)
```

## Deployment Notes

### Docker Configuration
The Researcher agent is included in the agents container. Ensure environment variables are properly passed:

```yaml
services:
  agents:
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - BRAVE_API_KEY=${BRAVE_API_KEY}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - NEO4J_URI=${NEO4J_URI}
      - NEO4J_USER=${NEO4J_USER}
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
```

### Production Recommendations
- Use connection pooling for database access
- Enable memory cleanup cron jobs
- Monitor knowledge graph query performance
- Implement rate limiting for web search
- Regular vector index maintenance