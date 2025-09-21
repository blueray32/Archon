#!/usr/bin/env python3
"""
Bulk-import local files into Archon Knowledge Base via /api/documents/upload.

Usage:
  python3 scripts/import_local_kb.py --path /absolute/path/to/folder \
    [--server http://localhost:8181] [--tag ai-agent-mastery] [--type technical]

Notes:
- Skips non-text/binary files by default. Adjust EXT_WHITELIST below as needed.
- Sends tags as JSON array and knowledge_type as required by the API.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
import sys
import time

import requests


EXT_WHITELIST = {
    ".md",
    ".markdown",
    ".txt",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".rst",
}


def guess_mime(p: Path) -> str:
    mt, _ = mimetypes.guess_type(str(p))
    return mt or "text/plain"


def should_include(p: Path) -> bool:
    if not p.is_file():
        return False
    ext = p.suffix.lower()
    if ext in EXT_WHITELIST:
        return True
    # Include .log and no-extension small text files heuristically
    if ext == ".log":
        return True
    if ext == "":
        try:
            size = p.stat().st_size
            return size < 2 * 1024 * 1024  # < 2MB
        except Exception:
            return False
    return False


def upload_file(server: str, file_path: Path, tags: list[str], knowledge_type: str) -> tuple[bool, str]:
    url = f"{server.rstrip('/')}/api/documents/upload"
    mime = guess_mime(file_path)
    try:
        with file_path.open("rb") as f:
            files = {"file": (file_path.name, f, mime)}
            data = {
                "tags": json.dumps(tags),
                "knowledge_type": knowledge_type,
            }
            resp = requests.post(url, files=files, data=data, timeout=60)
            if resp.ok:
                return True, resp.text
            return False, f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, str(e)


def main():
    ap = argparse.ArgumentParser(description="Import a local folder into Archon KB")
    ap.add_argument("--path", required=True, help="Absolute path to folder or file")
    ap.add_argument("--server", default=os.environ.get("ARCHON_SERVER_URL", "http://localhost:8181"))
    ap.add_argument("--tag", action="append", default=[], help="Tag to attach (can repeat)")
    ap.add_argument("--type", dest="ktype", default="technical", help="knowledge_type: technical|business")
    args = ap.parse_args()

    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        sys.exit(1)

    tags = args.tag or []
    # Add folder name as a tag by default
    if root.is_dir():
        tags.append(root.name)

    total = 0
    success = 0
    failed = 0
    errors: list[tuple[Path, str]] = []

    paths: list[Path]
    if root.is_file():
        paths = [root]
    else:
        paths = [p for p in root.rglob("*") if should_include(p)]

    print(f"Discovered {len(paths)} files to upload from {root}")
    for p in paths:
        total += 1
        ok, msg = upload_file(args.server, p, tags, args.ktype)
        if ok:
            success += 1
            print(f"[OK] {p}")
        else:
            failed += 1
            errors.append((p, msg))
            print(f"[ERR] {p} -> {msg}")
        # Be polite to server
        time.sleep(0.05)

    print(f"\nDone. Uploaded {success}/{total} files. Failed: {failed}")
    if errors:
        print("Failures:")
        for p, emsg in errors[:20]:
            print(f"- {p}: {emsg}")
        if len(errors) > 20:
            print(f"... and {len(errors) - 20} more")


if __name__ == "__main__":
    main()

