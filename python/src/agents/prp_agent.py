"""
PRP Agent - ChatGPT-style agent with PRP-driven context and persistent memory.

This agent uses RAG over PRPs and conversation history to provide contextual,
conversational responses similar to ChatGPT.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from .base_agent import ArchonDependencies, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class PRPDependencies(ArchonDependencies):
    """Dependencies for PRP agent."""

    session_id: str | None = None
    persona_name: str = "chat_gpt_like"
    rag_retriever: Any | None = None  # RAG retrieval function
    progress_callback: Any | None = None


class PRPOutput(BaseModel):
    """Output model for PRP agent responses."""

    output: str
    context_used: list[str] | None = None
    sources: list[str] | None = None
    metadata: dict[str, Any] | None = None


class PRPAgent(BaseAgent[PRPDependencies, PRPOutput]):
    """
    PRP Agent for ChatGPT-style conversational AI with PRP context.

    Features:
    - RAG retrieval over PRPs and conversation history
    - Persona-driven system prompts
    - Persistent memory via embeddings
    - Streaming support
    """

    def __init__(
        self,
        model: str = "openai:gpt-4o-mini",
        name: str = "PRPAgent",
        retries: int = 3,
        enable_rate_limiting: bool = True,
        **agent_kwargs,
    ):
        super().__init__(
            model=model, name=name, retries=retries, enable_rate_limiting=enable_rate_limiting, **agent_kwargs
        )

    def _create_agent(self, **kwargs) -> Agent:
        """Create the PydanticAI agent with PRP-specific configuration."""
        return Agent(
            model=self.model,
            deps_type=PRPDependencies,
            output_type=PRPOutput,
            system_prompt=self.get_system_prompt(),
            retries=self.retries,
            **kwargs,
        )

    def get_system_prompt(self) -> str:
        """
        Get the base system prompt for PRP agent.
        This can be overridden by persona configuration at runtime.
        """
        return """You are a helpful engineering copilot. Behave like ChatGPT:
- Clear, actionable explanations, minimal fluff.
- Numbered steps when appropriate.
- If unsure, state assumptions and proceed with best effort.
- Maintain continuity by recalling prior context from memory.

Use retrieved context from PRPs and previous conversations to provide informed responses.
When relevant context is provided, acknowledge it and use it to inform your answer.
"""

    async def run_with_context(
        self,
        user_prompt: str,
        session_id: str,
        persona_name: str = "chat_gpt_like",
        rag_retriever: Any | None = None,
        progress_callback: Any | None = None,
    ) -> PRPOutput:
        """
        Run the agent with RAG context retrieval.

        Args:
            user_prompt: The user's message
            session_id: Chat session ID for context retrieval
            persona_name: Name of persona to use
            rag_retriever: Function to retrieve RAG context
            progress_callback: Optional callback for progress updates

        Returns:
            PRPOutput with response and metadata
        """
        # Build dependencies
        deps = PRPDependencies(
            session_id=session_id,
            persona_name=persona_name,
            rag_retriever=rag_retriever,
            progress_callback=progress_callback,
        )

        # Retrieve context if retriever is provided
        context_str = ""
        sources = []
        if rag_retriever:
            try:
                context_results = await rag_retriever(session_id, user_prompt)
                if context_results:
                    context_str = context_results.get("context", "")
                    sources = context_results.get("sources", [])
                    if progress_callback:
                        await progress_callback(
                            {"step": "rag_retrieval", "log": f"Retrieved {len(sources)} context sources"}
                        )
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")
                if progress_callback:
                    await progress_callback({"step": "rag_retrieval", "log": f"Context retrieval warning: {str(e)}"})

        # Build enhanced prompt with context
        enhanced_prompt = user_prompt
        if context_str:
            enhanced_prompt = f"""Retrieved Context:
{context_str}

User Question:
{user_prompt}

Please provide a helpful response using the context where relevant."""

        # Run the agent
        result = await self.run(enhanced_prompt, deps)

        # Add sources to result if available
        if sources:
            result.sources = sources

        return result


# Helper function for standalone usage
async def run_prp_agent(
    prompt: str,
    session_id: str = "default",
    persona_name: str = "chat_gpt_like",
    rag_retriever: Any | None = None,
    model: str | None = None,
) -> PRPOutput:
    """
    Convenience function to run PRP agent.

    Args:
        prompt: User's message
        session_id: Chat session ID
        persona_name: Persona to use
        rag_retriever: Optional RAG retrieval function
        model: Optional model override

    Returns:
        PRPOutput with agent response
    """
    agent_model = model or os.getenv("PRP_CHAT_MODEL", "openai:gpt-4o-mini")
    agent = PRPAgent(model=agent_model)

    return await agent.run_with_context(
        user_prompt=prompt, session_id=session_id, persona_name=persona_name, rag_retriever=rag_retriever
    )