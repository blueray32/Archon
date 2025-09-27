#!/usr/bin/env bash
set -euo pipefail
STORY="${STORY:?usage: make publish STORY=feature-x/ID}"
VAULT="${OBSIDIAN_VAULT:?Set OBSIDIAN_VAULT=/path/to/Vault}"
SRC="artifacts/${STORY}/notes.md"
TS="$(date +%Y-%m-%d)"
DEST="${VAULT}/Archon/${STORY////-}-${TS}.md"
mkdir -p "$(dirname "$DEST")"
{ echo "# Archon Update — ${STORY} (${TS})"; echo; [ -f "$SRC" ] && cat "$SRC" || echo "No notes"; } > "$DEST"
echo "Wrote ${DEST}"
