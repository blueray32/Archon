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

PROMPT=$(
  cat <<'EOF'
Follow this PRP strictly. Guardrails:
- Use only files named within the PRP Inputs.
- Keep diffs minimal and focused.
- Update docs/tests exactly as Acceptance requires.
- Summarize your plan BEFORE edits; then apply changes.

--- PRP START ---
EOF
)
PROMPT_TEXT="${PROMPT}
$(cat "$PRP")
--- PRP END ---"

run_claude() {
  # Try util-linux 'script' first (supports: script -q -c "cmd" /dev/null)
  if command -v script >/dev/null 2>&1 && script -q -c "true" /dev/null >/dev/null 2>&1; then
    script -q -c "claude code --prompt $(printf %q "$PROMPT_TEXT")" /dev/null || true
    return
  fi
  # Try BSD/macOS 'script' (no -c; file first, command after)
  if command -v script >/dev/null 2>&1; then
    script -q /dev/null /bin/sh -lc "claude code --prompt \"\$PROMPT_TEXT\"" || true
    return
  fi
  # Fallback: run directly (may fail if no TTY, but we still proceed)
  claude code --prompt "$PROMPT_TEXT" || true
}

if [[ "${RUN_CLAUDE:-1}" = "1" ]] && command -v claude >/dev/null 2>&1; then
  echo "- Executor: Claude CLI" >> "$ART/notes.md"
  run_claude
else
  echo "- Executor: manual mode (RUN_CLAUDE=0 or no claude CLI)" >> "$ART/notes.md"
fi

# Collect changes vs HEAD (staged, unstaged, untracked)
TMP_LIST="$(mktemp)"
git diff --name-only HEAD >> "$TMP_LIST" || true
git diff --name-only --cached >> "$TMP_LIST" || true
git ls-files --others --exclude-standard >> "$TMP_LIST" || true
sort -u "$TMP_LIST" > "$ART/changed_files.csv"
rm -f "$TMP_LIST"

# Save per-file patches
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
