"""
Embeddings Maintenance Service

Periodically logs embedding health (total/missing) to help operators spot gaps.
Optionally can be extended to run automated backfills.
"""

import asyncio
import os
from typing import Any

from ...config.logfire_config import get_logger, safe_span
from ..client_manager import get_supabase_client

logger = get_logger(__name__)


def _count(client, table: str, null_only: bool = False) -> int:
    sel = client.table(table).select("id", count="exact", head=True)
    if null_only:
        sel = sel.filter("embedding", "is", "null")
    res = sel.execute()
    return int(res.count or 0)


async def log_embeddings_health_once() -> dict[str, Any]:
    """Fetch and log current embedding health for both tables."""
    with safe_span("embeddings_health_monitor"):
        try:
            client = get_supabase_client()

            pages_total = _count(client, "archon_crawled_pages")
            pages_missing = _count(client, "archon_crawled_pages", null_only=True)
            code_total = _count(client, "archon_code_examples")
            code_missing = _count(client, "archon_code_examples", null_only=True)

            payload = {
                "pages": {"total": pages_total, "missing": pages_missing},
                "code_examples": {"total": code_total, "missing": code_missing},
                "summary": {
                    "total": pages_total + code_total,
                    "missing": pages_missing + code_missing,
                },
            }

            logger.info(
                "Embeddings health | pages=%s/%s missing | code=%s/%s missing | total_missing=%s",
                pages_missing,
                pages_total,
                code_missing,
                code_total,
                payload["summary"]["missing"],
            )

            return payload
        except Exception as e:
            logger.error("Embeddings health monitor failed: %s", e, exc_info=True)
            return {"error": str(e)}


async def run_embeddings_health_monitor(stop_event: asyncio.Event | None = None):
    """Run a periodic health logger with configurable interval (minutes)."""
    try:
        interval_min = float(os.getenv("EMBEDDINGS_HEALTH_LOG_INTERVAL_MIN", "60"))
    except Exception:
        interval_min = 60.0

    # Ensure a sensible minimum
    if interval_min < 1:
        interval_min = 1.0

    logger.info("Starting embeddings health monitor | interval_min=%.1f", interval_min)

    try:
        while True:
            await log_embeddings_health_once()

            # Support external stop event for clean shutdown
            if stop_event and stop_event.is_set():
                break

            await asyncio.sleep(interval_min * 60.0)
    except asyncio.CancelledError:
        logger.info("Embeddings health monitor cancelled")
    except Exception as e:
        logger.error("Embeddings health monitor error: %s", e, exc_info=True)
    finally:
        logger.info("Embeddings health monitor stopped")

