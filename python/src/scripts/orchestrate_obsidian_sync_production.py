#!/usr/bin/env python3
"""
Production-Grade Obsidian Orchestration

Features:
- Content hashing for idempotency (skip unchanged notes)
- Sharding + resume capability
- Concurrency controls
- Frontmatter hygiene
- Metrics & manifest output
- Changes log (CSV)
- Git integration (optional)
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Setup path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "python"))

# Load env
from dotenv import load_dotenv

env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

from src.agents.archon_memory_sync import ArchonMemorySync
from src.agents.obsidian_tools_production import ObsidianToolsProduction, SyncState
from src.agents.ollama_client import OllamaClient
from src.server.services.client_manager import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ProductionMetrics:
    """Track metrics for observability."""

    def __init__(self):
        self.start_time = datetime.now()
        self.notes_scanned = 0
        self.notes_processed = 0
        self.notes_skipped_unchanged = 0
        self.notes_skipped_rules = 0
        self.notes_failed = 0
        self.tags_applied = 0
        self.errors = []
        self.durations = {}

    def to_dict(self) -> dict:
        end_time = datetime.now()
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_s": (end_time - self.start_time).total_seconds(),
            "notes_scanned": self.notes_scanned,
            "notes_processed": self.notes_processed,
            "notes_skipped_unchanged": self.notes_skipped_unchanged,
            "notes_skipped_rules": self.notes_skipped_rules,
            "notes_failed": self.notes_failed,
            "tags_applied": self.tags_applied,
            "durations": self.durations,
            "errors": self.errors[:50],  # Limit error list
        }


async def run_production_sync(
    vault_path: str,
    auto_tag: bool = False,
    create_embeddings: bool = False,
    concurrency: int = 5,
    shard_size: int = 2000,
    resume: bool = True,
    state_file: str = "sync_state.json",
    dry_run: bool = False,
    git_commit: bool = False,
    sync_to_db_only: bool = False,
) -> dict:
    """
    Run production-grade orchestration.

    Args:
        vault_path: Path to Obsidian vault
        auto_tag: Auto-tag with Ollama
        create_embeddings: Create embeddings for RAG
        concurrency: Max concurrent Ollama calls
        shard_size: Process notes in shards
        resume: Resume from state file
        state_file: Path to state.json
        dry_run: Don't write changes
        git_commit: Create git commit after sync

    Returns:
        Execution report
    """
    metrics = ProductionMetrics()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifacts_dir = Path("artifacts") / f"obsidian_sync_{run_id}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    state_path = Path(state_file)
    changes_log_path = artifacts_dir / "changes_log.csv"

    logger.info("=== Production Obsidian Orchestration ===")
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Vault: {vault_path}")
    logger.info(f"Concurrency: {concurrency}")
    logger.info(f"Shard size: {shard_size}")
    logger.info(f"Resume: {resume}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Sync-to-DB only: {sync_to_db_only}")

    # Load state
    state = SyncState.load(state_path) if resume else SyncState()
    state.last_run_timestamp = datetime.now().isoformat()

    # Initialize tools
    tools = ObsidianToolsProduction(vault_path)

    # Step 1: Scan vault
    logger.info("\n[1/4] Scanning vault...")
    scan_start = datetime.now()

    index, state = tools.scan_vault(state=state)

    metrics.notes_scanned = index.notes_count
    metrics.notes_skipped_rules = len(index.skipped_files)
    metrics.durations["scan"] = (datetime.now() - scan_start).total_seconds()

    logger.info(f"✓ Scanned {index.notes_count} notes")
    logger.info(f"✓ Skipped {len(index.skipped_files)} files by rules")
    logger.info(f"✓ Found {len(index.tags_summary)} unique tags")

    # Save vault index
    index_path = artifacts_dir / "vault_index.json"
    index_path.write_text(index.model_dump_json(indent=2))
    logger.info(f"✓ Saved index to {index_path}")

    # Step 2: Auto-tag (optional)
    # Force-disable auto-tagging when syncing to DB only
    if sync_to_db_only:
        auto_tag = False

    tag_suggestions = {}
    if auto_tag:
        logger.info("\n[2/4] Auto-tagging with Ollama...")
        tag_start = datetime.now()

        async with OllamaClient() as ollama:
            healthy = await ollama.health_check()
            if not healthy:
                logger.warning("Ollama not available - skipping auto-tagging")
                metrics.errors.append("ollama_unavailable")
            else:
                model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
                logger.info(f"Using model: {model}, concurrency: {concurrency}")

                # Process in shards
                all_notes = index.notes
                for shard_idx in range(0, len(all_notes), shard_size):
                    shard = all_notes[shard_idx : shard_idx + shard_size]
                    shard_num = shard_idx // shard_size + 1
                    total_shards = (len(all_notes) + shard_size - 1) // shard_size

                    logger.info(f"Processing shard {shard_num}/{total_shards} ({len(shard)} notes)")

                    shard_suggestions, state = await tools.auto_tag_notes_with_resume(
                        shard, ollama, model, state, max_concurrent=concurrency
                    )

                    tag_suggestions.update(shard_suggestions)

                    # Save state after each shard
                    if not dry_run:
                        state.save(state_path)
                        logger.info(f"✓ Saved state (processed {state.processed_count} notes)")

        metrics.tags_applied = len(tag_suggestions)
        metrics.notes_processed = len(tag_suggestions)
        metrics.notes_skipped_unchanged = len(index.notes) - len(tag_suggestions)
        metrics.durations["auto_tag"] = (datetime.now() - tag_start).total_seconds()

        logger.info(f"✓ Generated {len(tag_suggestions)} tag suggestions")
        logger.info(f"✓ Skipped {metrics.notes_skipped_unchanged} unchanged notes")

        # Save suggestions
        suggestions_path = artifacts_dir / "tag_suggestions.json"
        suggestions_path.write_text(json.dumps(tag_suggestions, indent=2))

        # Step 3: Apply tags
        if tag_suggestions:
            logger.info("\n[3/4] Applying tags to notes...")
            apply_start = datetime.now()

            # Initialize changes log
            with open(changes_log_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["path", "field", "old_value", "new_value", "reason"])

            updated_count = 0
            for note in index.notes:
                if note.path not in tag_suggestions:
                    continue

                suggested_tags = tag_suggestions[note.path]
                note_file = Path(vault_path) / note.path

                try:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would update {note.path} with {suggested_tags}")
                        updated_count += 1
                    else:
                        changes = tools.update_frontmatter_hygiene(
                            note_file,
                            {
                                "area": suggested_tags.get("area"),
                                "service": suggested_tags.get("service"),
                                "status": suggested_tags.get("status"),
                                "source": "archon",
                            },
                            merge=True,
                            preserve_existing=True,
                        )

                        # Log changes
                        with open(changes_log_path, "a", newline="") as f:
                            writer = csv.writer(f)
                            for field, change in changes.items():
                                writer.writerow(
                                    [note.path, field, change.get("old"), change.get("new"), "auto_tag"]
                                )

                        updated_count += 1

                except Exception as e:
                    logger.error(f"Failed to update {note.path}: {e}")
                    metrics.errors.append({"path": note.path, "error": str(e)})
                    metrics.notes_failed += 1

            metrics.durations["apply_tags"] = (datetime.now() - apply_start).total_seconds()
            logger.info(f"✓ Updated {updated_count} notes")

            if not dry_run:
                logger.info(f"✓ Changes logged to {changes_log_path}")
    else:
        logger.info("\n[2/4] Skipping auto-tagging")

    # Step 4: Sync to Archon (if configured)
    sync_report = {}
    # Allow DB sync even when avoiding file writes (sync_to_db_only)
    if (not dry_run) or sync_to_db_only:
        logger.info("\n[4/4] Syncing to Archon...")
        try:
            supabase = get_supabase_client()

            embedding_service = None
            if create_embeddings:
                from src.server.services.prp_service import PRPService

                embedding_service = PRPService(supabase)

            sync_service = ArchonMemorySync(supabase, embedding_service)
            sync_report = await sync_service.sync_vault_index(index, create_embeddings=create_embeddings)

            logger.info(f"✓ Synced {sync_report.get('synced_notes', 0)} notes to Archon")

        except Exception as e:
            logger.warning(f"Archon sync failed: {e}")
            sync_report = {"error": str(e)}
            metrics.errors.append({"component": "archon_sync", "error": str(e)})

    # Create index note
    if not sync_to_db_only and not dry_run:
        logger.info("\nCreating index note...")
        index_note_path = tools.create_index_note(index)
        logger.info(f"✓ Created {index_note_path}")
    else:
        index_note_path = None

    # Save metrics
    metrics_path = artifacts_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics.to_dict(), indent=2))
    logger.info(f"✓ Saved metrics to {metrics_path}")

    # Git commit (optional)
    if git_commit and not dry_run and tag_suggestions:
        logger.info("\nCreating git commit...")
        try:
            git_dir = Path(vault_path) / ".git"
            if git_dir.exists():
                subprocess.run(["git", "-C", vault_path, "add", "."], check=True)

                commit_msg = f"""Obsidian sync: {datetime.now().strftime('%Y-%m-%d')}

Tagged {len(tag_suggestions)} notes
Run ID: {run_id}

🤖 Generated with Archon Orchestration
"""
                subprocess.run(["git", "-C", vault_path, "commit", "-m", commit_msg], check=True)

                logger.info("✓ Git commit created")
            else:
                logger.warning("No git repository found in vault")
        except Exception as e:
            logger.warning(f"Git commit failed: {e}")
            metrics.errors.append({"component": "git", "error": str(e)})

    # Final report
    report = {
        "run_id": run_id,
        "vault_path": vault_path,
        "config": {
            "auto_tag": auto_tag,
            "create_embeddings": create_embeddings,
            "concurrency": concurrency,
            "shard_size": shard_size,
            "dry_run": dry_run,
        },
        "results": {
            "notes_scanned": metrics.notes_scanned,
            "notes_processed": metrics.notes_processed,
            "notes_skipped_unchanged": metrics.notes_skipped_unchanged,
            "notes_skipped_rules": metrics.notes_skipped_rules,
            "notes_failed": metrics.notes_failed,
            "tags_applied": metrics.tags_applied,
        },
        "artifacts": {
            "vault_index": str(index_path),
            "tag_suggestions": str(artifacts_dir / "tag_suggestions.json") if tag_suggestions else None,
            "changes_log": str(changes_log_path) if tag_suggestions else None,
            "metrics": str(metrics_path),
            "index_note": str(index_note_path) if index_note_path else None,
        },
        "metrics": metrics.to_dict(),
        "archon_sync": sync_report,
    }

    # Save report
    report_path = artifacts_dir / "manifest.json"
    report_path.write_text(json.dumps(report, indent=2))

    # Add manifest path to report
    report["artifacts"]["manifest"] = str(report_path)

    logger.info("\n=== Orchestration Complete ===")
    logger.info(f"Processed: {metrics.notes_processed}/{metrics.notes_scanned} notes")
    logger.info(f"Duration: {metrics.to_dict()['duration_s']:.1f}s")
    logger.info(f"Artifacts: {artifacts_dir}")
    logger.info(f"Manifest: {report_path}")

    return report


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Production Obsidian orchestration")
    parser.add_argument("--vault", type=str, default=os.getenv("OBSIDIAN_VAULT"), help="Vault path")
    parser.add_argument("--auto-tag", action="store_true", help="Auto-tag with Ollama")
    parser.add_argument("--create-embeddings", action="store_true", help="Create embeddings")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent Ollama calls")
    parser.add_argument("--shard-size", type=int, default=2000, help="Shard size for processing")
    parser.add_argument("--no-resume", action="store_true", help="Don't resume from state")
    parser.add_argument("--state-file", type=str, default="sync_state.json", help="State file path")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    parser.add_argument("--git-commit", action="store_true", help="Create git commit")
    parser.add_argument("--sync-to-db", action="store_true", help="Sync to DB only (no vault writes)")

    args = parser.parse_args()

    if not args.vault:
        logger.error("Vault path required. Use --vault or set OBSIDIAN_VAULT")
        sys.exit(1)

    vault_path = Path(args.vault)
    if not vault_path.exists():
        logger.error(f"Vault not found: {vault_path}")
        sys.exit(1)

    try:
        report = await run_production_sync(
            str(vault_path),
            auto_tag=args.auto_tag,
            create_embeddings=args.create_embeddings,
            concurrency=args.concurrency,
            shard_size=args.shard_size,
            resume=not args.no_resume,
            state_file=args.state_file,
            dry_run=args.dry_run,
            git_commit=args.git_commit,
            sync_to_db_only=args.sync_to_db,
        )

        logger.info(f"\n✓ Success! See {report['artifacts']['manifest']}")

    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Interrupted by user. State saved - run with --resume to continue.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n\n❌ Orchestration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
