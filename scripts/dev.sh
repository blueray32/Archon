#!/usr/bin/env bash
# Usage: make dev STORY=feature-x/001
set -euo pipefail
STORY="${STORY:?usage: make dev STORY=feature-x/001}"
PRP="ai_docs/PRPs/${STORY}/PRP.md"
[ -f "$PRP" ] || { echo "PRP not found: $PRP" >&2; exit 1; }

ART="artifacts/${STORY}"
mkdir -p "$ART/diffs"

echo "# Dev run for ${STORY}" > "$ART/notes.md"
date -u +"%Y-%m-%dT%H:%M:%SZ" >> "$ART/notes.md"
echo "- PRP: ${PRP}" >> "$ART/notes.md"

BASE="$(git rev-parse HEAD 2>/dev/null || echo '')"

# Optional: run with Claude Code if installed (edit to your liking)
if command -v claude >/dev/null 2>&1; then
  echo "- Executor: Claude Code" >> "$ART/notes.md"
  # Keep it simple: pass the PRP as the prompt; cwd is repo root so file tools apply here
  claude code --project . --prompt "Follow this PRP strictly, use named reads only, minimize diffs:\n\n$(cat "$PRP")" || true
else
  echo "- Executor: (no claude CLI found) — manual edit mode" >> "$ART/notes.md"
  echo "Edit files per $PRP, then re-run 'make dev STORY=${STORY}' to snapshot diffs." >&2
fi

# Snapshot diffs vs BASE (if repo had no commits, BASE may be blank)
if [ -n "$BASE" ]; then
  git diff --name-only "$BASE"... > "$ART/changed_files.csv" || true
  # Save unified diffs per file (human-friendly review)
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    safe="$(echo "$f" | tr '/' '_')"
    git diff "$BASE"... -- "$f" > "$ART/diffs/${safe}.patch" || true
  done < "$ART/changed_files.csv"
else
  # fallback: list modified & untracked
  git status --porcelain | awk '{print $2}' > "$ART/changed_files.csv" || true
fi

echo "- Artifacts: $ART" >> "$ART/notes.md"
echo "Dev done."
