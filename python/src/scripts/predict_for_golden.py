#!/usr/bin/env python3
"""
Predict tags for golden set notes (read-only, no vault modifications).

Generates predictions using Ollama for QA evaluation against golden_set_archon.json.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from pydantic import BaseModel

# Setup path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "python"))

from src.agents.ollama_client import OllamaClient
from src.agents.obsidian_tools_production import ObsidianToolsProduction

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def predict_for_note(
    tools: ObsidianToolsProduction,
    ollama: OllamaClient,
    vault_path: Path,
    note_rel_path: str,
    model: str,
) -> dict[str, str] | None:
    """
    Generate tag predictions for a single note.

    Args:
        tools: ObsidianToolsProduction instance
        ollama: OllamaClient instance
        vault_path: Path to vault
        note_rel_path: Relative path to note in vault
        model: Ollama model name

    Returns:
        Predictions dict with area, service, status or None on error
    """
    note_path = vault_path / note_rel_path

    if not note_path.exists() or note_path.suffix.lower() != ".md":
        logger.warning(f"Note not found or invalid: {note_rel_path}")
        return None

    try:
        # Read note content (no modifications)
        content = note_path.read_text(encoding="utf-8")

        # Truncate if too long (keep first 120K chars for context)
        if len(content) > 120000:
            content = content[:120000] + "\n\n[... truncated ...]"

        # Generate prediction using Ollama
        prompt = f"""Analyze this Obsidian note and suggest metadata tags.

Return JSON with these keys:
- area: primary topic area (e.g., "AI", "Architecture", "DevOps", "Business")
- service: specific service/tool if applicable (e.g., "FastAPI", "Docker", "Postgres")
- status: note status (e.g., "active", "archived", "draft", "complete")

Only return valid JSON, no other text.

--- NOTE START ---
{content}
--- NOTE END ---"""

        class PredictedTags(BaseModel):
            area: str | None = ""
            service: str | None = ""
            status: str | None = ""

        result = await ollama.generate(model, prompt=prompt, json_schema=PredictedTags)
        if isinstance(result, dict):
            return {
                "area": result.get("area", "") or "",
                "service": result.get("service", "") or "",
                "status": result.get("status", "") or "",
            }
        else:
            # Fallback: best-effort parse
            try:
                parsed = json.loads(str(result))
                return {
                    "area": parsed.get("area", ""),
                    "service": parsed.get("service", ""),
                    "status": parsed.get("status", ""),
                }
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to parse JSON for {note_rel_path}: {e}")
                return {"area": "", "service": "", "status": ""}

    except Exception as e:
        logger.error(f"Failed to predict for {note_rel_path}: {e}")
        return None


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate predictions for golden set (read-only)")
    parser.add_argument("--vault", type=str, required=True, help="Vault path")
    parser.add_argument("--golden", type=str, required=True, help="Golden set JSON path")
    parser.add_argument("--model", type=str, default="qwen2.5:3b", help="Ollama model")
    parser.add_argument("--out", type=str, default="artifacts/predictions_golden.json", help="Output path")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent predictions")
    parser.add_argument("--resume", action="store_true", help="Resume from existing predictions (skip completed)")
    parser.add_argument("--max-notes", type=int, help="Limit predictions to first N notes (for testing)")
    parser.add_argument("--save-every", type=int, default=50, help="Save intermediate results every N notes")

    args = parser.parse_args()

    vault_path = Path(args.vault)
    golden_path = Path(args.golden)
    output_path = Path(args.out)

    if not vault_path.exists():
        logger.error(f"Vault not found: {vault_path}")
        sys.exit(1)

    if not golden_path.exists():
        logger.error(f"Golden set not found: {golden_path}")
        sys.exit(1)

    # Load golden set
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    logger.info(f"Loaded golden set: {len(golden)} notes")

    # Initialize services
    tools = ObsidianToolsProduction(str(vault_path))
    ollama = OllamaClient(os.environ.get("OLLAMA_HOST", "http://localhost:11434"))

    # Verify model available
    try:
        models = await ollama.list_models()
        if not any(m.name.startswith(args.model) for m in models):
            logger.error(f"Model not found: {args.model}")
            logger.info(f"Available models: {[m.name for m in models]}")
            sys.exit(1)
        logger.info(f"Using model: {args.model}")
    except Exception as e:
        logger.error(f"Failed to connect to Ollama: {e}")
        sys.exit(1)

    # Load existing predictions if resuming
    predictions = {}
    if args.resume and output_path.exists():
        try:
            predictions = json.loads(output_path.read_text(encoding="utf-8"))
            logger.info(f"Loaded {len(predictions)} existing predictions (resume mode)")
        except Exception as e:
            logger.warning(f"Failed to load existing predictions: {e}")
            predictions = {}

    # Filter note paths
    note_paths = [k for k in golden.keys() if not str(k).startswith("_")]

    # Skip already-predicted notes if resuming
    if args.resume:
        remaining_paths = [p for p in note_paths if p not in predictions]
        logger.info(f"Skipping {len(note_paths) - len(remaining_paths)} already-predicted notes")
        note_paths = remaining_paths

    # Limit to max_notes if specified
    if args.max_notes:
        note_paths = note_paths[:args.max_notes]
        logger.info(f"Limited to first {len(note_paths)} notes (--max-notes={args.max_notes})")

    if not note_paths:
        logger.info("No notes to process")
        return

    # Generate predictions with progress tracking
    semaphore = asyncio.Semaphore(args.concurrency)
    completed = 0
    failed = 0

    async def predict_with_semaphore(note_path: str):
        nonlocal completed, failed
        async with semaphore:
            result = await predict_for_note(tools, ollama, vault_path, note_path, args.model)
            if result:
                completed += 1
            else:
                failed += 1

            if (completed + failed) % 10 == 0:
                logger.info(f"Progress: {completed + failed}/{len(note_paths)} ({completed} ok, {failed} failed)")

            return note_path, result

    logger.info(f"Generating predictions for {len(note_paths)} notes (concurrency={args.concurrency})...")

    # Process in batches for incremental saving
    batch_size = args.save_every
    for batch_start in range(0, len(note_paths), batch_size):
        batch_end = min(batch_start + batch_size, len(note_paths))
        batch_paths = note_paths[batch_start:batch_end]

        logger.info(f"Processing batch {batch_start//batch_size + 1} ({batch_start+1}-{batch_end}/{len(note_paths)})")

        tasks = [predict_with_semaphore(note_path) for note_path in batch_paths]
        results = await asyncio.gather(*tasks)

        for note_path, prediction in results:
            if prediction:
                predictions[note_path] = prediction

        # Save after each batch
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(predictions, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"✓ Saved {len(predictions)} predictions to {output_path}")

    logger.info(f"✓ Final: {len(predictions)} predictions ({completed} new, {failed} failed)")
    logger.info(f"  Coverage: {len(predictions)}/{len(golden)} ({100*len(predictions)/len(golden):.1f}%)")


if __name__ == "__main__":
    asyncio.run(main())
