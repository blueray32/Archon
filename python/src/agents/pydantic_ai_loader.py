"""
Dynamic loader for the Pydantic AI agent implementation.

Allows swapping in an external agent class via env var without changing server code.

Usage:
- Set PYDANTIC_AI_AGENT_CLASS to "module.path:ClassName" to override.
- If not set or import fails, falls back to local PydanticAIAgent.
"""

from __future__ import annotations

import os
import importlib
from typing import Type

from .pydantic_ai_agent import PydanticAIAgent as DefaultPydanticAIAgent


def get_pydantic_ai_agent_class() -> Type:
    target = os.getenv("PYDANTIC_AI_AGENT_CLASS")
    if not target:
        return DefaultPydanticAIAgent
    try:
        mod_path, _, cls_name = target.partition(":")
        if not mod_path or not cls_name:
            raise ValueError("PYDANTIC_AI_AGENT_CLASS must be 'module.path:ClassName'")
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, cls_name)
        if not isinstance(cls, type):
            raise TypeError("Resolved object is not a class")
        return cls
    except Exception:
        # Fallback to default if anything fails
        return DefaultPydanticAIAgent

