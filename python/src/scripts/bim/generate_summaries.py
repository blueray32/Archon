#!/usr/bin/env python3
"""
Generate CSV/Markdown Summaries from JSONL

Converts flattened element data into CSV and Markdown table formats
for use with Docling or manual review.

Usage:
    python -m src.scripts.bim.generate_summaries
"""

import csv
import json
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Main execution function."""
    # Paths
    src = Path(os.environ.get("BIM_FLAT_JSONL", "./out/elements.jsonl"))
    csv_path = Path(os.environ.get("BIM_CSV", "./out/elements.csv"))
    md_path = Path(os.environ.get("BIM_MD", "./out/elements.md"))

    if not src.exists():
        logger.error(f"Source file not found: {src}")
        logger.error("Run aps_fetch_elements.py first to generate elements.jsonl")
        return

    logger.info(f"Reading from: {src}")

    # Read and process JSONL
    rows = []
    with src.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                rec = json.loads(line)
                rows.append(
                    [
                        rec.get("uid", ""),
                        rec.get("category", ""),
                        rec.get("family", ""),
                        rec.get("type", ""),
                        rec.get("level", ""),
                        rec.get("system", ""),
                    ]
                )
            except json.JSONDecodeError as e:
                logger.warning(f"Skipping invalid JSON on line {line_num}: {e}")

    logger.info(f"Processed {len(rows)} elements")

    # Create output directories
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    # Write CSV
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["uid", "category", "family", "type", "level", "system"])
        writer.writerows(rows)

    logger.info(f"Wrote CSV: {csv_path}")

    # Write Markdown
    with md_path.open("w", encoding="utf-8") as f:
        # Header
        f.write("| uid | category | family | type | level | system |\n")
        f.write("|---|---|---|---|---|---|\n")

        # Rows
        for row in rows:
            # Escape pipe characters and handle None values
            escaped = [str(x or "").replace("|", "\\|") for x in row]
            f.write("| " + " | ".join(escaped) + " |\n")

    logger.info(f"Wrote Markdown: {md_path}")

    logger.info("=" * 60)
    logger.info("Summary generation complete!")
    logger.info(f"  Elements: {len(rows)}")
    logger.info(f"  CSV: {csv_path}")
    logger.info(f"  Markdown: {md_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
