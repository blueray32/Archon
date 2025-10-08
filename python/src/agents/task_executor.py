"""
Task Executor - Executes orchestrated plans with Reduce & Delegate principles.

Handles task execution across different executors (Claude, Codex, Ollama).
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .ollama_client import OllamaClient
from .orchestrator_agent import ExecutorType, OrchestratorOutput, Task

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskResult(BaseModel):
    """Result from task execution."""

    task_id: str
    status: TaskStatus
    executor: ExecutorType
    output: Any = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_s: float = 0.0
    artifacts: list[str] = []


class ExecutionReport(BaseModel):
    """Report from executing an orchestrated plan."""

    run_id: str
    goal: str
    started_at: str
    completed_at: str | None = None
    duration_s: float = 0.0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_total: int = 0
    results: list[TaskResult] = []
    artifacts: list[str] = []
    summary: str = ""
    validation: str = ""
    metrics: dict[str, Any] = {}


@dataclass
class ExecutorConfig:
    """Configuration for task executors."""

    workspace_root: str = field(default_factory=lambda: os.getcwd())
    obsidian_vault: str | None = None
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    max_concurrent_ollama: int = 5
    progress_callback: Any | None = None


class TaskExecutor:
    """
    Executes orchestrated plans across multiple executors.

    Supports:
    - Dependency resolution (topological sort)
    - Parallel execution where possible
    - Progress tracking
    - Artifact management
    """

    def __init__(self, config: ExecutorConfig | None = None):
        """
        Initialize task executor.

        Args:
            config: Executor configuration
        """
        self.config = config or ExecutorConfig()
        self.ollama = OllamaClient(base_url=self.config.ollama_host)
        self.artifacts_dir = Path(self.config.workspace_root) / "artifacts"
        self.artifacts_dir.mkdir(exist_ok=True)

    async def execute_plan(self, plan: OrchestratorOutput) -> ExecutionReport:
        """
        Execute an orchestrated plan.

        Args:
            plan: OrchestratorOutput from orchestrator agent

        Returns:
            ExecutionReport with results and artifacts
        """
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.artifacts_dir / run_id
        run_dir.mkdir(exist_ok=True)

        started_at = datetime.now()
        results: list[TaskResult] = []

        logger.info(f"Starting execution of plan: {plan.goal}")

        # Build dependency graph
        task_graph = self._build_dependency_graph(plan.plan)

        # Execute tasks in topological order
        completed_tasks = set()

        while len(completed_tasks) < len(plan.plan):
            # Find tasks ready to execute (all dependencies completed)
            ready_tasks = [
                task
                for task in plan.plan
                if task.id not in completed_tasks and all(dep in completed_tasks for dep in task.depends_on)
            ]

            if not ready_tasks:
                # Check for circular dependencies or failures
                remaining = [task for task in plan.plan if task.id not in completed_tasks]
                logger.error(f"No tasks ready to execute. Remaining: {[t.id for t in remaining]}")
                break

            # Execute ready tasks in parallel
            task_results = await asyncio.gather(
                *[self._execute_task(task, run_dir) for task in ready_tasks], return_exceptions=True
            )

            for task, result in zip(ready_tasks, task_results):
                if isinstance(result, Exception):
                    logger.error(f"Task {task.id} failed with exception: {result}")
                    results.append(
                        TaskResult(
                            task_id=task.id,
                            status=TaskStatus.FAILED,
                            executor=task.route,
                            error=str(result),
                            started_at=datetime.now().isoformat(),
                            completed_at=datetime.now().isoformat(),
                        )
                    )
                else:
                    results.append(result)

                completed_tasks.add(task.id)

                if self.config.progress_callback:
                    await self.config.progress_callback(
                        {
                            "step": "task_execution",
                            "task_id": task.id,
                            "status": result.status if not isinstance(result, Exception) else "failed",
                            "progress": len(completed_tasks),
                            "total": len(plan.plan),
                        }
                    )

        # Generate report
        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        completed_count = sum(1 for r in results if r.status == TaskStatus.COMPLETED)
        failed_count = sum(1 for r in results if r.status == TaskStatus.FAILED)

        all_artifacts = [artifact for result in results for artifact in result.artifacts]

        report = ExecutionReport(
            run_id=run_id,
            goal=plan.goal,
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_s=duration,
            tasks_completed=completed_count,
            tasks_failed=failed_count,
            tasks_total=len(plan.plan),
            results=results,
            artifacts=all_artifacts,
            summary=f"Executed {len(plan.plan)} tasks: {completed_count} completed, {failed_count} failed",
            validation=self._validate_results(results, plan),
            metrics={"total_duration_s": duration, "avg_task_duration_s": duration / len(plan.plan) if plan.plan else 0},
        )

        # Save report
        report_path = run_dir / "execution_report.json"
        report_path.write_text(report.model_dump_json(indent=2))
        logger.info(f"Execution report saved to {report_path}")

        return report

    def _build_dependency_graph(self, tasks: list[Task]) -> dict[str, list[str]]:
        """Build dependency graph from task list."""
        graph = {task.id: task.depends_on for task in tasks}
        return graph

    async def _execute_task(self, task: Task, run_dir: Path) -> TaskResult:
        """
        Execute a single task.

        Args:
            task: Task to execute
            run_dir: Directory for run artifacts

        Returns:
            TaskResult with execution outcome
        """
        started_at = datetime.now()
        logger.info(f"Executing task {task.id} on {task.route}")

        try:
            if task.route == ExecutorType.LOCAL_OLLAMA:
                output = await self._execute_ollama_task(task)
            elif task.route == ExecutorType.CLOUD_CLAUDE:
                output = await self._execute_claude_task(task)
            elif task.route == ExecutorType.CLOUD_CODEX:
                output = await self._execute_codex_task(task)
            else:
                raise ValueError(f"Unknown executor type: {task.route}")

            # Save task output
            task_output_path = run_dir / f"{task.id}_output.json"
            task_output_path.write_text(json.dumps(output, indent=2))

            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                executor=task.route,
                output=output,
                started_at=started_at.isoformat(),
                completed_at=completed_at.isoformat(),
                duration_s=duration,
                artifacts=[str(task_output_path)],
            )

        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}")
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                executor=task.route,
                error=str(e),
                started_at=started_at.isoformat(),
                completed_at=completed_at.isoformat(),
                duration_s=duration,
            )

    async def _execute_ollama_task(self, task: Task) -> dict[str, Any]:
        """Execute task using local Ollama model."""
        prompt = f"""Task: {task.description}

Inputs: {', '.join(task.inputs) if task.inputs else 'None'}
Expected Outputs: {', '.join(task.outputs) if task.outputs else 'None'}
Acceptance Criteria: {task.accept_criteria}

Please complete this task and provide your output.
"""

        result = await self.ollama.generate(
            model=self.config.ollama_model,
            prompt=prompt,
            system="You are a helpful assistant executing tasks as part of a larger workflow. Be concise and precise.",
        )

        return {"executor": "ollama", "model": self.config.ollama_model, "result": result, "task_id": task.id}

    async def _execute_claude_task(self, task: Task) -> dict[str, Any]:
        """Execute task using Claude (placeholder for now)."""
        logger.warning(f"Claude executor not fully implemented. Task {task.id} marked as manual.")
        return {
            "executor": "claude",
            "task_id": task.id,
            "note": "Manual execution required - Claude tasks need interactive IDE integration",
            "task_description": task.description,
        }

    async def _execute_codex_task(self, task: Task) -> dict[str, Any]:
        """Execute task using Codex (placeholder for now)."""
        logger.warning(f"Codex executor not fully implemented. Task {task.id} marked as manual.")
        return {
            "executor": "codex",
            "task_id": task.id,
            "note": "Manual execution required - Codex tasks need Codex CLI integration",
            "task_description": task.description,
        }

    def _validate_results(self, results: list[TaskResult], plan: OrchestratorOutput) -> str:
        """Validate execution results against plan."""
        validation_lines = []

        completed = [r for r in results if r.status == TaskStatus.COMPLETED]
        failed = [r for r in results if r.status == TaskStatus.FAILED]

        validation_lines.append(f"✓ {len(completed)}/{len(plan.plan)} tasks completed successfully")

        if failed:
            validation_lines.append(f"✗ {len(failed)} tasks failed:")
            for result in failed:
                validation_lines.append(f"  - {result.task_id}: {result.error}")

        return "\n".join(validation_lines)


# Helper function for standalone usage
async def execute_orchestrated_plan(
    plan: OrchestratorOutput, workspace_root: str | None = None, ollama_host: str = "http://localhost:11434"
) -> ExecutionReport:
    """
    Execute an orchestrated plan.

    Args:
        plan: OrchestratorOutput from orchestrator
        workspace_root: Root for artifacts
        ollama_host: Ollama API endpoint

    Returns:
        ExecutionReport with results
    """
    config = ExecutorConfig(workspace_root=workspace_root or os.getcwd(), ollama_host=ollama_host)

    executor = TaskExecutor(config)
    return await executor.execute_plan(plan)
