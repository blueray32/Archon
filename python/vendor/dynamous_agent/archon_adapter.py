"""
Archon adapter for the Dynamous "4_Pydantic_AI_Agent" implementation.

This bridges an external PydanticAI agent (factory or class) into Archon's
Agents Service interface without changing external source code.

Configuration via env:
- DYNAMOUS_AGENT_FACTORY: "module.path:factory_or_class" (default tries
  python.vendor.4_Pydantic_AI_Agent.agent:create_agent)
  The factory can be:
    * a function returning a pydantic_ai.Agent
    * a class (will be instantiated), optionally accepting model=...

Usage with server loader:
- PYDANTIC_AI_AGENT_CLASS=python.vendor.dynamous_agent.archon_adapter:DynamousPydanticAIAgentAdapter

Optional envs mirrored from the Dynamous project are simply passed through
the environment and read by the vendor code directly (e.g., LLM_* vars).
"""

from __future__ import annotations

import importlib
import os
from typing import Any, Callable

from pydantic_ai import Agent as PydanticAIAgent

from ...src.agents.base_agent import ArchonDependencies, BaseAgent


def _load_factory(target: str) -> Callable[[], PydanticAIAgent] | type | Any:
    mod_path, _, sym = target.partition(":")
    if not mod_path or not sym:
        raise ValueError("DYNAMOUS_AGENT_FACTORY must be 'module.path:symbol'")
    mod = importlib.import_module(mod_path)
    obj = getattr(mod, sym)
    return obj


class DynamousPydanticAIAgentAdapter(BaseAgent[ArchonDependencies, Any]):
    """
    Adapter that wraps a vendor PydanticAI agent for Archon's agent server.
    """

    def __init__(self, model: str | None = None, **kwargs):
        # Honor Archon server model if provided, allow vendor code to override via env
        self._archon_model = model
        super().__init__(model=model or os.getenv("LLM_CHOICE", "openai:gpt-4o-mini"), name="DynamousPydanticAIAgent", **kwargs)

    def _create_agent(self, **kwargs) -> PydanticAIAgent:
        # Determine factory symbol to load the vendor agent
        target = os.getenv(
            "DYNAMOUS_AGENT_FACTORY",
            "python.vendor.4_Pydantic_AI_Agent.agent:create_agent",
        )
        obj = _load_factory(target)

        # Cases:
        # 1) function -> returns pydantic_ai.Agent
        # 2) class -> returns instance (try with model kw first)
        # 3) instance -> already usable
        agent: PydanticAIAgent
        if callable(obj):  # function or class
            try:
                agent = obj(model=self._archon_model or self.model)
            except TypeError:
                produced = obj()
                if isinstance(produced, PydanticAIAgent):
                    agent = produced
                else:
                    # If a class instance was returned, try to access its `.agent`
                    agent = getattr(produced, "agent")
        else:
            # Direct instance or module attr
            agent = obj if isinstance(obj, PydanticAIAgent) else getattr(obj, "agent")

        if not isinstance(agent, PydanticAIAgent):
            raise TypeError("Dynamous adapter expected a pydantic_ai.Agent instance")

        return agent

    def get_system_prompt(self) -> str:
        # Vendor's agent defines its own prompts; Archon doesn't override
        return "Dynamous Pydantic AI Agent"

