#!/usr/bin/env python3
"""
Golden Set Builder - Sample diverse notes for QA validation

Samples notes by:
- Size (small, medium, large)
- Path depth (root, nested, deep)
- Tags (none, few, many)
- Modification time (recent, old)
- Word count distribution
"""

import argparse
import json
import logging
import random
import sys
from collections import defaultdict
from pathlib import Path

# Setup path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "python"))

from dotenv import load_dotenv

env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

from src.agents.obsidian_tools_production import ObsidianToolsProduction

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def stratify_notes(notes: list, target_count: int = 200) -> list:
    """
    Stratified sampling for diverse golden set.

    Strategies:
    - 25% by size (small: <100 words, medium: 100-500, large: >500)
    - 25% by path depth (shallow, medium, deep)
    - 25% by tags (none, few, many)
    - 25% by recency (recent, medium, old)
    """
    samples = []

    # Filter out notes with no content
    notes_with_content = [n for n in notes if n.word_count > 10]

    if len(notes_with_content) < target_count:
        logger.warning(f"Only {len(notes_with_content)} notes with content, using all")
        return notes_with_content[:target_count]

    # 1. Sample by size
    by_size = defaultdict(list)
    for note in notes_with_content:
        if note.word_count < 100:
            by_size["small"].append(note)
        elif note.word_count < 500:
            by_size["medium"].append(note)
        else:
            by_size["large"].append(note)

    size_samples = []
    size_per_bucket = target_count // 4 // 3  # 25% of target / 3 buckets
    for bucket, bucket_notes in by_size.items():
        if bucket_notes:
            size_samples.extend(random.sample(bucket_notes, min(size_per_bucket, len(bucket_notes))))

    # 2. Sample by path depth
    by_depth = defaultdict(list)
    for note in notes_with_content:
        depth = len(Path(note.path).parts)
        if depth <= 1:
            by_depth["shallow"].append(note)
        elif depth <= 3:
            by_depth["medium"].append(note)
        else:
            by_depth["deep"].append(note)

    depth_samples = []
    depth_per_bucket = target_count // 4 // 3
    for bucket, bucket_notes in by_depth.items():
        if bucket_notes:
            depth_samples.extend(random.sample(bucket_notes, min(depth_per_bucket, len(bucket_notes))))

    # 3. Sample by tags
    by_tags = defaultdict(list)
    for note in notes_with_content:
        tag_count = len(note.tags)
        if tag_count == 0:
            by_tags["none"].append(note)
        elif tag_count <= 3:
            by_tags["few"].append(note)
        else:
            by_tags["many"].append(note)

    tag_samples = []
    tag_per_bucket = target_count // 4 // 3
    for bucket, bucket_notes in by_tags.items():
        if bucket_notes:
            tag_samples.extend(random.sample(bucket_notes, min(tag_per_bucket, len(bucket_notes))))

    # 4. Sample by recency
    sorted_by_time = sorted(notes_with_content, key=lambda n: n.modified or "", reverse=True)
    recency_samples = []
    third = len(sorted_by_time) // 3
    recency_per_bucket = target_count // 4 // 3

    recency_samples.extend(random.sample(sorted_by_time[:third], min(recency_per_bucket, third)))  # Recent
    recency_samples.extend(
        random.sample(sorted_by_time[third : 2 * third], min(recency_per_bucket, third))
    )  # Medium
    recency_samples.extend(random.sample(sorted_by_time[2 * third :], min(recency_per_bucket, len(sorted_by_time) - 2 * third)))  # Old

    # Combine and deduplicate
    all_samples = size_samples + depth_samples + tag_samples + recency_samples
    unique_samples = []
    seen_paths = set()

    for note in all_samples:
        if note.path not in seen_paths:
            unique_samples.append(note)
            seen_paths.add(note.path)

    # If we don't have enough, top up randomly
    if len(unique_samples) < target_count:
        remaining = [n for n in notes_with_content if n.path not in seen_paths]
        if remaining:
            needed = target_count - len(unique_samples)
            unique_samples.extend(random.sample(remaining, min(needed, len(remaining))))

    return unique_samples[:target_count]


def build_golden_set(vault_path: str, output_path: str, count: int = 200, seed: int | None = None):
    """
    Build golden set from vault.

    Args:
        vault_path: Path to vault
        output_path: Output JSON file
        count: Number of notes to sample
        seed: Random seed for reproducibility
    """
    if seed is not None:
        random.seed(seed)

    logger.info(f"Building golden set from {vault_path}")

    # Scan vault
    tools = ObsidianToolsProduction(vault_path)
    index, _ = tools.scan_vault()

    logger.info(f"Scanned {index.notes_count} notes")

    # Stratified sampling
    logger.info(f"Sampling {count} diverse notes...")
    samples = stratify_notes(index.notes, target_count=count)

    logger.info(f"Selected {len(samples)} notes")

    # Build output
    golden_set = {
        "_README": "Golden dataset for QA validation. Manually label each note with correct area/service/status.",
        "_INSTRUCTIONS": "1. Review each note. 2. Assign area (required), service (optional), status (required). 3. Leave service empty (\"\") if not applicable.",
        "_TAG_SCHEMA": {
            "area": [
                "MEP",
                "BIM",
                "Revit",
                "NavisWorks",
                "Spanish",
                "Community",
                "Engineering",
                "Architecture",
                "Construction",
            ],
            "service": ["agents", "crawler", "mcp", "ui", "database", "embedding", "search"],
            "status": ["draft", "review", "published", "archived"],
        },
        "_STATS": {
            "vault_path": vault_path,
            "total_notes": index.notes_count,
            "sampled_notes": len(samples),
            "sample_distribution": {
                "by_size": {
                    "small (<100 words)": len([n for n in samples if n.word_count < 100]),
                    "medium (100-500)": len([n for n in samples if 100 <= n.word_count < 500]),
                    "large (>500)": len([n for n in samples if n.word_count >= 500]),
                },
                "by_tags": {
                    "none": len([n for n in samples if len(n.tags) == 0]),
                    "few (1-3)": len([n for n in samples if 1 <= len(n.tags) <= 3]),
                    "many (>3)": len([n for n in samples if len(n.tags) > 3]),
                },
            },
        },
    }

    # Add samples with context
    for note in samples:
        golden_set[note.path] = {
            "area": "",  # TO FILL
            "service": "",  # TO FILL (or leave empty)
            "status": "",  # TO FILL
            "_context": {
                "title": note.title,
                "word_count": note.word_count,
                "tags": note.tags[:10],
                "headings": note.headings[:5],
            },
        }

    # Save
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(golden_set, indent=2))

    logger.info(f"✓ Golden set saved to {output_path}")
    logger.info(f"✓ Contains {len(samples)} notes to label")
    logger.info("\nNext steps:")
    logger.info(f"1. Open {output_path}")
    logger.info("2. For each note, fill in area/service/status")
    logger.info("3. Use _context hints (title, tags, headings) to decide")
    logger.info("4. Run QA harness after labeling")

    # Show sample
    logger.info("\nSample entries (first 3):")
    for i, note in enumerate(samples[:3]):
        logger.info(f"\n  {i+1}. {note.path}")
        logger.info(f"     Title: {note.title}")
        logger.info(f"     Words: {note.word_count}, Tags: {note.tags[:3]}")
        logger.info(f"     Headings: {note.headings[:2]}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Build golden set for QA")
    parser.add_argument("--vault", type=str, required=True, help="Path to Obsidian vault")
    parser.add_argument("--output", type=str, default="golden_set.json", help="Output file")
    parser.add_argument("--count", type=int, default=200, help="Number of notes to sample")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")

    args = parser.parse_args()

    vault_path = Path(args.vault)
    if not vault_path.exists():
        logger.error(f"Vault not found: {vault_path}")
        sys.exit(1)

    try:
        build_golden_set(str(vault_path), args.output, count=args.count, seed=args.seed)
    except Exception as e:
        logger.error(f"Failed to build golden set: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
