#!/usr/bin/env python3
"""
Quick test of orchestration with a small subset of notes.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "python"))

# Load environment variables
from dotenv import load_dotenv
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

from src.agents.obsidian_tools import ObsidianTools
from src.agents.ollama_client import OllamaClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    """Test orchestration with small subset of notes."""
    vault_path = "/Users/ciarancox/Documents/ArchonVault"

    logger.info("=== Quick Orchestration Test ===")

    # Step 1: Scan vault
    logger.info("[1/3] Scanning vault...")
    tools = ObsidianTools(vault_path)
    index = tools.scan_vault()
    logger.info(f"✓ Found {index.notes_count} notes total")

    # Step 2: Test auto-tagging on first 5 notes with content
    logger.info("[2/3] Testing auto-tagging on first 5 notes...")

    # Filter notes with actual content
    notes_with_content = [n for n in index.notes if n.word_count > 10][:5]

    if not notes_with_content:
        logger.warning("No notes with content found")
        return

    logger.info(f"Selected notes for tagging:")
    for note in notes_with_content:
        logger.info(f"  - {note.title} ({note.word_count} words)")

    # Test Ollama connection
    async with OllamaClient() as client:
        healthy = await client.health_check()
        if not healthy:
            logger.error("Ollama not available at http://localhost:11434")
            return

        logger.info("✓ Ollama connected")

        # Auto-tag the notes
        suggestions = await tools.auto_tag_notes(notes_with_content, client, model="qwen2.5:3b")

        logger.info(f"✓ Generated {len(suggestions)} tag suggestions")

        # Display results
        logger.info("[3/3] Tag suggestions:")
        for note_path, tags in suggestions.items():
            logger.info(f"\n  {note_path}:")
            logger.info(f"    area: {tags.get('area', 'N/A')}")
            logger.info(f"    service: {tags.get('service', 'N/A')}")
            logger.info(f"    status: {tags.get('status', 'N/A')}")

    # Save results
    output_file = Path("artifacts/quick_test_results.json")
    output_file.parent.mkdir(exist_ok=True)
    output_file.write_text(json.dumps(suggestions, indent=2))
    logger.info(f"\n✓ Results saved to {output_file}")

    logger.info("\n=== Test Complete ===")
    logger.info(f"Processed {len(suggestions)} notes successfully")


if __name__ == "__main__":
    asyncio.run(main())
