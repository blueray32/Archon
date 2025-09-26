#!/usr/bin/env bash
# Usage: make dev STORY=feature-x/001
set -euo pipefail
STORY="${STORY:?usage: make dev STORY=feature-x/001}"
PRP="ai_docs/PRPs/${STORY}/PRP.md"
[ -f "$PRP" ] || { echo "PRP not found: $PRP" >&2; exit 1; }

ART="artifacts/${STORY}"
mkdir -p "$ART/diffs"

{
  echo "# Dev run for ${STORY}"
  date -u +"%Y-%m-%dT%H:%M:%SZ"
  echo "- PRP: ${PRP}"
} > "$ART/notes.md"

# If you later want to call a CLI, do it here. For now we stay CLI-agnostic.
if command -v claude >/dev/null 2>&1; then
  echo "- Executor: Claude CLI detected (auto-run disabled for portability; use your IDE/CLI to edit per PRP, then re-run)" >> "$ART/notes.md"
else
  echo "- Executor: manual mode" >> "$ART/notes.md"
fi

# Capture staged + unstaged working-tree changes vs HEAD (no commit needed)
git diff --name-only > "$ART/changed_files.csv" || true
while IFS= read -r f; do
  [ -n "$f" ] || continue
  safe="$(echo "$f" | tr '/' '_')"
  git diff -- "$f" > "$ART/diffs/${safe}.patch" || true
done < "$ART/changed_files.csv"

echo "- Artifacts: $ART" >> "$ART/notes.md"
echo "Dev done."
