#!/usr/bin/env python3
"""
Supabase cleanup using the REST API.

Steps:
1. Remove crawled chunks older than RETENTION_DAYS.
2. Cap crawled chunks per source to MAX_CHUNKS_PER_SOURCE (by lowest chunk_number).
3. Trim document versions per (project, field, document) to MAX_VERSIONS_PER_DOC (newest kept).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from itertools import islice
from typing import Dict, Iterable, List, Tuple

import requests
from dotenv import load_dotenv


RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "60"))
MAX_CHUNKS_PER_SOURCE = int(os.getenv("MAX_CHUNKS_PER_SOURCE", "400"))
MAX_VERSIONS_PER_DOC = int(os.getenv("MAX_VERSIONS_PER_DOC", "5"))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "1000"))
ID_BATCH_SIZE = int(os.getenv("ID_BATCH_SIZE", "150"))
MAX_SOURCES = int(os.getenv("MAX_SOURCES", "2000"))
SOURCE_BATCH_SIZE = int(os.getenv("SOURCE_BATCH_SIZE", "100"))
MAX_PRP_DOCS = int(os.getenv("MAX_PRP_DOCS", "2000"))


def chunked(iterable: Iterable[str], size: int) -> Iterable[List[str]]:
    iterator = iter(iterable)
    while True:
        batch = list(islice(iterator, size))
        if not batch:
            break
        yield batch


def env_or_fail(key: str) -> str:
    value = os.getenv(key)
    if not value:
        print(f"❌ Missing required environment variable: {key}", file=sys.stderr)
        sys.exit(1)
    return value


def build_headers(service_key: str, extra: Dict[str, str] | None = None) -> Dict[str, str]:
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Accept-Profile": "public",
        "Prefer": "count=exact",
    }
    if extra:
        headers.update(extra)
    return headers


class SupabaseRequestError(RuntimeError):
    def __init__(self, method: str, path: str, status_code: int, text: str) -> None:
        super().__init__(f"{method} {path} failed ({status_code}): {text}")
        self.status_code = status_code
        self.text = text


def supabase_request(
    method: str,
    base_url: str,
    path: str,
    service_key: str,
    *,
    params: Dict[str, str] | None = None,
    json_body=None,
    range_header: Tuple[int, int] | None = None,
) -> requests.Response:
    url = f"{base_url}/rest/v1/{path}"
    headers = build_headers(service_key)
    if range_header:
        start, end = range_header
        headers["Range"] = f"{start}-{end}"
    response = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=30)
    if response.status_code >= 400:
        raise SupabaseRequestError(method, path, response.status_code, response.text)
    return response


def fetch_range(
    base_url: str,
    path: str,
    service_key: str,
    *,
    params: Dict[str, str] | None = None,
    start: int = 0,
    size: int = PAGE_SIZE,
) -> Tuple[List[Dict], int | None]:
    attempt_size = size

    while True:
        try:
            response = supabase_request(
                "GET",
                base_url,
                path,
                service_key,
                params=params,
                range_header=(start, start + attempt_size - 1),
            )
            break
        except SupabaseRequestError as err:
            if err.status_code >= 500 and attempt_size > 50:
                attempt_size = max(50, attempt_size // 2)
                continue
            raise
    data = response.json()
    total = None
    content_range = response.headers.get("content-range")
    if content_range and "/" in content_range:
        _, total_part = content_range.split("/")
        if total_part != "*":
            total = int(total_part)
    return data, total


def fetch_all_rows(
    base_url: str,
    path: str,
    service_key: str,
    *,
    params: Dict[str, str] | None = None,
) -> List[Dict]:
    results: List[Dict] = []
    start = 0

    while True:
        page, total = fetch_range(
            base_url,
            path,
            service_key,
            params=params,
            start=start,
            size=PAGE_SIZE,
        )
        if not page:
            break
        results.extend(page)
        start += len(page)
        if total is not None and start >= total:
            break
        if len(page) < PAGE_SIZE:
            break

    return results


def delete_where(base_url: str, table: str, service_key: str, params: Dict[str, str]) -> int:
    response = supabase_request("DELETE", base_url, table, service_key, params=params)
    # Supabase returns match count via header
    count_header = response.headers.get("content-range")
    if count_header and "/" in count_header:
        _, total = count_header.split("/")
        try:
            return int(total)
        except ValueError:
            pass
    return 0


def delete_ids(base_url: str, table: str, service_key: str, ids: Iterable[str]) -> int:
    deleted = 0
    for batch in chunked(ids, ID_BATCH_SIZE):
        if not batch:
            continue
        id_list = ",".join(batch)
        params = {"id": f"in.({id_list})"}
        supabase_request("DELETE", base_url, table, service_key, params=params)
        deleted += len(batch)
    return deleted


def prune_crawled_pages(base_url: str, service_key: str) -> Dict[str, int]:
    stats = {"expired": 0, "capped": 0}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()

    stats["expired"] = delete_where(
        base_url,
        "archon_crawled_pages",
        service_key,
        params={"created_at": f"lt.{cutoff}"},
    )

    sources = fetch_all_rows(
        base_url,
        "archon_sources",
        service_key,
        params={"select": "source_id", "order": "source_id"},
    )

    total_sources = len(sources)
    for idx, source in enumerate(sources, start=1):
        source_id = source["source_id"]
        initial_rows, total = fetch_range(
            base_url,
            "archon_crawled_pages",
            service_key,
            params={
                "select": "id,chunk_number",
                "source_id": f"eq.{source_id}",
                "order": "chunk_number",
            },
            size=MAX_CHUNKS_PER_SOURCE + 1,
        )
        if total is None:
            total = len(initial_rows)

        if total <= MAX_CHUNKS_PER_SOURCE:
            continue

        excess_ids = [str(row["id"]) for row in initial_rows[MAX_CHUNKS_PER_SOURCE:]]
        next_start = MAX_CHUNKS_PER_SOURCE + len(excess_ids)

        while next_start < total:
            page_rows, _ = fetch_range(
                base_url,
                "archon_crawled_pages",
                service_key,
                params={
                    "select": "id",
                    "source_id": f"eq.{source_id}",
                    "order": "chunk_number",
                },
                start=next_start,
                size=PAGE_SIZE,
            )
            if not page_rows:
                break
            excess_ids.extend(str(item["id"]) for item in page_rows)
            next_start += len(page_rows)

        stats["capped"] += delete_ids(base_url, "archon_crawled_pages", service_key, excess_ids)

        if idx % 25 == 0 or idx == total_sources:
            print(f"  processed {idx}/{total_sources} sources", flush=True)

    return stats


def prune_document_versions(base_url: str, service_key: str) -> int:
    rows = fetch_all_rows(
        base_url,
        "archon_document_versions",
        service_key,
        params={
            "select": "id,project_id,field_name,document_id,created_at",
            "order": "project_id,field_name,document_id,created_at.desc",
        },
    )

    delete_queue: List[str] = []
    counters: Dict[Tuple, int] = {}

    for row in rows:
        key = (row.get("project_id"), row.get("field_name"), row.get("document_id"))
        counters[key] = counters.get(key, 0) + 1
        if counters[key] > MAX_VERSIONS_PER_DOC:
            delete_queue.append(str(row["id"]))

    return delete_ids(base_url, "archon_document_versions", service_key, delete_queue)


def count_rows(
    base_url: str,
    table: str,
    service_key: str,
    column: str = "id",
    params: Dict[str, str] | None = None,
) -> int:
    request_params = {"select": column, "limit": "1"}
    if params:
        request_params.update(params)
    response = supabase_request(
        "GET",
        base_url,
        table,
        service_key,
        params=request_params,
    )
    content_range = response.headers.get("content-range") or response.headers.get("Content-Range")
    if not content_range or "/" not in content_range:
        return 0
    try:
        return int(content_range.split("/")[1])
    except ValueError:
        return 0


def prune_old_sources(base_url: str, service_key: str) -> Dict[str, int | str | None]:
    stats: Dict[str, int | str | None] = {
        "removed_sources": 0,
        "removed_pages": 0,
        "removed_examples": 0,
        "cutoff": None,
    }

    total_sources = count_rows(base_url, "archon_sources", service_key, column="source_id")
    if total_sources <= MAX_SOURCES:
        return stats

    cutoff_index = max(total_sources - MAX_SOURCES - 1, 0)
    cutoff_rows, _ = fetch_range(
        base_url,
        "archon_sources",
        service_key,
        params={
            "select": "source_id,created_at",
            "order": "created_at.asc",
        },
        start=cutoff_index,
        size=1,
    )

    if not cutoff_rows:
        return stats

    cutoff_ts = cutoff_rows[0]["created_at"]
    stats["cutoff"] = cutoff_ts

    old_sources = fetch_all_rows(
        base_url,
        "archon_sources",
        service_key,
        params={
            "select": "source_id,created_at",
            "order": "created_at.asc",
            "created_at": f"lt.{cutoff_ts}",
        },
    )

    for idx, source in enumerate(old_sources, start=1):
        sid = source["source_id"]
        stats["removed_pages"] += delete_where(
            base_url,
            "archon_crawled_pages",
            service_key,
            params={"source_id": f"eq.{sid}"},
        )
        stats["removed_examples"] += delete_where(
            base_url,
            "archon_code_examples",
            service_key,
            params={"source_id": f"eq.{sid}"},
        )
        if idx % 200 == 0:
            print(f"  removed data for {idx}/{len(old_sources)} sources", flush=True)

    stats["removed_sources"] = delete_where(
        base_url,
        "archon_sources",
        service_key,
        params={"created_at": f"lt.{cutoff_ts}"},
    )

    return stats


def prune_prp_docs(base_url: str, service_key: str) -> Dict[str, int]:
    stats = {"existing": 0, "removed": 0}
    total_docs = count_rows(
        base_url,
        "prp_docs",
        service_key,
        column="id",
        params={"kind": "eq.doc"},
    )
    stats["existing"] = total_docs
    if total_docs <= MAX_PRP_DOCS:
        return stats

    offset = MAX_PRP_DOCS
    while offset < total_docs:
        page, _ = fetch_range(
            base_url,
            "prp_docs",
            service_key,
            params={
                "select": "id",
                "kind": "eq.doc",
                "order": "created_at.desc",
            },
            start=offset,
            size=PAGE_SIZE,
        )
        if not page:
            break
        stats["removed"] += delete_ids(
            base_url,
            "prp_docs",
            service_key,
            (str(item["id"]) for item in page),
        )
        offset += len(page)

    return stats


def main() -> None:
    load_dotenv()

    supabase_url = env_or_fail("SUPABASE_URL")
    service_key = env_or_fail("SUPABASE_SERVICE_KEY")

    base_url = supabase_url.rstrip("/")

    print("== Supabase REST Cleanup ==")
    print(f"Project: {supabase_url}")
    print(f"Retention days: {RETENTION_DAYS}")
    print(f"Chunks/source cap: {MAX_CHUNKS_PER_SOURCE}")
    print(f"Versions/doc cap: {MAX_VERSIONS_PER_DOC}")
    print("")

    source_stats = prune_old_sources(base_url, service_key)
    if source_stats["removed_sources"]:
        print(
            "archon_sources -> "
            f"removed {source_stats['removed_sources']} sources older than {source_stats['cutoff']}\n"
            f"archon_crawled_pages -> removed {source_stats['removed_pages']} old chunks\n"
            f"archon_code_examples -> removed {source_stats['removed_examples']} old examples"
        )
        print("")

    prp_stats = prune_prp_docs(base_url, service_key)
    if prp_stats["removed"]:
        print(
            f"prp_docs -> kept latest {MAX_PRP_DOCS}, removed {prp_stats['removed']} older docs "
            f"(previously {prp_stats['existing']})"
        )
        print("")

    crawl_stats = prune_crawled_pages(base_url, service_key)
    print(
        f"archon_crawled_pages -> deleted {crawl_stats['expired']} expired chunks, "
        f"removed {crawl_stats['capped']} exceeding cap"
    )

    version_deleted = prune_document_versions(base_url, service_key)
    print(f"archon_document_versions -> removed {version_deleted} stale versions")

    print("")
    print("Cleanup finished. Autovacuum will reclaim space shortly; schedule this script to run regularly.")


if __name__ == "__main__":
    main()
class SupabaseRequestError(RuntimeError):
    def __init__(self, method: str, path: str, status_code: int, text: str) -> None:
        super().__init__(f"{method} {path} failed ({status_code}): {text}")
        self.status_code = status_code
        self.text = text
