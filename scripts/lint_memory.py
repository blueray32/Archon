#!/usr/bin/env python3
"""
Memory Linter

Checks that memory files stay concise:
- Max 50 lines
- Max 500 tokens (uses tiktoken if available, else ~chars/4 heuristic)

Usage:
  python3 scripts/lint_memory.py --paths "memory/**/*.md" --paths "agents/memory/**/*.md"

Make target:
  make memory-lint [PATHS="memory/**/*.md agents/memory/**/*.md"]
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


DEFAULT_PATTERNS = [
    "memory/**/*.md",
    "agents/memory/**/*.md",
]


@dataclass
class FileDiagnostic:
    file: str
    lines: int
    tokens: int
    severity: str  # "ok" | "error"
    errors: list[str]


def count_tokens(text: str, encoding_name: str | None = None) -> int:
    # Prefer tiktoken when available for accurate counts
    try:
        import tiktoken  # type: ignore

        enc = None
        if encoding_name:
            try:
                enc = tiktoken.get_encoding(encoding_name)
            except Exception:
                enc = None
        if enc is None:
            # Fallback to a common encoding if available
            try:
                enc = tiktoken.encoding_for_model("gpt-4o-mini")
            except Exception:
                enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Heuristic tokens ~ chars / 4
        return int(math.ceil(len(text) / 4))


def lint_file(path: Path, max_lines: int, max_tokens: int, encoding_name: str | None) -> FileDiagnostic:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        return FileDiagnostic(
            file=str(path), lines=0, tokens=0, severity="error", errors=[f"Non-UTF8 file: {e}"]
        )
    except Exception as e:
        return FileDiagnostic(
            file=str(path), lines=0, tokens=0, severity="error", errors=[f"Read error: {e}"]
        )

    lines = content.count("\n") + (0 if content.endswith("\n") or content == "" else 1)
    tokens = count_tokens(content, encoding_name)

    errors: list[str] = []
    if lines > max_lines:
        errors.append(f"Lines {lines} > max {max_lines}")
    if tokens > max_tokens:
        errors.append(f"Tokens {tokens} > max {max_tokens}")

    return FileDiagnostic(
        file=str(path),
        lines=lines,
        tokens=tokens,
        severity="error" if errors else "ok",
        errors=errors,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint memory files for concision")
    parser.add_argument(
        "--paths",
        action="append",
        help="Glob pattern for files (can repeat)",
    )
    parser.add_argument("--max-lines", type=int, default=50)
    parser.add_argument("--max-tokens", type=int, default=500)
    parser.add_argument("--encoding", type=str, default="cl100k_base")
    args = parser.parse_args(argv)

    patterns = args.paths or DEFAULT_PATTERNS

    files: list[str] = []
    for pat in patterns:
        files.extend(glob.glob(pat, recursive=True))

    files = sorted({f for f in files if os.path.isfile(f)})

    diagnostics: list[dict[str, Any]] = []

    for f in files:
        diag = lint_file(Path(f), args.max_lines, args.max_tokens, args.encoding)
        diagnostics.append(asdict(diag))

    error_count = sum(1 for d in diagnostics if d["severity"] == "error")
    result = {
        "summary": {
            "scanned": len(diagnostics),
            "errors": error_count,
            "max_lines": args.max_lines,
            "max_tokens": args.max_tokens,
        },
        "diagnostics": diagnostics,
    }

    # Human-friendly output to stderr if violations
    if error_count > 0:
        print("Memory linter found violations:", file=sys.stderr)
        for d in diagnostics:
            if d["severity"] == "error":
                print(f" - {d['file']}: {', '.join(d['errors'])}", file=sys.stderr)

    # Machine-readable output to stdout
    print(json.dumps(result, ensure_ascii=False))

    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())

