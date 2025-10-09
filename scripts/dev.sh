#!/usr/bin/env bash
# Usage: make dev STORY=feature-x/001  [RUN_CLAUDE=0 to skip CLI]
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

# --- run Claude Code interactively (no --prompt flags; ensure TTY) ---
run_claude() {
  # util-linux 'script' (Linux): script -q -c "cmd" /dev/null
  if command -v script >/dev/null 2>&1 && script -q -c "true" /dev/null >/dev/null 2>&1; then
    script -q -c "claude code" /dev/null || true
    return
  fi
  # BSD/macOS 'script': script -q /dev/null <cmd...>
  if command -v script >/dev/null 2>&1; then
    script -q /dev/null claude code || true
    return
  fi
  # Fallback: run directly (may fail if no TTY)
  claude code || true
}

if [[ "${RUN_CLAUDE:-1}" = "1" ]] && command -v claude >/dev/null 2>&1; then
  echo "- Executor: Claude CLI (interactive)" >> "$ART/notes.md"
  echo "- Tip: paste the PRP into Claude if needed -> $PRP" >> "$ART/notes.md"
  run_claude
else
  echo "- Executor: manual mode (RUN_CLAUDE=0 or no claude CLI)" >> "$ART/notes.md"
fi

# --- collect changes vs HEAD (tracked/unstaged/untracked), EXCLUDING noise ---
TMP_LIST="$(mktemp)"
# helper: filter out noisy paths
_filter_noise() { grep -Ev '^(artifacts/|\.git/|node_modules/|python/\.venv/|\.venv/|venv/)$|^artifacts/|^\.git/|^node_modules/|^python/\.venv/|^\.venv/|^venv/'; }

git diff --name-only HEAD            | _filter_noise >> "$TMP_LIST" || true
git diff --name-only --cached        | _filter_noise >> "$TMP_LIST" || true
git ls-files --others --exclude-standard | _filter_noise >> "$TMP_LIST" || true

sort -u "$TMP_LIST" > "$ART/changed_files.csv"
rm -f "$TMP_LIST"

# --- save per-file patches (tracked vs HEAD; untracked vs /dev/null) ---
while IFS= read -r f; do
  [ -n "$f" ] || continue
  safe="$(printf "%s" "$f" | tr '/' '_')"
  if git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
    git diff HEAD -- "$f" > "$ART/diffs/${safe}.patch" || true
  else
    git diff --no-index -- /dev/null "$f" > "$ART/diffs/${safe}.patch" 2>/dev/null || true
  fi
done < "$ART/changed_files.csv"

echo "- Artifacts: $ART" >> "$ART/notes.md"
echo "Dev done."
