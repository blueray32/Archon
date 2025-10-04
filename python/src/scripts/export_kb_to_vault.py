"""
Export Archon knowledge base to a local Obsidian vault.

Writes Markdown files for sources, crawled pages (reconstructed per-URL),
and code examples under `${OBSIDIAN_VAULT}/Archon/Knowledge/`.

Usage:
  OBSIDIAN_VAULT="/Users/you/Documents/ArchonVault" uv run python -m src.scripts.export_kb_to_vault

Environment variables required:
  - SUPABASE_URL
  - SUPABASE_SERVICE_KEY (service_role key)
  - OBSIDIAN_VAULT (absolute path)

Behavior:
  - Fails fast if required env vars are missing or invalid.
  - Skips individual items that fail to export but continues the batch, logging details.
  - Never writes partial/corrupt content: only writes files once full content is prepared.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from supabase import Client

# Reuse existing client factory and logging helpers
from src.server.services.client_manager import get_supabase_client
from src.server.config.logfire_config import get_logger


logger = get_logger(__name__)


@dataclass
class ExportTarget:
    root: Path
    knowledge_dir: Path


def _sanitize_name(name: str) -> str:
    """Return a safe filesystem name.

    Keeps alphanumerics, dash and underscore; collapses other chars to single underscore.
    """
    name = name.strip() or "untitled"
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_\-]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name[:120]


def _ensure_export_target(base_path: str | None) -> ExportTarget:
    vault = base_path or os.getenv("OBSIDIAN_VAULT")
    if not vault:
        raise RuntimeError(
            "OBSIDIAN_VAULT not set. Set OBSIDIAN_VAULT=/path/to/ObsidianVault or pass --target."
        )

    root = Path(vault).expanduser().resolve()
    if not root.exists():
        raise RuntimeError(f"Vault path does not exist: {root}")
    if not root.is_dir():
        raise RuntimeError(f"Vault path is not a directory: {root}")

    knowledge_dir = root / "Archon" / "Knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    return ExportTarget(root=root, knowledge_dir=knowledge_dir)


def _fetch_sources(client: Client) -> list[dict[str, Any]]:
    result = client.from_("archon_sources").select("*").order("updated_at", desc=False).execute()
    if getattr(result, "error", None):
        raise RuntimeError(f"Supabase error fetching sources: {result.error}")
    return result.data or []


def _filter_sources(
    sources: list[dict[str, Any]],
    source_ids: list[str] | None = None,
    tags: list[str] | None = None,
    knowledge_type: str | None = None,
    updated_since: str | None = None,
) -> list[dict[str, Any]]:
    """Filter sources in-memory according to provided criteria.

    This avoids DB-specific JSONB filter syntax and remains robust across environments.
    """
    filtered = sources

    if source_ids:
        sid_set = {s.strip() for s in source_ids if s and s.strip()}
        filtered = [s for s in filtered if (s.get("source_id") or "") in sid_set]

    if knowledge_type:
        kt = knowledge_type.strip().lower()
        def _kt_match(src: dict[str, Any]) -> bool:
            meta = src.get("metadata") or {}
            val = (meta.get("knowledge_type") or "").lower()
            return val == kt
        filtered = [s for s in filtered if _kt_match(s)]

    if tags:
        tag_set = {t.strip().lower() for t in tags if t and t.strip()}
        def _has_tags(src: dict[str, Any]) -> bool:
            meta = src.get("metadata") or {}
            arr = meta.get("tags") or []
            arr_norm = {str(x).strip().lower() for x in arr}
            return bool(tag_set.intersection(arr_norm))
        filtered = [s for s in filtered if _has_tags(s)]

    if updated_since:
        try:
            from datetime import datetime
            import dateutil.parser  # type: ignore
            threshold = dateutil.parser.isoparse(updated_since)
        except Exception:
            # Try basic parse without dateutil
            try:
                threshold = datetime.fromisoformat(updated_since)
            except Exception:
                threshold = None
        if threshold is not None:
            def _updated_after(src: dict[str, Any]) -> bool:
                val = src.get("updated_at")
                if not val:
                    return False
                try:
                    dt = dateutil.parser.isoparse(val)  # type: ignore
                except Exception:
                    try:
                        dt = datetime.fromisoformat(val)
                    except Exception:
                        return False
                return dt >= threshold
            filtered = [s for s in filtered if _updated_after(s)]

    return filtered


def _fetch_pages_for_source(client: Client, source_id: str) -> list[dict[str, Any]]:
    result = (
        client.from_("archon_crawled_pages")
        .select("url, chunk_number, content, metadata")
        .eq("source_id", source_id)
        .order("url", desc=False)
        .order("chunk_number", desc=False)
        .execute()
    )
    if getattr(result, "error", None):
        raise RuntimeError(f"Supabase error fetching pages for {source_id}: {result.error}")
    return result.data or []


def _fetch_code_examples_for_source(client: Client, source_id: str) -> list[dict[str, Any]]:
    result = (
        client.from_("archon_code_examples")
        .select("url, chunk_number, content, summary, metadata")
        .eq("source_id", source_id)
        .order("url", desc=False)
        .order("chunk_number", desc=False)
        .execute()
    )
    if getattr(result, "error", None):
        raise RuntimeError(f"Supabase error fetching code examples for {source_id}: {result.error}")
    return result.data or []


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _yaml_frontmatter(obj: dict[str, Any]) -> str:
    def _serialize(v: Any) -> str:
        if isinstance(v, (str, int, float)):
            # Quote strings that contain special chars
            if isinstance(v, str) and (":" in v or "#" in v or v.strip() != v):
                return json.dumps(v)
            return str(v)
        if v is True:
            return "true"
        if v is False:
            return "false"
        if v is None:
            return "null"
        if isinstance(v, (list, tuple)):
            return f"[{', '.join(_serialize(i) for i in v)}]"
        if isinstance(v, dict):
            lines = []
            for k, vv in v.items():
                lines.append(f"  {k}: {_serialize(vv)}")
            return "\n" + "\n".join(lines)
        return json.dumps(v)

    lines = ["---"]
    for k, v in obj.items():
        if isinstance(v, dict):
            lines.append(f"{k}:{_serialize(v)}")
        else:
            lines.append(f"{k}: {_serialize(v)}")
    lines.append("---")
    return "\n".join(lines)


def export_source(client: Client, tgt: ExportTarget, source: dict[str, Any]) -> dict[str, Any]:
    source_id = source.get("source_id") or ""
    title = source.get("title") or source.get("source_display_name") or source_id
    if not source_id:
        raise RuntimeError("source_id missing in source record")

    folder_name = _sanitize_name(source.get("source_display_name") or title or source_id)
    source_dir = tgt.knowledge_dir / folder_name
    pages_dir = source_dir / "pages"
    examples_dir = source_dir / "code_examples"
    source_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)
    examples_dir.mkdir(parents=True, exist_ok=True)

    # index.md with metadata + summary
    front = {
        "title": title,
        "source_id": source_id,
        "source_url": source.get("source_url"),
        "display_name": source.get("source_display_name"),
        "word_count": source.get("total_word_count", 0),
        "metadata": source.get("metadata") or {},
        "created_at": source.get("created_at"),
        "updated_at": source.get("updated_at"),
        "exported_at": datetime.utcnow().isoformat() + "Z",
    }
    body = source.get("summary") or ""
    index_md = f"{_yaml_frontmatter(front)}\n\n# {title}\n\n{body}\n"
    _write_atomic(source_dir / "index.md", index_md)

    # Pages: reconstruct by URL
    try:
        rows = _fetch_pages_for_source(client, source_id)
    except Exception as e:
        logger.error(f"Failed to fetch pages for {source_id}: {e}", exc_info=True)
        rows = []

    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        url = (r.get("url") or "").strip()
        content = (r.get("content") or "").strip()
        if not url or not content:
            # Skip corrupted/empty rows
            continue
        by_url[url].append(r)

    page_count = 0
    for url, chunks in by_url.items():
        try:
            chunks.sort(key=lambda x: int(x.get("chunk_number") or 0))
            full_content = "\n\n".join(ch.get("content") or "" for ch in chunks)
            if not full_content.strip():
                continue
            url_stub = _sanitize_name(url.split("//", 1)[-1])
            page_front = {
                "url": url,
                "source_id": source_id,
                "chunk_count": len(chunks),
            }
            page_md = f"{_yaml_frontmatter(page_front)}\n\n# {url}\n\n{full_content}\n"
            _write_atomic(pages_dir / f"{url_stub}.md", page_md)
            page_count += 1
        except Exception as e:
            logger.error(f"Failed to export page for source={source_id} url={url}: {e}", exc_info=True)
            continue

    # Code examples
    example_count = 0
    try:
        examples = _fetch_code_examples_for_source(client, source_id)
    except Exception as e:
        logger.error(f"Failed to fetch code examples for {source_id}: {e}", exc_info=True)
        examples = []

    for ex in examples:
        try:
            url = (ex.get("url") or "").strip()
            content = ex.get("content") or ""
            summary = ex.get("summary") or ""
            if not content.strip():
                continue
            url_stub = _sanitize_name(url.split("//", 1)[-1] if url else f"example_{ex.get('chunk_number', 0)}")
            ex_front = {
                "url": url or None,
                "source_id": source_id,
                "summary": summary,
            }
            ex_md = f"{_yaml_frontmatter(ex_front)}\n\n# Code Example\n\n{summary}\n\n```\n{content}\n```\n"
            _write_atomic(examples_dir / f"{url_stub}.md", ex_md)
            example_count += 1
        except Exception as e:
            logger.error(
                f"Failed to export code example for source={source_id}, url={ex.get('url')}: {e}",
                exc_info=True,
            )
            continue

    return {"pages": page_count, "examples": example_count}


def run_export(
    client: Client,
    vault_path: str | None = None,
    progress_hook: callable | None = None,
    *,
    source_ids: list[str] | None = None,
    tags: list[str] | None = None,
    knowledge_type: str | None = None,
    updated_since: str | None = None,
) -> dict[str, Any]:
    """Run knowledge base export.

    Args:
        client: Supabase client
        vault_path: Optional override for OBSIDIAN_VAULT
        progress_hook: Optional callable(total:int, done:int, last_status:str)

    Returns:
        Summary dict with counts and failures
    """
    target = _ensure_export_target(vault_path)

    sources = _fetch_sources(client)
    if source_ids or tags or knowledge_type or updated_since:
        sources = _filter_sources(
            sources,
            source_ids=source_ids,
            tags=tags,
            knowledge_type=knowledge_type,
            updated_since=updated_since,
        )
    total = len(sources)
    if total == 0:
        return {"exported": 0, "failed": 0, "failures": []}

    successes = 0
    failures: list[dict[str, str]] = []

    for i, src in enumerate(sources, start=1):
        sid = src.get("source_id") or ""
        try:
            stats = export_source(client, target, src)
            successes += 1
            if progress_hook:
                progress_hook(total, i, f"Exported {sid}: pages={stats['pages']}, examples={stats['examples']}")
        except Exception as e:
            msg = str(e)
            logger.error(f"Failed to export source {sid}: {msg}", exc_info=True)
            failures.append({"source_id": sid, "error": msg})
            if progress_hook:
                progress_hook(total, i, f"Failed {sid}: {msg}")

    return {"exported": successes, "failed": len(failures), "failures": failures}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Archon knowledge base to Obsidian vault")
    parser.add_argument("--target", help="Override OBSIDIAN_VAULT path")
    args = parser.parse_args(argv)

    # Fail fast on missing critical configuration
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        logger.error("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in environment")
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY env vars are required", file=sys.stderr)
        return 2

    # Initialize client and run export
    try:
        client = get_supabase_client()
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}", exc_info=True)
        print(f"ERROR: Failed to create Supabase client: {e}", file=sys.stderr)
        return 2

    try:
        # Simple CLI run without progress hook
        summary = run_export(client, args.target)
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        print(f"ERROR: Export failed: {e}", file=sys.stderr)
        return 2

    print(
        f"Done. Exported {summary['exported']} sources. Failures: {summary['failed']}"
    )
    if summary.get("failures"):
        print(json.dumps({"failed": summary["failures"]}, indent=2))

    return 0 if summary.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
