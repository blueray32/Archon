#!/usr/bin/env python3
"""
Context Bundle Writer

Creates and appends entries to JSONL bundles under agents/context-bundles/.

Commands:
  - new --purpose "..." [--id NAME]
      Creates a new bundle directory and bundle.jsonl with a start record.

  - read --path PATH [--bundle DIR]
      Appends a file record with content and metadata to bundle.jsonl.

  - findings --bullets '["Item A","Item B"]' [--bundle DIR]
      Appends a findings record with bullets.

Behavior:
  - Maintains agents/context-bundles/.current containing the active bundle dir.
  - Fails fast with clear error messages on invalid inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.cwd()
CB_ROOT = ROOT / "agents" / "context-bundles"
CURRENT_FILE = CB_ROOT / ".current"


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-")
    return s.lower()[:40] or "bundle"


def ensure_root() -> None:
    try:
        CB_ROOT.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise RuntimeError(f"Failed to create bundles root at {CB_ROOT}: {e}")


def set_current(bundle_dir: Path) -> None:
    try:
        CURRENT_FILE.write_text(str(bundle_dir), encoding="utf-8")
    except Exception as e:
        raise RuntimeError(f"Failed to set current bundle: {e}")


def get_current(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit)
        if not (p.exists() and p.is_dir() and (p / "bundle.jsonl").exists()):
            raise FileNotFoundError(f"Provided bundle directory invalid or missing bundle.jsonl: {p}")
        return p

    if CURRENT_FILE.exists():
        p = Path(CURRENT_FILE.read_text(encoding="utf-8").strip())
        if p.exists():
            return p

    # Fallback: newest subdir with bundle.jsonl
    candidates: list[Path] = [d for d in CB_ROOT.glob("*/") if (d / "bundle.jsonl").exists()]
    if not candidates:
        raise FileNotFoundError(
            "No current bundle found. Create one with: make bundle-new PURPOSE=\"...\""
        )
    latest = max(candidates, key=lambda d: d.stat().st_mtime)
    set_current(latest)
    return latest


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_jsonl_record(bundle_path: Path, record: dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False)
    with bundle_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


@dataclass
class StartRecord:
    type: str
    purpose: str
    created_at: str
    tool: str
    version: str


@dataclass
class FileRecord:
    type: str
    path: str
    relpath: str
    size: int
    sha256: str
    created_at: str
    content: str


@dataclass
class FindingsRecord:
    type: str
    bullets: list[str]
    created_at: str


def cmd_new(purpose: str, ident: str | None) -> None:
    ensure_root()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"{ts}-{slugify(ident or purpose)}"
    bundle_dir = CB_ROOT / name
    try:
        bundle_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise RuntimeError(f"Bundle directory already exists: {bundle_dir}")
    bundle_path = bundle_dir / "bundle.jsonl"

    start = StartRecord(
        type="start",
        purpose=purpose,
        created_at=iso_now(),
        tool="context-bundle-writer",
        version="1",
    )
    write_jsonl_record(bundle_path, asdict(start))
    set_current(bundle_dir)
    print(str(bundle_dir))


def cmd_read(file_path: str, bundle: str | None) -> None:
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")

    bundle_dir = get_current(bundle)
    bundle_path = bundle_dir / "bundle.jsonl"

    try:
        content = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise RuntimeError(f"File is not UTF-8 text: {p}")

    p_resolved = p.resolve()
    root_resolved = ROOT.resolve()
    if hasattr(p_resolved, "is_relative_to"):
        is_rel = p_resolved.is_relative_to(root_resolved)  # type: ignore[attr-defined]
    else:
        try:
            p_resolved.relative_to(root_resolved)
            is_rel = True
        except Exception:
            is_rel = False

    relpath = (
        str(p_resolved.relative_to(root_resolved)) if is_rel else p.name
    )

    rec = FileRecord(
        type="file",
        path=str(p_resolved),
        relpath=relpath,
        size=p.stat().st_size,
        sha256=sha256_file(p),
        created_at=iso_now(),
        content=content,
    )
    write_jsonl_record(bundle_path, asdict(rec))
    print(str(bundle_path))


def cmd_findings(bullets_text: str, bundle: str | None) -> None:
    try:
        bullets = json.loads(bullets_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"BULLETS must be a JSON array string: {e}")

    if not isinstance(bullets, list) or not all(isinstance(b, str) for b in bullets):
        raise ValueError("BULLETS must be a JSON array of strings, e.g. ['Risk A','Risk B']")

    bundle_dir = get_current(bundle)
    bundle_path = bundle_dir / "bundle.jsonl"

    rec = FindingsRecord(type="findings", bullets=bullets, created_at=iso_now())
    write_jsonl_record(bundle_path, asdict(rec))
    print(str(bundle_path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Context bundle writer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="Create a new bundle")
    p_new.add_argument("--purpose", required=True, help="Purpose/goal for this bundle")
    p_new.add_argument("--id", dest="ident", required=False, help="Optional bundle name override")

    p_read = sub.add_parser("read", help="Append a file's content to the bundle")
    p_read.add_argument("--path", required=True, help="Path to file to read")
    p_read.add_argument("--bundle", required=False, help="Explicit bundle directory to write to")

    p_findings = sub.add_parser("findings", help="Append findings bullets to the bundle")
    p_findings.add_argument("--bullets", required=True, help="JSON array string of bullet texts")
    p_findings.add_argument("--bundle", required=False, help="Explicit bundle directory to write to")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "new":
            cmd_new(args.purpose, args.ident)
        elif args.cmd == "read":
            cmd_read(args.path, args.bundle)
        elif args.cmd == "findings":
            cmd_findings(args.bullets, args.bundle)
        else:
            parser.error("Unknown command")
        return 0
    except Exception as e:
        # Fail fast with detailed error
        print(f"ERROR: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    sys.exit(main())
