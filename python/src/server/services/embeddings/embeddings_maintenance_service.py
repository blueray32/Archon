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


async def _fetch_missing_rows(client, table: str, limit: int, source_id: str | None):
    sel = client.table(table).select("id,content")
    sel = sel.filter("embedding", "is", "null").limit(limit)
    if source_id:
        sel = sel.eq("source_id", source_id)
    res = sel.execute()
    return res.data or []


async def run_embeddings_backfill_scheduler(stop_event: asyncio.Event | None = None):
    """Optional scheduler to backfill missing embeddings conservatively.

    Controlled by environment variables (all optional):
      - EMBEDDINGS_AUTOBACKFILL_INTERVAL_MIN (default: 1440, i.e. daily)
      - EMBEDDINGS_AUTOBACKFILL_LIMIT (default: 200)
      - EMBEDDINGS_AUTOBACKFILL_BATCH_SIZE (default: 50)
      - EMBEDDINGS_AUTOBACKFILL_TABLES (default: "pages,code_examples")
      - EMBEDDINGS_AUTOBACKFILL_SOURCE_ID (default: empty, i.e., all)
      - EMBEDDINGS_AUTOBACKFILL_DRY_RUN (default: true)
    """
    try:
        interval_min = float(os.getenv("EMBEDDINGS_AUTOBACKFILL_INTERVAL_MIN", "1440"))
    except Exception:
        interval_min = 1440.0

    if interval_min < 5:
        interval_min = 5.0

    try:
        limit = int(os.getenv("EMBEDDINGS_AUTOBACKFILL_LIMIT", "200"))
    except Exception:
        limit = 200
    try:
        batch_size = int(os.getenv("EMBEDDINGS_AUTOBACKFILL_BATCH_SIZE", "50"))
    except Exception:
        batch_size = 50
    tables_env = os.getenv("EMBEDDINGS_AUTOBACKFILL_TABLES", "pages,code_examples")
    tables = [t.strip() for t in tables_env.split(",") if t.strip() in ("pages", "code_examples")]
    if not tables:
        tables = ["pages", "code_examples"]
    source_id = os.getenv("EMBEDDINGS_AUTOBACKFILL_SOURCE_ID", "").strip() or None
    dry_run = os.getenv("EMBEDDINGS_AUTOBACKFILL_DRY_RUN", "true").lower() in ("true", "1", "yes", "on")

    logger.info(
        "Starting embeddings backfill scheduler | interval_min=%.1f, limit=%s, batch=%s, tables=%s, dry_run=%s",
        interval_min,
        limit,
        batch_size,
        ",".join(tables),
        dry_run,
    )

    from .embedding_service import create_embeddings_batch  # lazy import

    try:
        client = get_supabase_client()
        table_map = {"pages": "archon_crawled_pages", "code_examples": "archon_code_examples"}

        while True:
            run_summary: dict[str, Any] = {}

            for key in tables:
                table = table_map[key]
                updated = 0
                failed = 0

                try:
                    rows = await _fetch_missing_rows(client, table, limit, source_id)
                    if not rows:
                        run_summary[key] = {"processed": 0, "updated": 0, "failed": 0}
                        continue

                    # Create embeddings in batches
                    for i in range(0, len(rows), batch_size):
                        batch = rows[i : i + batch_size]
                        texts = [(r.get("content") or "").strip() for r in batch]
                        # Skip empty-only batches entirely
                        nonempty_pairs = [(r, t) for r, t in zip(batch, texts) if t]
                        if not nonempty_pairs:
                            continue
                        ordered_rows = [r for r, _ in nonempty_pairs]
                        ordered_texts = [t for _, t in nonempty_pairs]

                        try:
                            result = await create_embeddings_batch(ordered_texts)
                        except Exception as e:
                            logger.error("Batch embed failed: %s", e, exc_info=True)
                            failed += len(ordered_rows)
                            continue

                        # Update successful ones only
                        idx = 0
                        for emb in result.embeddings:
                            row = ordered_rows[idx]
                            idx += 1
                            if not dry_run:
                                try:
                                    client.table(table).update({"embedding": emb}).eq("id", row["id"]).execute()
                                    updated += 1
                                except Exception as ue:
                                    failed += 1
                                    logger.error("DB update failed id=%s: %s", row.get("id"), ue, exc_info=True)

                        # Count embedding creation failures
                        failed += len(result.failed_items or [])

                    run_summary[key] = {
                        "processed": len(rows),
                        "updated": updated,
                        "failed": failed,
                    }
                except Exception as e:
                    logger.error("Backfill pass failed for %s: %s", table, e, exc_info=True)
                    run_summary[key] = {"error": str(e)}

            logger.info("Embeddings backfill pass done | dry_run=%s | summary=%s", dry_run, run_summary)

            if stop_event and stop_event.is_set():
                break

            await asyncio.sleep(interval_min * 60.0)

    except asyncio.CancelledError:
        logger.info("Embeddings backfill scheduler cancelled")
    except Exception as e:
        logger.error("Embeddings backfill scheduler error: %s", e, exc_info=True)
    finally:
        logger.info("Embeddings backfill scheduler stopped")

