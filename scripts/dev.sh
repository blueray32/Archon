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

# Auto-run Claude Code unless disabled
if [[ "${RUN_CLAUDE:-1}" = "1" && "$(command -v claude || true)" ]]; then
  echo "- Executor: Claude CLI" >> "$ART/notes.md"
  # Prefer a real TTY: use 'script' if present (avoids Ink raw-mode crash)
  if command -v script >/dev/null 2>&1; then
    script -q /dev/null -c "claude code --prompt $(printf %q "$PROMPT_TEXT")" || true
  else
    claude code --prompt "$PROMPT_TEXT" || true
  fi
else
  echo "- Executor: manual mode (RUN_CLAUDE=0 or no claude CLI)" >> "$ART/notes.md"
fi

# Collect changes vs HEAD (tracked + untracked)
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
