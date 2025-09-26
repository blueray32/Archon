#!/usr/bin/env bash
set -euo pipefail
TASK="${TASK:-}"
OUT="artifacts/context-bundle"
mkdir -p "$OUT"
git ls-files > "$OUT/filelist.txt"
echo "Wrote $OUT/filelist.txt"
