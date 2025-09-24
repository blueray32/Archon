"""
Agents Service - Lightweight FastAPI server for PydanticAI agents

This service ONLY hosts PydanticAI agents. It does NOT contain:
- ML models or embeddings (those are in Server)
- Direct database access (use MCP tools)
- Business logic (that's in Server)

The agents use MCP tools for all data operations.
"""

import asyncio
import json
import re
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import our PydanticAI agents
from .document_agent import DocumentAgent
from .rag_agent import RagAgent
from .pydantic_ai_loader import get_pydantic_ai_agent_class
from .spanish_tutor_agent import SpanishTutorAgent
from .researcher_agent import ResearcherAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Request/Response models
class AgentRequest(BaseModel):
    """Request model for agent interactions"""

    agent_type: str  # "document", "rag", etc.
    prompt: str
    context: dict[str, Any] | None = None
    options: dict[str, Any] | None = None


class AgentResponse(BaseModel):
    """Response model for agent interactions"""

    success: bool
    result: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


# Agent registry
AVAILABLE_AGENTS = {
    "document": DocumentAgent,
    "rag": RagAgent,
    "spanish_tutor": SpanishTutorAgent,
    "researcher": ResearcherAgent,
    "pydantic_ai": get_pydantic_ai_agent_class(),
}

# Global credentials storage
AGENT_CREDENTIALS = {}


async def fetch_credentials_from_server():
    """Fetch credentials from the server's internal API."""
    max_retries = 30  # Try for up to 5 minutes (30 * 10 seconds)
    retry_delay = 10  # seconds

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                # Call the server's internal credentials endpoint
                server_port = os.getenv("ARCHON_SERVER_PORT")
                if not server_port:
                    raise ValueError(
                        "ARCHON_SERVER_PORT environment variable is required. "
                        "Please set it in your .env file or environment."
                    )
                response = await client.get(
                    f"http://archon-server:{server_port}/internal/credentials/agents", timeout=10.0
                )
                response.raise_for_status()
                credentials = response.json()

                # Set credentials as environment variables
                for key, value in credentials.items():
                    if value is not None:
                        os.environ[key] = str(value)
                        logger.info(f"Set credential: {key}")

                # Store credentials globally for agent initialization
                global AGENT_CREDENTIALS
                AGENT_CREDENTIALS = credentials

                logger.info(f"Successfully fetched {len(credentials)} credentials from server")
                return credentials

        except (httpx.HTTPError, httpx.RequestError) as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Failed to fetch credentials (attempt {attempt + 1}/{max_retries}): {e}"
                )
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to fetch credentials after {max_retries} attempts")
                raise Exception("Could not fetch credentials from server")


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    logger.info("Starting Agents service...")

    # Fetch credentials from server first
    try:
        await fetch_credentials_from_server()
    except Exception as e:
        logger.error(f"Failed to fetch credentials: {e}")
        # Continue with defaults if we can't get credentials

    # Initialize agents with fetched credentials
    app.state.agents = {}
    for name, agent_class in AVAILABLE_AGENTS.items():
        try:
            logger.info(f"Attempting to initialize {name} agent...")
            # Pass model configuration from credentials
            model_key = f"{name.upper()}_AGENT_MODEL"
            model = AGENT_CREDENTIALS.get(model_key, "openai:gpt-4o-mini")

            # Override Spanish tutor to use gpt-4o-mini to avoid quota issues
            if name == "spanish_tutor" and model == "openai:gpt-4o":
                model = "openai:gpt-4o-mini"
                logger.info(f"Overriding Spanish tutor to use gpt-4o-mini due to quota limits")

            logger.info(f"Using model: {model} for {name} agent")

            # agent_class may be a class, a factory function, or an instance
            if isinstance(agent_class, type):
                agent_instance = agent_class(model=model)
            elif callable(agent_class):
                try:
                    agent_instance = agent_class(model=model)
                except TypeError:
                    agent_instance = agent_class()
            else:
                agent_instance = agent_class
            app.state.agents[name] = agent_instance
            logger.info(f"Successfully initialized {name} agent with model: {model}")
        except Exception as e:
            import traceback
            logger.error(f"Failed to initialize {name} agent: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")

    yield

    # Cleanup
    logger.info("Shutting down Agents service...")


# Create FastAPI app
app = FastAPI(
    title="Archon Agents Service",
    description="Lightweight service hosting PydanticAI agents",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "agents",
        "agents_available": list(AVAILABLE_AGENTS.keys()),
        "note": "This service only hosts PydanticAI agents",
    }


@app.post("/agents/run", response_model=AgentResponse)
async def run_agent(request: AgentRequest):
    """
    Run a specific agent with the given prompt.

    The agent will use MCP tools for any data operations.
    """
    try:
        # Get the requested agent
        if request.agent_type not in app.state.agents:
            raise HTTPException(status_code=400, detail=f"Unknown agent type: {request.agent_type}")

        agent = app.state.agents[request.agent_type]

        # Prepare dependencies based on agent type
        if request.agent_type in ("rag", "pydantic_ai"):
            from .rag_agent import RagDependencies

            deps = RagDependencies(
                source_filter=request.context.get("source_filter") if request.context else None,
                match_count=request.context.get("match_count", 5) if request.context else 5,
                project_id=request.context.get("project_id") if request.context else None,
                prp_mode=(request.agent_type == "pydantic_ai"),
            )
        elif request.agent_type == "document":
            from .document_agent import DocumentDependencies

            deps = DocumentDependencies(
                project_id=request.context.get("project_id") if request.context else None,
                user_id=request.context.get("user_id") if request.context else None,
            )
        elif request.agent_type == "spanish_tutor":
            from .spanish_tutor_agent import SpanishTutorDependencies

            deps = SpanishTutorDependencies(
                student_level=request.context.get("student_level", "beginner") if request.context else "beginner",
                conversation_mode=request.context.get("conversation_mode", "casual") if request.context else "casual",
                focus_area=request.context.get("focus_area") if request.context else None,
                previous_context=request.context.get("previous_context") if request.context else None,
                response_style=request.context.get("response_style", "minimal") if request.context else "minimal",
                include_translation=bool(request.context.get("include_translation", False)) if request.context else False,
                include_corrections=bool(request.context.get("include_corrections", True)) if request.context else True,
                include_grammar_notes=bool(request.context.get("include_grammar_notes", False)) if request.context else False,
                include_vocabulary=bool(request.context.get("include_vocabulary", False)) if request.context else False,
                include_cultural_notes=bool(request.context.get("include_cultural_notes", False)) if request.context else False,
                include_encouragement=bool(request.context.get("include_encouragement", True)) if request.context else True,
                include_next_topic=bool(request.context.get("include_next_topic", False)) if request.context else False,
                max_reply_sentences=int(request.context.get("max_reply_sentences", 2)) if request.context else 2,
                reading_mode=bool(request.context.get("reading_mode", False)) if request.context else False,
            )
        elif request.agent_type == "researcher":
            from .researcher_agent import ResearcherDependencies

            deps = ResearcherDependencies(
                project_id=request.context.get("project_id") if request.context else None,
                source_filter=request.context.get("source_filter") if request.context else None,
                match_count=request.context.get("match_count", 5) if request.context else 5,
                enable_web_search=request.context.get("enable_web_search", True) if request.context else True,
                enable_image_analysis=request.context.get("enable_image_analysis", True) if request.context else True,
                enable_code_execution=request.context.get("enable_code_execution", True) if request.context else True,
                enable_knowledge_graph=request.context.get("enable_knowledge_graph", True) if request.context else True,
                user_memories=request.context.get("user_memories", "") if request.context else "",
                brave_api_key=os.getenv('BRAVE_API_KEY'),
                searxng_base_url=os.getenv('SEARXNG_BASE_URL'),
            )
        else:
            # Default dependencies
            from .base_agent import ArchonDependencies

            deps = ArchonDependencies()

        # Run the agent
        result = await agent.run(request.prompt, deps)

        # Normalize result into a consistent shape `{ output: string, raw: Any }`
        def to_output(res: Any) -> str:
            try:
                if isinstance(res, str):
                    return res
                if isinstance(res, dict):
                    # common keys in our agents
                    for key in ("output", "answer", "text", "message"):
                        if key in res and isinstance(res[key], str):
                            return res[key]
                    # last resort - pretty print
                    import json
                    return json.dumps(res, ensure_ascii=False)[:4000]
                # Pydantic models or other objects
                if hasattr(res, "model_dump"):
                    dumped = res.model_dump()
                    return to_output(dumped)
                return str(res)
            except Exception:
                return str(res)

        output_text = to_output(result)

        # Enforce strict reading mode for Spanish tutor (two lines: Spanish then English)
        def unwrap_agent_result_text(text: str) -> str:
            try:
                if isinstance(text, str) and text.startswith("AgentRunResult(") and "output=" in text:
                    # Capture contents of output='...'
                    m = re.search(r"output\s*=\s*'([^']*)'", text, flags=re.S)
                    if not m:
                        m = re.search(r'output\s*=\s*"([^"]*)"', text, flags=re.S)
                    if m:
                        inner = m.group(1)
                        # Light unescape for common sequences without breaking UTF‑8
                        inner = (
                            inner
                            .replace(r"\n", "\n")
                            .replace(r"\t", "\t")
                            .replace(r'\"', '"')
                            .replace(r"\'", "'")
                        )
                        return inner
                    # Fallback: strip wrapper if we can't parse cleanly
                    stripped = text[len("AgentRunResult(") :]
                    return stripped[:-1] if stripped.endswith(")") else stripped
            except Exception:
                return text
            return text

        def strip_emojis(s: str) -> str:
            try:
                # Remove common emoji ranges
                return re.sub("[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\U0001F1E6-\U0001F1FF\u2600-\u26FF\u2700-\u27BF]", "", s)
            except re.error:
                # Narrow fallback if wide unicode not supported
                return s

        def strip_bullets_markdown(s: str) -> str:
            try:
                # Remove leading bullets or numeric list markers
                s = re.sub(r"^\s*(?:[-*•]+|\d+[\.\)]\s*)\s*", "", s)
                # Remove markdown bold/italic
                s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
                s = re.sub(r"\*(.*?)\*", r"\1", s)
                # Remove bracketed phonetics or asides
                s = re.sub(r"\[[^\]]+\]", "", s)
                # Remove stray bullet symbols (keep dashes in word pairs)
                s = re.sub(r"[•▪︎◦·●]", "", s)
                # Trim repeated spaces
                s = re.sub(r"\s{2,}", " ", s)
                return s.strip()
            except re.error:
                return s

        def enforce_reading_mode(text: str) -> str:
            # Unwrap wrappers and normalize
            t = unwrap_agent_result_text(text)
            # Split and sanitize lines
            lines = [strip_bullets_markdown(strip_emojis(ln.strip())) for ln in t.splitlines() if ln.strip()]

            # Expand any inline translations "Spanish (English)" into two lines
            expanded: list[str] = []
            for ln in lines:
                m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", ln)
                if m:
                    es = m.group(1).strip().strip('"“”')
                    en = m.group(2).strip().strip('"“”')
                    if es:
                        expanded.append(es)
                    if en:
                        expanded.append(en)
                else:
                    expanded.append(ln)

            # Remove any leftover list-like starts that slipped through
            cleaned = [re.sub(r"^\s*(?:[-*•]+|\d+[\.\)]\s*)\s*", "", ln).strip() for ln in expanded if ln]

            # Join back preserving order to keep bilingual pairs authored by the agent
            return "\n".join([ln for ln in cleaned if ln])

        # Always unwrap AgentRunResult wrappers for cleaner UI
        output_text = unwrap_agent_result_text(output_text)

        if request.agent_type == "spanish_tutor" and request.context and request.context.get("reading_mode"):
            output_text = enforce_reading_mode(output_text)

        normalized = {"output": output_text, "raw": result}

        return AgentResponse(
            success=True,
            result=normalized,
            metadata={"agent_type": request.agent_type, "model": agent.model},
        )

    except Exception as e:
        logger.error(f"Error running {request.agent_type} agent: {e}")
        return AgentResponse(success=False, error=str(e))


@app.get("/agents/list")
async def list_agents():
    """List all available agents and their capabilities"""
    agents_info = {}

    for name, agent in app.state.agents.items():
        agents_info[name] = {
            "name": agent.name,
            "model": agent.model,
            "description": agent.__class__.__doc__ or "No description available",
            "available": True,
        }

    return {"agents": agents_info, "total": len(agents_info)}


def _reinit_agents(app: FastAPI):
    """Reinitialize agents using current AGENT_CREDENTIALS and registry."""
    app.state.agents = {}
    for name, agent_class in AVAILABLE_AGENTS.items():
        try:
            logger.info(f"Reinitializing {name} agent...")
            model_key = f"{name.upper()}_AGENT_MODEL"
            model = AGENT_CREDENTIALS.get(model_key, "openai:gpt-4o-mini")

            # Override Spanish tutor to use gpt-4o-mini to avoid quota issues
            if name == "spanish_tutor" and model == "openai:gpt-4o":
                model = "openai:gpt-4o-mini"
                logger.info(f"Overriding Spanish tutor to use gpt-4o-mini due to quota limits")
            if isinstance(agent_class, type):
                agent_instance = agent_class(model=model)
            elif callable(agent_class):
                try:
                    agent_instance = agent_class(model=model)
                except TypeError:
                    agent_instance = agent_class()
            else:
                agent_instance = agent_class
            app.state.agents[name] = agent_instance
            logger.info(f"Agent {name} ready with model {model}")
        except Exception as e:
            logger.error(f"Failed to initialize {name}: {e}")


@app.post("/agents/refresh-credentials")
async def refresh_credentials():
    """Refresh credentials from the main server and reinitialize agents.

    Useful after updating OPENAI_API_KEY or model choices via Settings without restart.
    """
    try:
        creds = await fetch_credentials_from_server()
        # Update global creds
        global AGENT_CREDENTIALS
        AGENT_CREDENTIALS = creds
        # Reinit agents with possibly updated models/keys
        _reinit_agents(app)
        return {"success": True, "message": "Credentials refreshed", "keys": list(creds.keys())}
    except Exception as e:
        logger.error(f"Refresh credentials failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_type}/stream")
async def stream_agent(agent_type: str, request: AgentRequest):
    """
    Stream responses from an agent using Server-Sent Events (SSE).

    This endpoint streams the agent's response in real-time, allowing
    for a more interactive experience.
    """
    # Get the requested agent
    if agent_type not in app.state.agents:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {agent_type}")

    agent = app.state.agents[agent_type]

    async def generate() -> AsyncGenerator[str, None]:
        try:
            # Prepare dependencies based on agent type
            # Import dependency classes
            if agent_type in ("rag", "pydantic_ai"):
                from .rag_agent import RagDependencies

                deps = RagDependencies(
                    source_filter=request.context.get("source_filter") if request.context else None,
                    match_count=request.context.get("match_count", 5) if request.context else 5,
                    project_id=request.context.get("project_id") if request.context else None,
                    prp_mode=(agent_type == "pydantic_ai"),
                )
            elif agent_type == "document":
                from .document_agent import DocumentDependencies

                deps = DocumentDependencies(
                    project_id=request.context.get("project_id") if request.context else None,
                    user_id=request.context.get("user_id") if request.context else None,
                )
            elif agent_type == "spanish_tutor":
                from .spanish_tutor_agent import SpanishTutorDependencies

                deps = SpanishTutorDependencies(
                    student_level=request.context.get("student_level", "beginner") if request.context else "beginner",
                    conversation_mode=request.context.get("conversation_mode", "casual") if request.context else "casual",
                    focus_area=request.context.get("focus_area") if request.context else None,
                    previous_context=request.context.get("previous_context") if request.context else None,
                    response_style=request.context.get("response_style", "minimal") if request.context else "minimal",
                    include_translation=bool(request.context.get("include_translation", False)) if request.context else False,
                    include_corrections=bool(request.context.get("include_corrections", True)) if request.context else True,
                    include_grammar_notes=bool(request.context.get("include_grammar_notes", False)) if request.context else False,
                    include_vocabulary=bool(request.context.get("include_vocabulary", False)) if request.context else False,
                    include_cultural_notes=bool(request.context.get("include_cultural_notes", False)) if request.context else False,
                    include_encouragement=bool(request.context.get("include_encouragement", True)) if request.context else True,
                    include_next_topic=bool(request.context.get("include_next_topic", False)) if request.context else False,
                    max_reply_sentences=int(request.context.get("max_reply_sentences", 2)) if request.context else 2,
                    reading_mode=bool(request.context.get("reading_mode", False)) if request.context else False,
                )
            elif agent_type == "researcher":
                from .researcher_agent import ResearcherDependencies

                deps = ResearcherDependencies(
                    project_id=request.context.get("project_id") if request.context else None,
                    source_filter=request.context.get("source_filter") if request.context else None,
                    match_count=request.context.get("match_count", 5) if request.context else 5,
                    enable_web_search=request.context.get("enable_web_search", True) if request.context else True,
                    enable_image_analysis=request.context.get("enable_image_analysis", True) if request.context else True,
                    enable_code_execution=request.context.get("enable_code_execution", True) if request.context else True,
                    enable_knowledge_graph=request.context.get("enable_knowledge_graph", True) if request.context else True,
                    user_memories=request.context.get("user_memories", "") if request.context else "",
                    brave_api_key=os.getenv('BRAVE_API_KEY'),
                    searxng_base_url=os.getenv('SEARXNG_BASE_URL'),
                )
            else:
                # Default dependencies
                from .base_agent import ArchonDependencies

                deps = ArchonDependencies()

            # Use PydanticAI's run_stream method
            # run_stream returns an async context manager directly
            async with agent.run_stream(request.prompt, deps) as stream:
                # Stream text chunks as they arrive
                async for chunk in stream.stream_text():
                    event_data = json.dumps({"type": "stream_chunk", "content": chunk})
                    yield f"data: {event_data}\n\n"

                # Get the final structured result
                try:
                    final_result = await stream.get_data()
                    event_data = json.dumps({"type": "stream_complete", "content": final_result})
                    yield f"data: {event_data}\n\n"
                except Exception:
                    # If we can't get structured data, just send completion
                    event_data = json.dumps({"type": "stream_complete", "content": ""})
                    yield f"data: {event_data}\n\n"

        except Exception as e:
            logger.error(f"Error streaming {agent_type} agent: {e}")
            event_data = json.dumps({"type": "error", "error": str(e)})
            yield f"data: {event_data}\n\n"

    # Return SSE response
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


# Main entry point
if __name__ == "__main__":
    agents_port = os.getenv("ARCHON_AGENTS_PORT")
    if not agents_port:
        raise ValueError(
            "ARCHON_AGENTS_PORT environment variable is required. "
            "Please set it in your .env file or environment. "
            "Default value: 8052"
        )
    port = int(agents_port)

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,  # Disable reload in production
    )
