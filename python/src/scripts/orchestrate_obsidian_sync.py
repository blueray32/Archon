#!/usr/bin/env python3
"""
End-to-end orchestration workflow: Obsidian Vault Indexing & Archon Sync

Demonstrates:
- Orchestrator agent planning
- Task routing (Claude, Codex, Ollama)
- Obsidian vault scanning
- Auto-tagging with Ollama
- Archon memory sync
- Execution reporting

Usage:
    python src/scripts/orchestrate_obsidian_sync.py --vault /path/to/vault
    python src/scripts/orchestrate_obsidian_sync.py --vault /path/to/vault --dry-run
    python src/scripts/orchestrate_obsidian_sync.py --auto-tag --create-embeddings
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "python"))

# Load environment variables from .env
from dotenv import load_dotenv
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

from src.agents.archon_memory_sync import ArchonMemorySync
from src.agents.obsidian_tools import ObsidianTools
from src.agents.ollama_client import OllamaClient
from src.agents.orchestrator_agent import ExecutorType, OrchestratorAgent, OrchestratorDependencies, Task, TaskPriority
from src.agents.task_executor import ExecutorConfig, TaskExecutor
from src.server.services.client_manager import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def create_obsidian_sync_plan(
    vault_path: str, auto_tag: bool = False, create_embeddings: bool = False
) -> dict:
    """
    Create a plan for Obsidian vault sync using the orchestrator.

    Args:
        vault_path: Path to Obsidian vault
        auto_tag: Whether to auto-tag notes
        create_embeddings: Whether to create embeddings

    Returns:
        Plan dictionary (simplified, not full OrchestratorOutput)
    """
    tasks = []

    # Task 1: Scan vault
    tasks.append(
        {
            "id": "T1",
            "description": "Scan Obsidian vault and collect note paths, headings, tags",
            "route": ExecutorType.CLOUD_CLAUDE,
            "inputs": [vault_path],
            "outputs": ["vault_index.json"],
            "depends_on": [],
            "accept_criteria": "JSON file with complete vault index",
            "priority": TaskPriority.HIGH,
        }
    )

    # Task 2: Auto-tag (optional)
    if auto_tag:
        tasks.append(
            {
                "id": "T2",
                "description": "Batch-tag notes by topics using Ollama (MEP, BIM, Revit, Spanish, etc.)",
                "route": ExecutorType.LOCAL_OLLAMA,
                "inputs": ["vault_index.json"],
                "outputs": ["tag_suggestions.json"],
                "depends_on": ["T1"],
                "accept_criteria": "JSON with tag suggestions for each note",
                "priority": TaskPriority.MEDIUM,
            }
        )

        tasks.append(
            {
                "id": "T3",
                "description": "Update note frontmatter with suggested tags",
                "route": ExecutorType.CLOUD_CLAUDE,
                "inputs": ["tag_suggestions.json"],
                "outputs": ["tagging_report.txt"],
                "depends_on": ["T2"],
                "accept_criteria": "Notes updated with new tags, change log created",
                "priority": TaskPriority.MEDIUM,
            }
        )

    # Task 4: Sync to Archon
    final_task_deps = ["T3"] if auto_tag else ["T1"]
    tasks.append(
        {
            "id": "T4",
            "description": "Sync vault index and notes to Archon memory",
            "route": ExecutorType.CLOUD_CLAUDE,
            "inputs": ["vault_index.json"],
            "outputs": ["sync_report.json", "archon_index.md"],
            "depends_on": final_task_deps,
            "accept_criteria": "Vault data stored in Archon database, index created",
            "priority": TaskPriority.HIGH,
        }
    )

    return {
        "goal": f"Index Obsidian vault at {vault_path}, auto-tag notes, sync to Archon",
        "tasks": tasks,
        "workspace": os.getcwd(),
        "vault_path": vault_path,
        "auto_tag": auto_tag,
        "create_embeddings": create_embeddings,
    }


async def execute_obsidian_sync(
    vault_path: str,
    auto_tag: bool = False,
    create_embeddings: bool = False,
    dry_run: bool = False,
    ollama_host: str = "http://localhost:11434",
) -> dict:
    """
    Execute the full Obsidian sync workflow.

    Args:
        vault_path: Path to Obsidian vault
        auto_tag: Whether to auto-tag notes
        create_embeddings: Whether to create embeddings
        dry_run: If True, only plan (don't execute)
        ollama_host: Ollama API endpoint

    Returns:
        Execution report
    """
    logger.info("=== Obsidian Vault Orchestration ===")
    logger.info(f"Vault: {vault_path}")
    logger.info(f"Auto-tag: {auto_tag}")
    logger.info(f"Create embeddings: {create_embeddings}")
    logger.info(f"Dry run: {dry_run}")

    # Step 1: Create plan
    logger.info("\n[1/4] Creating orchestration plan...")
    plan = await create_obsidian_sync_plan(vault_path, auto_tag, create_embeddings)

    logger.info(f"Created plan with {len(plan['tasks'])} tasks:")
    for task in plan["tasks"]:
        logger.info(f"  - {task['id']}: {task['description']} [{task['route']}]")

    if dry_run:
        logger.info("\nDry run - stopping here. Plan:")
        print(json.dumps(plan, indent=2, default=str))
        return {"dry_run": True, "plan": plan}

    # Step 2: Scan vault
    logger.info("\n[2/4] Scanning Obsidian vault...")
    obsidian_tools = ObsidianTools(vault_path)
    vault_index = obsidian_tools.scan_vault()

    logger.info(f"Scanned {vault_index.notes_count} notes")
    logger.info(f"Found {len(vault_index.tags_summary)} unique tags")
    logger.info(f"Found {len(vault_index.areas_summary)} areas")

    # Save vault index
    artifacts_dir = Path("artifacts") / f"obsidian_sync_{vault_index.scanned_at[:10]}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    index_path = artifacts_dir / "vault_index.json"
    index_path.write_text(vault_index.model_dump_json(indent=2))
    logger.info(f"Saved vault index to {index_path}")

    # Step 3: Auto-tag (optional)
    tag_suggestions = {}
    if auto_tag:
        logger.info("\n[3/4] Auto-tagging notes with Ollama...")
        async with OllamaClient(base_url=ollama_host) as ollama:
            # Check health
            healthy = await ollama.health_check()
            if not healthy:
                logger.warning(f"Ollama not available at {ollama_host} - skipping auto-tagging")
            else:
                tag_suggestions = await obsidian_tools.auto_tag_notes(
                    vault_index.notes, ollama, model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
                )

                logger.info(f"Generated tag suggestions for {len(tag_suggestions)} notes")

                # Save suggestions
                suggestions_path = artifacts_dir / "tag_suggestions.json"
                suggestions_path.write_text(json.dumps(tag_suggestions, indent=2))
                logger.info(f"Saved tag suggestions to {suggestions_path}")

                # Update frontmatter (preview first)
                logger.info("\nTag suggestion preview (first 5 notes):")
                for i, (note_path, tags) in enumerate(list(tag_suggestions.items())[:5]):
                    logger.info(f"  {note_path}: {tags}")

                # Apply tags (if not dry run)
                logger.info("\nApplying tags to notes...")
                updated_count = 0
                for note in vault_index.notes:
                    if note.path in tag_suggestions:
                        suggested_tags = tag_suggestions[note.path]
                        note_file = Path(vault_path) / note.path

                        try:
                            obsidian_tools.update_frontmatter(
                                note_file,
                                {
                                    "area": suggested_tags.get("area"),
                                    "service": suggested_tags.get("service"),
                                    "status": suggested_tags.get("status"),
                                    "source": "archon",
                                },
                                merge=True,
                            )
                            updated_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to update {note.path}: {e}")

                logger.info(f"Updated {updated_count} notes with tags")
    else:
        logger.info("\n[3/4] Skipping auto-tagging (disabled)")

    # Step 4: Sync to Archon
    logger.info("\n[4/4] Syncing to Archon memory...")
    try:
        supabase = get_supabase_client()

        # Check if we should create embeddings
        embedding_service = None
        if create_embeddings:
            from src.server.services.prp_service import PRPService

            embedding_service = PRPService(supabase)

        sync_service = ArchonMemorySync(supabase, embedding_service)
        sync_report = await sync_service.sync_vault_index(vault_index, create_embeddings=create_embeddings)

        logger.info("Archon sync report:")
        for key, value in sync_report.items():
            logger.info(f"  {key}: {value}")

        # Save sync report
        sync_report_path = artifacts_dir / "archon_sync_report.json"
        sync_report_path.write_text(json.dumps(sync_report, indent=2))

    except Exception as e:
        logger.error(f"Failed to sync to Archon: {e}")
        sync_report = {"error": str(e)}

    # Create index note
    logger.info("\nCreating Archon index note...")
    index_note_path = obsidian_tools.create_index_note(vault_index)
    logger.info(f"Created index at {index_note_path}")

    # Final report
    report = {
        "vault_path": vault_path,
        "notes_scanned": vault_index.notes_count,
        "tags_found": len(vault_index.tags_summary),
        "areas_found": len(vault_index.areas_summary),
        "auto_tagged": len(tag_suggestions),
        "archon_sync": sync_report,
        "artifacts_dir": str(artifacts_dir),
        "index_note": str(index_note_path),
    }

    logger.info("\n=== Orchestration Complete ===")
    logger.info(json.dumps(report, indent=2))

    return report


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Orchestrate Obsidian vault indexing and Archon sync")
    parser.add_argument(
        "--vault", type=str, default=os.getenv("OBSIDIAN_VAULT"), help="Path to Obsidian vault (or set OBSIDIAN_VAULT)"
    )
    parser.add_argument("--auto-tag", action="store_true", help="Auto-tag notes using Ollama")
    parser.add_argument("--create-embeddings", action="store_true", help="Create embeddings for notes")
    parser.add_argument("--dry-run", action="store_true", help="Create plan only, don't execute")
    parser.add_argument("--ollama-host", type=str, default="http://localhost:11434", help="Ollama API endpoint")

    args = parser.parse_args()

    if not args.vault:
        logger.error("Vault path required. Use --vault or set OBSIDIAN_VAULT environment variable.")
        sys.exit(1)

    vault_path = Path(args.vault)
    if not vault_path.exists():
        logger.error(f"Vault path does not exist: {vault_path}")
        sys.exit(1)

    try:
        report = await execute_obsidian_sync(
            str(vault_path),
            auto_tag=args.auto_tag,
            create_embeddings=args.create_embeddings,
            dry_run=args.dry_run,
            ollama_host=args.ollama_host,
        )

        # Save final report
        final_report_path = Path("artifacts") / "obsidian_orchestration_report.json"
        final_report_path.parent.mkdir(exist_ok=True)
        final_report_path.write_text(json.dumps(report, indent=2))

        logger.info(f"\nFinal report saved to {final_report_path}")

    except Exception as e:
        logger.error(f"Orchestration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
