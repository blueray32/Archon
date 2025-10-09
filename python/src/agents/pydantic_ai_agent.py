"""
PydanticAIAgent - PRP-guided RAG agent specialized for Pydantic AI docs

Builds on RagAgent with stricter PRP (Product Requirement Prompt) guidance:
- Concise, replayable context
- Prefer prime sources (llmstxt Pydantic docs) with explicit source_filter
- Short, structured answers with citations and next-step suggestions
- Optional context-bundle JSONL logging when enabled
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext

from .rag_agent import RagAgent, RagDependencies

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    # This file: Archon/python/src/agents/pydantic_ai_agent.py
    # repo root is 3 parents up from python/src/agents -> Archon
    return Path(__file__).resolve().parents[3]


def _bundles_root() -> Path:
    return _repo_root() / "agents" / "context-bundles"


def _ensure_bundle_dir() -> Path | None:
    try:
        root = _bundles_root()
        root.mkdir(parents=True, exist_ok=True)
        # Simple session directory by timestamp
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        bdir = root / f"session-{ts}"
        bdir.mkdir(parents=True, exist_ok=True)
        bpath = bdir / "bundle.jsonl"
        if not bpath.exists():
            with bpath.open("w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "type": "start",
                    "ts": datetime.utcnow().isoformat(),
                    "tool": "pydantic_ai_agent",
                }) + "\n")
        return bpath
    except Exception as e:
        logger.warning(f"Failed to create context-bundle path: {e}")
        return None


class PydanticAIAgent(RagAgent):
    """
    PRP-guided specialization of RagAgent for Pydantic AI workflows.
    """

    def _create_agent(self, **kwargs) -> Agent:
        agent = super()._create_agent(**kwargs)

        # Strong PRP system guidance specifically for this agent
        @agent.system_prompt
        async def prp_core_rules(ctx: RunContext[RagDependencies]) -> str:
            return (
                """
You are operating in PRP Mode for Pydantic AI:
- Build a concise, replayable context; prefer prime sources (Pydantic llmstxt)
- Keep answers short, structured, and cite sources when possible
- Use tools sparingly; focus on high-signal retrieval
- If context is missing, state assumptions and next steps briefly
"""
            )

        # Provide a minimal, canonical example as a fallback when examples are requested
        @agent.system_prompt
        async def example_fallback(ctx: RunContext[RagDependencies]) -> str:
            return (
                """
If the user asks for a short example of using PydanticAI Agent and relevant documentation is unavailable,
provide this concise Python example instead:

```python
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

class Deps(BaseModel):
    project_id: str | None = None

agent = Agent(
    model="openai:gpt-4o-mini",
    deps_type=Deps,
    system_prompt="You are a helpful assistant. Keep answers short."
)

@agent.tool
async def hello(ctx: RunContext[Deps], name: str) -> str:
    return f"Hello, {name}!"

# In an async context
# result = await agent.run("Say hello to Ciaran", Deps(project_id="demo"))
# print(result.data if hasattr(result, "data") else result)
```

Keep the response brief and include a one‑line note that this is a minimal fallback example.
"""
            )

        # Optional tool: record PRP step into a JSONL context-bundle
        @agent.tool
        async def prp_record_step(
            ctx: RunContext[RagDependencies], step: str, details: str | None = None
        ) -> str:
            """Record a concise PRP step to a JSONL context bundle (best-effort)."""
            bundle_path = _ensure_bundle_dir()
            if not bundle_path:
                return "context-bundle unavailable"
            try:
                rec = {
                    "type": "step",
                    "ts": datetime.utcnow().isoformat(),
                    "agent": "pydantic_ai",
                    "project_id": ctx.deps.project_id,
                    "source_filter": ctx.deps.source_filter,
                    "step": step,
                    "details": details or "",
                }
                with bundle_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                return "recorded"
            except Exception as e:
                logger.warning(f"Failed to write bundle step: {e}")
                return "record failed"

        return agent
