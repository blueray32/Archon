Vendor integrations
===================

This directory is for optional third‑party agent implementations that you want to run inside Archon.

Using "4_Pydantic_AI_Agent"
---------------------------
1) Copy the upstream folder into this repo:
   - Source: 4_Pydantic_AI_Agent
   - Destination: python/vendor/4_Pydantic_AI_Agent

2) Set env vars for the Agents service (Docker Compose or local env):
   - PYDANTIC_AI_AGENT_CLASS=python.vendor.dynamous_agent.archon_adapter:DynamousPydanticAIAgentAdapter
   - DYNAMOUS_AGENT_FACTORY=python.vendor.4_Pydantic_AI_Agent.agent:create_agent

3) Configure LLM and embeddings for the vendor agent (examples):
   - LLM_PROVIDER=openai
   - LLM_BASE_URL=https://api.openai.com/v1
   - LLM_API_KEY=...
   - LLM_CHOICE=gpt-4o-mini
   - EMBEDDING_PROVIDER=openai
   - EMBEDDING_BASE_URL=https://api.openai.com/v1
   - EMBEDDING_API_KEY=...
   - EMBEDDING_MODEL_CHOICE=text-embedding-3-small

   Optional (if used by vendor agent):
   - SUPABASE_URL, SUPABASE_SERVICE_KEY
   - BRAVE_API_KEY or SEARXNG_BASE_URL

4) Restart the Agents service (Docker Compose profile "agents") and verify:
   - curl http://localhost:3737/api/agent-chat/status → online: true
   - In the UI, select "Pydantic AI" and chat.

Fallback behavior
-----------------
If the vendor cannot be loaded, Archon automatically falls back to the built‑in PydanticAI PRP agent. The chat server will still route pydantic_ai → rag if the agents service doesn’t expose pydantic_ai.

