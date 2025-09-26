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

# ---- Try to run Claude CLI if present (but never fail on it)
PROMPT=$(
  cat <<'EOF'
Follow this PRP strictly. Obey these guardrails:
- Use only files named within the PRP Inputs.
- Keep diffs minimal and focused.
- Update docs/tests exactly as Acceptance requires.
- Summarize your plan BEFORE edits; then apply changes.
EOF
)
if command -v claude >/dev/null 2>&1; then
  echo "- Executor: Claude CLI detected" >> "$ART/notes.md"
  HELP="$(claude code --help 2>&1 || true)"
  # Prefer a --prompt-like flag if available
  if printf "%s" "$HELP" | grep -q -- "--prompt"; then
    claude code --prompt "$PROMPT

--- PRP START ---
$(cat "$PRP")
--- PRP END ---" || true
  else
    # Fallback: try piping prompt to stdin; if unsupported, it will no-op
    printf "%s\n\n--- PRP START ---\n%s\n--- PRP END ---\n" "$PROMPT" "$(cat "$PRP")" | claude code || true
  fi
else
  echo "- Executor: manual mode (no claude CLI found)" >> "$ART/notes.md"
fi

# ---- Collect changes vs HEAD (staged, unstaged, and untracked)
TMP_LIST="$(mktemp)"
git diff --name-only HEAD >> "$TMP_LIST" || true
git diff --name-only --cached >> "$TMP_LIST" || true
git ls-files --others --exclude-standard >> "$TMP_LIST" || true
sort -u "$TMP_LIST" > "$ART/changed_files.csv"
rm -f "$TMP_LIST"

# ---- Save per-file patches
while IFS= read -r f; do
  [ -n "$f" ] || continue
  safe="$(printf "%s" "$f" | tr '/' '_')"
  if git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
    # tracked file: diff vs HEAD
    git diff HEAD -- "$f" > "$ART/diffs/${safe}.patch" || true
  else
    # untracked file: create a no-index patch
    git diff --no-index -- /dev/null "$f" > "$ART/diffs/${safe}.patch" 2>/dev/null || true
  fi
done < "$ART/changed_files.csv"

echo "- Artifacts: $ART" >> "$ART/notes.md"
echo "Dev done."
