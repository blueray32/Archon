#!/usr/bin/env bash
# Usage: OBSIDIAN_VAULT="/path/to/Vault" make publish STORY=feature-x/001
set -euo pipefail
STORY="${STORY:?usage: make publish STORY=feature-x/001}"
VAULT="${OBSIDIAN_VAULT:-}"
[ -n "$VAULT" ] || { echo "Set OBSIDIAN_VAULT to your Obsidian vault path"; exit 1; }

SRC_NOTES="artifacts/${STORY}/notes.md"
TS="$(date +%Y-%m-%d)"
DEST="${VAULT}/Archon/${STORY//\//-}-${TS}.md"
mkdir -p "$(dirname "$DEST")"

{
  echo "# Archon Update — ${STORY} (${TS})"
  echo
  [ -f "$SRC_NOTES" ] && cat "$SRC_NOTES" || echo "_No notes found_"
} > "$DEST"

echo "Wrote ${DEST}"
