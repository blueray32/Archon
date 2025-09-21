"""
Embeddings Maintenance API

Provides endpoints to inspect embedding health and backfill missing embeddings
for crawled pages and code examples.
"""

from dataclasses import dataclass
from time import time
from typing import Any

from fastapi import APIRouter, HTTPException

from ..config.logfire_config import get_logger, safe_span
from ..services.client_manager import get_supabase_client
from ..services.embeddings.embedding_service import create_embeddings_batch

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])

logger = get_logger(__name__)


@dataclass
class TableHealth:
    table: str
    total: int
    missing: int
    with_embedding: int


def _count(client, table: str, null_only: bool = False) -> int:
    sel = client.table(table).select("id", count="exact", head=True)
    if null_only:
        # Use PostgREST 'is.null' filter via supabase-py
        sel = sel.filter("embedding", "is", "null")
    res = sel.execute()
    return int(res.count or 0)


@router.get("/health")
async def embeddings_health():
    """Return counts of total rows and missing embeddings per table."""
    with safe_span("embeddings_health"):
        try:
            client = get_supabase_client()
            pages_total = _count(client, "archon_crawled_pages")
            pages_missing = _count(client, "archon_crawled_pages", null_only=True)
            code_total = _count(client, "archon_code_examples")
            code_missing = _count(client, "archon_code_examples", null_only=True)

            pages = TableHealth(
                table="archon_crawled_pages",
                total=pages_total,
                missing=pages_missing,
                with_embedding=max(pages_total - pages_missing, 0),
            ).__dict__
            code = TableHealth(
                table="archon_code_examples",
                total=code_total,
                missing=code_missing,
                with_embedding=max(code_total - code_missing, 0),
            ).__dict__

            return {
                "pages": pages,
                "code_examples": code,
                "summary": {
                    "total": pages_total + code_total,
                    "missing": pages_missing + code_missing,
                    "with_embedding": (pages_total - pages_missing) + (code_total - code_missing),
                },
            }
        except Exception as e:
            logger.error("Embedding health check failed", exc_info=True)
            raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/backfill")
async def embeddings_backfill(request: dict[str, Any]):
    """
    Backfill missing embeddings.

    Request body:
    - tables: ["pages","code_examples"] or "all" (default: all)
    - batch_size: int (default 100)
    - limit: int (default 1000) maximum rows to process per table
    - dry_run: bool (default False) if True, do not write updates
    - source_id: optional str to filter by source_id
    """
    with safe_span("embeddings_backfill") as span:
        start = time()
        try:
            client = get_supabase_client()

            tables_req = request.get("tables", "all")
            if tables_req == "all" or not tables_req:
                tables = ["pages", "code_examples"]
            else:
                tables = list(tables_req)

            batch_size = int(request.get("batch_size", 100))
            limit = int(request.get("limit", 1000))
            dry_run = bool(request.get("dry_run", False))
            source_id = request.get("source_id")

            processed_summary: dict[str, Any] = {}

            async def process_table(table_key: str):
                table = "archon_crawled_pages" if table_key == "pages" else "archon_code_examples"
                text_field = "content"  # both tables use content as primary text
                processed = 0
                updated = 0
                failed = []

                while processed < limit:
                    sel = (
                        client.table(table)
                        .select(f"id,{text_field}")
                        .filter("embedding", "is", "null")
                        .limit(batch_size)
                    )
                    if source_id:
                        sel = sel.eq("source_id", source_id)
                    res = sel.execute()
                    rows = res.data or []
                    if not rows:
                        break

                    texts = [r.get(text_field) or "" for r in rows]

                    # Skip empty texts entirely
                    nonempty_pairs = [(r, t) for r, t in zip(rows, texts) if t.strip()]
                    if not nonempty_pairs:
                        processed += len(rows)
                        continue

                    ordered_rows = [r for r, _ in nonempty_pairs]
                    ordered_texts = [t for _, t in nonempty_pairs]

                    result = await create_embeddings_batch(ordered_texts)

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
                                failed.append({
                                    "id": row["id"],
                                    "error": str(ue),
                                    "stage": "update",
                                })

                    # Record failures from embedding creation
                    for f in result.failed_items:
                        failed.append({
                            "text_preview": f.get("text"),
                            "error": f.get("error"),
                            "error_type": f.get("error_type"),
                            "stage": "embed",
                        })

                    processed += len(rows)
                    if processed >= limit:
                        break

                processed_summary[table_key] = {
                    "processed": processed,
                    "updated": updated,
                    "failed_count": len(failed),
                    "failed": failed[:25],  # trim to avoid huge payloads
                    "dry_run": dry_run,
                }

            # Process selected tables
            for key in tables:
                await process_table(key)

            span.set_attribute("processed_summary", str(processed_summary))

            return {
                "success": True,
                "duration_seconds": round(time() - start, 2),
                "summary": processed_summary,
            }
        except Exception as e:
            logger.error("Embedding backfill failed", exc_info=True)
            raise HTTPException(status_code=500, detail={"error": str(e)})

