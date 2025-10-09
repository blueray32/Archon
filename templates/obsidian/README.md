# Obsidian Templates for Archon

This directory contains Templater templates for Archon-integrated note-taking in Obsidian.

## Templates

### Agent Log.md
Full-featured daily agent session log with:
- Auto-filled frontmatter: `area: archon`, `service: ops`, `status: active`
- Timestamped sections for tracking progress
- Structured sections: Objectives, Progress, Insights, Issues, Completed, Notes
- Related links section

**Usage in Obsidian:**
1. Install the Templater plugin
2. Copy this template to your vault's template folder (Settings → Templater → Template folder location)
3. Create new note in `Logs/Agents/` folder
4. Run Templater command: "Templater: Open Insert Template modal"
5. Select "Agent Log"

**Suggested filename:** `Logs/Agents/<YYYY-MM-DD>.md` (e.g., `Logs/Agents/2025-10-09.md`)

### Quick Agent Note.md
Minimal template for quick notes with:
- Cursor placeholders for title and service
- Pre-filled `area: archon` and `status: draft`
- Basic frontmatter structure

**Usage:**
Same as Agent Log, but optimized for quick capture.

## Installation

### Option 1: Copy Templates
```bash
cp templates/obsidian/*.md "/Users/ciarancox/Documents/ArchonVault/.templates/"
```

### Option 2: Symlink (recommended)
```bash
ln -s "/Users/ciarancox/Archon/templates/obsidian" "/Users/ciarancox/Documents/ArchonVault/.templates/archon"
```

Then configure Templater to use `.templates` or `.templates/archon` as the template folder.

## Templater Configuration

In Obsidian Settings → Templater:

1. **Template folder location:** `.templates` (or `.templates/archon` if using symlink)
2. **Syntax:** `<%` and `%>` (default)
3. **Trigger Templater on new file creation:** Optional, can auto-apply based on folder
4. **Enable Folder Templates:** Optional, can auto-apply "Agent Log" for files in `Logs/Agents/`

### Folder Template Setup (Optional)

To automatically apply the Agent Log template to new files in `Logs/Agents/`:

1. Settings → Templater → Folder Templates
2. Add folder template:
   - **Folder:** `Logs/Agents`
   - **Template:** `.templates/Agent Log.md`

Now any new note created in `Logs/Agents/` will automatically use the template.

## Frontmatter Schema

All templates follow the Archon frontmatter schema:

```yaml
---
title: Note title
date: YYYY-MM-DD
area: archon | personal | client-x
service: ops | research | docs | sales | crawler | mcp | ui | database | embedding | search
status: active | draft | review | published | archived
tags:
  - archon
  - other-tags
---
```

These fields enable:
- **area**: Top-level categorization for RAG filtering
- **service**: Archon service/component association
- **status**: Lifecycle state
- **tags**: Flexible tagging (scalar or array, auto-normalized by Archon)

## Integration with Archon

When these notes are indexed by Archon:
1. Frontmatter metadata is extracted and normalized
2. `area`, `service`, `status` available for filtering in RAG queries
3. Tags are normalized (scalar → array) to prevent type errors
4. Content is chunked and embedded for semantic search

Use the Archon MCP tools to audit and update frontmatter:
- `list_obsidian_metadata_gaps` - Find notes missing required fields
- `update_obsidian_frontmatter` - Batch update frontmatter fields
