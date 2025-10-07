#!/usr/bin/env python3
"""
APS Data Exchange - Fetch Elements

Pulls Revit model data from Autodesk Platform Services Data Exchange API
and flattens it into JSONL format for downstream processing.

Usage:
    export APS_ACCESS_TOKEN="your_token"
    export APS_EXCHANGE_ID="your_exchange_id"
    export BIM_FLAT_JSONL="./out/elements.jsonl"  # optional
    python -m src.scripts.bim.aps_fetch_elements
"""

import json
import logging
import os
import sys
from pathlib import Path

import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration from environment
TOKEN = os.environ.get("APS_ACCESS_TOKEN")
EXCHANGE_ID = os.environ.get("APS_EXCHANGE_ID")
ENDPOINT = "https://developer.api.autodesk.com/datacore/v1/graphql"

GRAPHQL_QUERY = """
query GetExchange($id: String!, $after: String) {
  exchange(exchangeId: $id) {
    id
    name
    elements(pagination: { pageSize: 500, after: $after }) {
      results {
        id
        name
        properties { results { name value } }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


def validate_config():
    """Validate required configuration."""
    if not TOKEN:
        logger.error("APS_ACCESS_TOKEN environment variable not set")
        sys.exit(1)
    if not EXCHANGE_ID:
        logger.error("APS_EXCHANGE_ID environment variable not set")
        sys.exit(1)


def fetch_page(after=None):
    """
    Fetch one page of elements from APS Data Exchange.

    Args:
        after: Cursor for pagination

    Returns:
        Dict with elements and pagination info

    Raises:
        requests.HTTPError: If API request fails
    """
    variables = {"id": EXCHANGE_ID, "after": after}

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        ENDPOINT,
        json={"query": GRAPHQL_QUERY, "variables": variables},
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        logger.error(f"GraphQL errors: {data['errors']}")
        raise Exception(f"GraphQL query failed: {data['errors']}")

    return data["data"]["exchange"]["elements"]


def flatten_element(elem):
    """
    Flatten APS element into normalized structure.

    Args:
        elem: Raw element from APS API

    Returns:
        Flattened dict with uid, category, family, type, level, system, params
    """
    # Extract properties into a dict
    props_raw = elem.get("properties", {}).get("results", [])
    props = {p["name"]: p["value"] for p in props_raw}

    return {
        "uid": elem["id"],
        "name": elem.get("name"),
        "category": props.get("Category") or props.get("Category Name"),
        "family": props.get("Family"),
        "type": props.get("Type"),
        "level": props.get("Level"),
        "system": props.get("System"),
        "params": props,  # Keep all properties for detailed analysis
    }


def main():
    """Main execution function."""
    validate_config()

    # Output path
    out_path = Path(os.environ.get("BIM_FLAT_JSONL", "./out/elements.jsonl"))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Fetching elements from exchange: {EXCHANGE_ID}")
    logger.info(f"Output path: {out_path}")

    cursor = None
    total_count = 0
    page_count = 0

    with out_path.open("w", encoding="utf-8") as f:
        while True:
            try:
                logger.info(f"Fetching page {page_count + 1} (cursor: {cursor or 'start'})")
                page_data = fetch_page(after=cursor)

                # Process and write elements
                for elem in page_data["results"]:
                    flattened = flatten_element(elem)
                    f.write(json.dumps(flattened) + "\n")
                    total_count += 1

                page_count += 1

                # Check for next page
                if not page_data["pageInfo"]["hasNextPage"]:
                    break

                cursor = page_data["pageInfo"]["endCursor"]

            except requests.HTTPError as e:
                logger.error(f"HTTP error fetching data: {e}")
                logger.error(f"Response: {e.response.text if e.response else 'No response'}")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Error processing page: {e}")
                sys.exit(1)

    logger.info("=" * 60)
    logger.info("Fetch complete!")
    logger.info(f"  Total elements: {total_count}")
    logger.info(f"  Pages fetched: {page_count}")
    logger.info(f"  Output file: {out_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
