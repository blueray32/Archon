#!/usr/bin/env python3
"""
PRP Embedding Sync Script

Indexes PRPs and documentation files by creating embeddings and storing them in the database.
Run this script whenever you add or update PRP files.

Usage:
    python -m src.scripts.prp_embed_sync
    # or
    uv run python -m src.scripts.prp_embed_sync
"""

import asyncio
import glob
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from supabase import create_client

from src.server.services.prp_service import PRPService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def index_files(prp_service: PRPService, pattern: str, kind: str, base_path: str = ".") -> int:
    """
    Index files matching a glob pattern.

    Args:
        prp_service: PRPService instance
        pattern: Glob pattern for files
        kind: Document kind ('prp', 'doc', 'persona')
        base_path: Base path for glob search

    Returns:
        Number of files indexed
    """
    files = glob.glob(os.path.join(base_path, pattern), recursive=True)
    count = 0

    for file_path in files:
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Extract title from filename
            title = Path(file_path).stem.replace("_", " ").replace("-", " ").title()

            # Upsert document
            result = await prp_service.upsert_prp_doc(kind=kind, path=file_path, content=content, title=title)

            if result:
                logger.info(f"✓ Indexed {kind}: {file_path}")
                count += 1
            else:
                logger.warning(f"✗ Failed to index {kind}: {file_path}")

        except Exception as e:
            logger.error(f"✗ Error processing {file_path}: {e}")

    return count


async def main():
    """Main execution function."""
    # Check for required environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not supabase_url or not supabase_key:
        logger.error("Missing required environment variables: SUPABASE_URL, SUPABASE_SERVICE_KEY")
        sys.exit(1)

    if not openai_key:
        logger.error("Missing OPENAI_API_KEY - required for embedding generation")
        sys.exit(1)

    # Initialize Supabase client
    supabase = create_client(supabase_url, supabase_key)

    # Initialize PRP service
    prp_service = PRPService(supabase_client=supabase, openai_api_key=openai_key)

    logger.info("Starting PRP embedding sync...")

    # Get project root (assumes script is in python/src/scripts/)
    project_root = Path(__file__).parent.parent.parent.parent

    # Index PRPs
    logger.info("Indexing PRP files...")
    prp_count = await index_files(
        prp_service, pattern="PRPs/**/*.prp.md", kind="prp", base_path=str(project_root)
    )

    # Index documentation
    logger.info("Indexing documentation files...")
    doc_count = await index_files(prp_service, pattern="docs/**/*.md", kind="doc", base_path=str(project_root))

    # Index personas (YAML files)
    logger.info("Indexing persona files...")
    persona_count = await index_files(
        prp_service, pattern="personas/**/*.yaml", kind="persona", base_path=str(project_root)
    )

    # Summary
    total = prp_count + doc_count + persona_count
    logger.info("=" * 60)
    logger.info(f"Embedding sync complete!")
    logger.info(f"  PRPs indexed: {prp_count}")
    logger.info(f"  Docs indexed: {doc_count}")
    logger.info(f"  Personas indexed: {persona_count}")
    logger.info(f"  Total: {total}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())