#!/usr/bin/env bash
set -euo pipefail
NAME="${1:?usage: scripts/speckit.sh <name>}"
OUT="ai_docs/specs/${NAME}"
TPL="tools/spec-kit/templates"
mkdir -p "$OUT"

# copy a minimal set (if submodule present); otherwise create placeholders
if [ -f "$TPL/README.md" ] && [ -f "$TPL/spec.md" ]; then
  cp -n "$TPL"/README.md "$OUT/README.md" 2>/dev/null || true
  cp -n "$TPL"/spec.md "$OUT/spec.md" 2>/dev/null || true
else
  echo "# $NAME" > "$OUT/README.md"
  echo "# Spec: $NAME" > "$OUT/spec.md"
fi
echo "SpecKit: scaffolded $OUT"
