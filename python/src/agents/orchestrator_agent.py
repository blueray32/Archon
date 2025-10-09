"""
Orchestrator Agent - Routes tasks between Cloud (Codex/Claude) and Local (Ollama) executors.

Implements the Reduce & Delegate pattern for hybrid AI orchestration.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from .base_agent import ArchonDependencies, BaseAgent

logger = logging.getLogger(__name__)


class ExecutorType(str, Enum):
    """Available executors for task routing."""

    CLOUD_CODEX = "codex"  # Cloud - Codex CLI for batch/web/automation
    CLOUD_CLAUDE = "claude"  # Local/IDE - Claude for interactive/filesystem/privacy
    LOCAL_OLLAMA = "ollama"  # Local models via Ollama for cheap parallel tasks


class TaskPriority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Task(BaseModel):
    """Individual task definition."""

    id: str
    description: str
    route: ExecutorType
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    accept_criteria: str
    estimated_tokens: int = 0
    priority: TaskPriority = TaskPriority.MEDIUM
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoutingDecision(BaseModel):
    """Router's decision for a single task."""

    task_id: str
    executor: ExecutorType
    reasoning: str
    estimated_cost: float = 0.0
    estimated_latency_s: float = 0.0
    privacy_level: str = "internal"


class OrchestratorOutput(BaseModel):
    """Output from the orchestrator agent."""

    goal: str
    plan: list[Task]
    delegations: list[dict[str, Any]]
    artifacts: list[dict[str, str]]
    report: dict[str, Any]


@dataclass
class OrchestratorDependencies(ArchonDependencies):
    """Dependencies for orchestrator agent."""

    workspace_root: str = field(default_factory=lambda: os.getcwd())
    obsidian_vault: str | None = None
    ollama_host: str = "http://localhost:11434"
    max_cost: float = 2.50  # EUR
    max_latency: float = 300.0  # seconds
    privacy_level: str = "internal"
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    progress_callback: Any | None = None


class OrchestratorAgent(BaseAgent[OrchestratorDependencies, OrchestratorOutput]):
    """
    Orchestrator Agent for hybrid AI task routing and delegation.

    Routes tasks between:
    - Cloud Codex (batch/web/automation)
    - Local Claude (interactive/filesystem/privacy)
    - Local Ollama (cheap parallel work)

    Implements Reduce & Delegate (R&D) principles.
    """

    def __init__(
        self,
        model: str = "openai:gpt-4o",
        name: str = "OrchestratorAgent",
        retries: int = 2,
        enable_rate_limiting: bool = True,
        **agent_kwargs,
    ):
        super().__init__(
            model=model, name=name, retries=retries, enable_rate_limiting=enable_rate_limiting, **agent_kwargs
        )

    def _create_agent(self, **kwargs) -> Agent:
        """Create the PydanticAI agent with orchestrator configuration."""
        agent = Agent(
            model=self.model,
            deps_type=OrchestratorDependencies,
            result_type=OrchestratorOutput,
            system_prompt=self.get_system_prompt(),
            retries=self.retries,
            **kwargs,
        )

        # Add routing tool
        @agent.tool
        async def route_task(ctx, task_description: str, requires_privacy: bool = False) -> RoutingDecision:
            """
            Determine the best executor for a task based on routing policy.

            Args:
                ctx: Agent context
                task_description: What the task needs to do
                requires_privacy: Whether task involves confidential data

            Returns:
                RoutingDecision with executor choice and reasoning
            """
            deps: OrchestratorDependencies = ctx.deps

            # Privacy guard
            if requires_privacy or deps.privacy_level == "confidential":
                return RoutingDecision(
                    task_id="auto",
                    executor=ExecutorType.LOCAL_OLLAMA,
                    reasoning="Privacy-sensitive data requires local processing",
                    privacy_level=deps.privacy_level,
                )

            # Tooling requirement (shell, filesystem, Archon tools)
            if any(
                keyword in task_description.lower()
                for keyword in ["shell", "filesystem", "git", "file", "script", "local"]
            ):
                return RoutingDecision(
                    task_id="auto",
                    executor=ExecutorType.CLOUD_CLAUDE,
                    reasoning="Requires shell/filesystem access - route to Claude",
                    estimated_latency_s=5.0,
                )

            # Web/cloud operations
            if any(keyword in task_description.lower() for keyword in ["web", "api", "http", "fetch", "scrape"]):
                return RoutingDecision(
                    task_id="auto",
                    executor=ExecutorType.CLOUD_CODEX,
                    reasoning="Web/API operations - route to Codex",
                    estimated_latency_s=10.0,
                )

            # Cheap parallel operations (tagging, summarization, extraction)
            if any(
                keyword in task_description.lower()
                for keyword in ["tag", "summarize", "extract", "classify", "batch", "scan"]
            ):
                return RoutingDecision(
                    task_id="auto",
                    executor=ExecutorType.LOCAL_OLLAMA,
                    reasoning="Cheap parallel operation - route to Ollama",
                    estimated_cost=0.0,
                    estimated_latency_s=2.0,
                )

            # Default to Claude for general tasks
            return RoutingDecision(
                task_id="auto",
                executor=ExecutorType.CLOUD_CLAUDE,
                reasoning="General task - route to Claude",
                estimated_latency_s=5.0,
            )

        return agent

    def get_system_prompt(self) -> str:
        """Get the system prompt for the orchestrator agent."""
        return """You are the Orchestrator. You receive high-level goals and produce executable plans.

ROUTING POLICY:
- Claude (local/IDE): Filesystem ops, code edits, Obsidian notes, privacy-sensitive work
- Codex (cloud): Web APIs, batch automation, multi-service glue, long-running jobs
- Ollama (local): Cheap parallel LLM work (tagging, summarizing, extracting)

PLANNING RULES (Reduce & Delegate):
1. Reduce scope → smallest meaningful deliverable
2. Delegate to least-expensive capable agent
3. Parallelize independent subtasks
4. Converge with deterministic validation
5. Produce artifacts with clear paths and metadata

OUTPUT REQUIREMENTS:
- goal: Short user goal
- plan: List of Task objects with routing decisions
- delegations: Executor calls (placeholder for now)
- artifacts: Planned output paths under workspace_root/artifacts/<run_id>/
- report: Summary, validation plan, metrics

Keep answers deterministic, show assumptions, prefer shipped artifacts over perfect unfinished work.
"""

    async def plan_task(self, goal: str, deps: OrchestratorDependencies | None = None) -> OrchestratorOutput:
        """
        Plan a task and generate routing decisions.

        Args:
            goal: High-level user goal
            deps: Orchestrator dependencies

        Returns:
            OrchestratorOutput with plan and delegations
        """
        if deps is None:
            deps = OrchestratorDependencies()

        # Build the planning prompt
        prompt = f"""Goal: {goal}

Workspace: {deps.workspace_root}
Obsidian Vault: {deps.obsidian_vault or 'Not configured'}
Budget: {deps.max_cost} EUR
Privacy Level: {deps.privacy_level}

Generate a complete plan with tasks, routing decisions, and artifacts.
"""

        result = await self.run(prompt, deps)
        return result


# Helper function for standalone usage
async def orchestrate(
    goal: str,
    workspace_root: str | None = None,
    obsidian_vault: str | None = None,
    max_cost: float = 2.50,
    privacy_level: str = "internal",
) -> OrchestratorOutput:
    """
    Convenience function to orchestrate a task.

    Args:
        goal: High-level goal to accomplish
        workspace_root: Root directory for artifacts
        obsidian_vault: Path to Obsidian vault
        max_cost: Maximum cost in EUR
        privacy_level: public|internal|confidential

    Returns:
        OrchestratorOutput with plan and routing
    """
    agent = OrchestratorAgent()
    deps = OrchestratorDependencies(
        workspace_root=workspace_root or os.getcwd(),
        obsidian_vault=obsidian_vault,
        max_cost=max_cost,
        privacy_level=privacy_level,
    )

    return await agent.plan_task(goal, deps)
