#!/usr/bin/env python3
"""
Context Bundle Loader

Reads a context bundle JSONL and prints a consolidated summary to stdout.

Usage:
  python3 scripts/load_bundle.py [--bundle DIR]

If --bundle is not provided, the loader uses agents/context-bundles/.current.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path.cwd()
CB_ROOT = ROOT / "agents" / "context-bundles"
CURRENT_FILE = CB_ROOT / ".current"


def get_current_bundle(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not (p.exists() and p.is_dir() and (p / "bundle.jsonl").exists()):
            raise FileNotFoundError(f"Provided bundle directory invalid or missing bundle.jsonl: {p}")
        return p
    if CURRENT_FILE.exists():
        p = Path(CURRENT_FILE.read_text(encoding="utf-8").strip())
        if p.exists():
            return p
    # Fallback: newest directory with bundle.jsonl
    candidates = [d for d in CB_ROOT.glob("*/") if (d / "bundle.jsonl").exists()]
    if not candidates:
        raise FileNotFoundError("No bundle found. Create one with make bundle-new PURPOSE=\"...\"")
    return max(candidates, key=lambda d: d.stat().st_mtime)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Invalid JSON on line {i}: {e}")
            if not isinstance(obj, dict):
                raise RuntimeError(f"Invalid record type on line {i}: expected object, got {type(obj).__name__}")
            records.append(obj)
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "purpose": None,
        "counts": {"file": 0, "findings": 0, "other": 0},
        "files": [],
        "findings": [],
    }
    for rec in records:
        rtype = rec.get("type")
        if rtype == "start":
            summary["purpose"] = rec.get("purpose")
        elif rtype == "file":
            summary["counts"]["file"] += 1
            summary["files"].append({
                "path": rec.get("relpath") or rec.get("path"),
                "size": rec.get("size"),
                "sha256": rec.get("sha256"),
            })
        elif rtype == "findings":
            summary["counts"]["findings"] += 1
            bullets = rec.get("bullets") or []
            if isinstance(bullets, list):
                summary["findings"].extend([str(b) for b in bullets])
        else:
            summary["counts"]["other"] += 1
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load and summarize a context bundle")
    parser.add_argument("--bundle", required=False, help="Bundle directory (defaults to current)")
    args = parser.parse_args(argv)

    try:
        bdir = get_current_bundle(args.bundle)
        bpath = bdir / "bundle.jsonl"
        records = load_jsonl(bpath)
        print(json.dumps({
            "bundle": str(bdir),
            "summary": summarize(records),
            "records": records,
        }, ensure_ascii=False))
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())

