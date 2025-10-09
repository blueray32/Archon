#!/usr/bin/env bash
set -euo pipefail

NAME="${1:?usage: scripts/speckit.sh <name>}"
OUT="ai_docs/specs/${NAME}"
TPL="tools/spec-kit/templates"

mkdir -p "$OUT"

# Ensure README.md exists in $OUT (prefer templates when available)
ensure_readme() {
  local target="$OUT/README.md"
  # Do not overwrite if user already created it
  if [ -f "$target" ]; then
    return 0
  fi
  if [ -d "$TPL" ]; then
    if [ -f "$TPL/README.md" ]; then
      cp "$TPL/README.md" "$target"
      return 0
    fi
    if [ -f "$TPL/README-template.md" ]; then
      cp "$TPL/README-template.md" "$target"
      return 0
    fi
  fi
  # Fallback placeholder
  printf '# %s\n' "$NAME" > "$target"
}

# Ensure spec.md exists in $OUT (prefer templates when available)
ensure_spec() {
  local target="$OUT/spec.md"
  # Do not overwrite if user already created it
  if [ -f "$target" ]; then
    return 0
  fi
  if [ -d "$TPL" ]; then
    if [ -f "$TPL/spec.md" ]; then
      cp "$TPL/spec.md" "$target"
      return 0
    fi
    if [ -f "$TPL/spec-template.md" ]; then
      cp "$TPL/spec-template.md" "$target"
      return 0
    fi
  fi
  # Fallback placeholder
  printf '# Spec: %s\n' "$NAME" > "$target"
}

ensure_readme
ensure_spec

echo "SpecKit: scaffolded $OUT"
