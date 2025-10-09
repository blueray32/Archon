#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-plan}"                                  # plan | apply
VAULT_DIR="${VAULT_DIR:-${HOME}/Documents/ArchonVault}"     # change if needed

# Files to write inside the Obsidian vault
MOC_PATH="${VAULT_DIR}/MOC — Archon.md"
TPL_DIR="${VAULT_DIR}/Templates"
TPL_PATH="${TPL_DIR}/Agent Log.md"
CANVAS_PATH="${VAULT_DIR}/Archon Map.canvas"

# Example MCP client config in the Archon repo (doesn't do anything by itself; safe)
ARCHON_MCP_DIR="$(pwd)/ai_docs/mcp"
ARCHON_MCP_EXAMPLE="${ARCHON_MCP_DIR}/obsidian.client.json.example"

# Helpers
die() { echo "ERROR: $*" >&2; exit 1; }
ensure_dir() { mkdir -p "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }
upper() { printf '%s' "$1" | tr '[:lower:]' '[:upper:]'; }

preview() {
  local f="$1"
  if [[ -f "$f" ]]; then
    echo "----- ${f} (first 60 lines) -----"
    sed -n '1,60p' "$f" || true
    echo "----- end preview -----"
  else
    echo "(will create: ${f})"
  fi
}

plan_write() {
  local target="$1"
  shift
  local tmp
  tmp="$(mktemp)"
  cat >"$tmp"
  if [[ ! -f "$target" ]]; then
    echo "CREATE: $target"
    preview "$tmp"
  else
    if diff -u "$target" "$tmp" >/dev/null 2>&1; then
      echo "UNCHANGED: $target"
    else
      echo "UPDATE: $target (showing diff)"
      diff -u "$target" "$tmp" || true
    fi
  fi
  rm -f "$tmp"
}

apply_write() {
  local target="$1"
  shift
  local tmp
  tmp="$(mktemp)"
  cat >"$tmp"
  if [[ -f "$target" ]] && diff -u "$target" "$tmp" >/dev/null 2>&1; then
    echo "UNCHANGED: $target"
    rm -f "$tmp"
    return 0
  fi
  ensure_dir "$(dirname "$target")"
  mv "$tmp" "$target"
  echo "WROTE: $target"
}

git_status_if_repo() {
  local dir="$1"
  if [[ -d "${dir}/.git" ]] && have git; then
    echo "Git status for ${dir}:"
    git -C "$dir" status -s || true
  else
    echo "No Git repo detected at ${dir} (optional)."
  fi
}

list_candidate_vaults() {
  echo "— Searching for Obsidian vaults —"
  find "${HOME}/Obsidian" \
    "${HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents" \
    -maxdepth 2 -type d -name ".obsidian" 2>/dev/null | sed 's|/.obsidian$||' || true
}

main() {
  echo "MODE=${MODE}"
  echo "VAULT_DIR=${VAULT_DIR}"
  if [[ ! -d "$VAULT_DIR/.obsidian" ]]; then
    echo "Could not find .obsidian inside VAULT_DIR."
    list_candidate_vaults
    die "Set VAULT_DIR to your vault path and re-run."
  fi

  # Content blobs
  MOC_CONTENT="$(cat <<'EOF'
---
title: "🔭 Archon — Map of Content"
type: moc
updated: <% tp.date.now("YYYY-MM-DD HH:mm") %>
---

# Archon — Map of Content

> Quick links: [[PRPs]] · [[Agents]] · [[ContextBundles]] · [[Logs/Agents]] · [[Tasks]]

## PRPs (latest first)
```dataview
TABLE file.mtime as "Updated"
FROM "PRPs"
WHERE type = "prp" OR file.folder = "PRPs"
SORT file.mtime DESC
```

Agents
```dataview
TABLE status, file.mtime as "Updated"
FROM "Agents"
WHERE type = "agent" OR file.folder = "Agents"
SORT file.mtime DESC
```

Context Bundles
```dataview
TABLE file.size as "KB", file.mtime as "Updated"
FROM "ContextBundles"
SORT file.mtime DESC
```

Daily Agent Logs (this week)
```dataview
LIST FROM "Logs/Agents"
WHERE file.mtime >= date(today) - dur(7 days)
SORT file.mtime DESC
```

Open Tasks
```dataview
TASK FROM "Tasks"
WHERE !completed
GROUP BY file.link
```

Recent Changes (last 24h)
```dataview
LIST FROM ""
WHERE file.mtime >= date(today) - dur(1 day)
SORT file.mtime DESC
```
EOF
)"

  TPL_CONTENT="$(cat <<'EOF'
---
title: "Agent Log — <% tp.date.now("YYYY-MM-DD") %>"
type: log
updated: <% tp.date.now("YYYY-MM-DD HH:mm") %>
---

# Agent Log — <% tp.date.now("YYYY-MM-DD") %>

## Decisions
- 

## Changes
- 

## Next Actions
- 
EOF
)"

  CANVAS_JSON="$(cat <<'EOF'
{
  "nodes": [
    { "id": "moc", "type": "file", "file": "MOC — Archon.md", "x": 0, "y": 0, "width": 360, "height": 220 },
    { "id": "prps", "type": "group", "label": "PRPs", "x": -500, "y": -100, "width": 300, "height": 260 },
    { "id": "agents", "type": "group", "label": "Agents", "x": 420, "y": -100, "width": 300, "height": 260 },
    { "id": "bundles", "type": "group", "label": "Context Bundles", "x": 420, "y": 260, "width": 300, "height": 260 },
    { "id": "logs", "type": "group", "label": "Logs/Agents", "x": -500, "y": 260, "width": 300, "height": 260 }
  ],
  "edges": [
    { "id": "e1", "fromNode": "moc", "toNode": "prps" },
    { "id": "e2", "fromNode": "moc", "toNode": "agents" },
    { "id": "e3", "fromNode": "agents", "toNode": "bundles" },
    { "id": "e4", "fromNode": "agents", "toNode": "logs" }
  ]
}
EOF
)"

  MCP_EXAMPLE="$(cat <<'EOF'
{
  "name": "obsidian",
  "server": "filesystem",
  "root": "/ABSOLUTE/PATH/TO/YOUR/VAULT",
  "readonly": false,
  "allowed_write_dirs": ["Logs/Agents", "Tasks"],
  "notes": "Example client config placeholder; wire into Archon MCP client per your setup."
}
EOF
)"

  echo "=== $(upper "$MODE") — Vault changes ==="
  if [[ "$MODE" == "plan" ]]; then
    plan_write "$MOC_PATH" <<<"$MOC_CONTENT"
    plan_write "$TPL_PATH" <<<"$TPL_CONTENT"
    plan_write "$CANVAS_PATH" <<<"$CANVAS_JSON"
  else
    apply_write "$MOC_PATH" <<<"$MOC_CONTENT"
    ensure_dir "$TPL_DIR"
    apply_write "$TPL_PATH" <<<"$TPL_CONTENT"
    apply_write "$CANVAS_PATH" <<<"$CANVAS_JSON"
  fi

  echo "=== $(upper "$MODE") — Archon repo example config ==="
  if [[ "$MODE" == "plan" ]]; then
    plan_write "$ARCHON_MCP_EXAMPLE" <<<"$MCP_EXAMPLE"
  else
    ensure_dir "$ARCHON_MCP_DIR"
    apply_write "$ARCHON_MCP_EXAMPLE" <<<"$MCP_EXAMPLE"
  fi

  echo "=== Git status snapshots ==="
  git_status_if_repo "$VAULT_DIR"
  git_status_if_repo "$(pwd)"

  echo "=== Summary ==="
  echo "MOC note:          $MOC_PATH"
  echo "Agent Log template: $TPL_PATH"
  echo "Canvas:            $CANVAS_PATH"
  echo "MCP example:       $ARCHON_MCP_EXAMPLE"
  echo "Mode:              $MODE"
  echo "Next:              To apply, run: MODE=apply VAULT_DIR=\"/absolute/path/to/vault\" bash scripts/obsidian_moc_ops.sh"
}

main "$@"
