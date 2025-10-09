# Daily Agent Log Automation

Quick script to create and update daily agent logs in your Obsidian vault with Claude Code integration.

## Usage

### From Terminal

```bash
# Create/update today's log
export OBSIDIAN_VAULT="/Users/ciarancox/Documents/ArchonVault"
./scripts/daily_agent_log.sh

# Specific date
./scripts/daily_agent_log.sh 2025-10-15
```

### From Claude Code

Use the custom slash command:

```bash
/daily-log
```

This will:
1. Create `Logs/Agents/YYYY-MM-DD.md` if it doesn't exist
2. Use the Agent Log template with pre-filled frontmatter
3. Add a timestamped "✅ Connected via Claude Code MCP" heartbeat
4. Preserve existing content if file already exists

## What It Does

### First Run (New Log)
- Creates `Logs/Agents/2025-10-09.md`
- Applies Agent Log template from `.templates/archon/Agent Log.md`
- Replaces Templater syntax with actual values:
  - `<% tp.date.now("YYYY-MM-DD") %>` → `2025-10-09`
  - `<% tp.date.now("HH:mm") %>` → `14:30`
- Adds initial "Connected via Claude Code MCP ✅" heartbeat

### Subsequent Runs (Existing Log)
- Opens existing log
- Appends new timestamped session:
  ```markdown
  ### 14:30 - Codex Session

  ✅ Connected via Claude Code MCP
  ```
- Preserves all existing content

## Template Format

The script processes the Agent Log template (`Agent Log.md`) and replaces Templater syntax:

```markdown
---
title: Agent Log - <% tp.date.now("YYYY-MM-DD") %>
date: <% tp.date.now("YYYY-MM-DD") %>
area: archon
service: ops
status: active
tags:
  - archon
  - ops
  - agent-log
  - daily
---

# Agent Log - <% tp.date.now("dddd, MMMM DD, YYYY") %>

## 📋 Session Overview

**Start Time:** <% tp.date.now("HH:mm") %>
**Agent:** Claude Code
**Focus Area:**

## 🎯 Objectives
...
```

Becomes:

```markdown
---
title: Agent Log - 2025-10-09
date: 2025-10-09
area: archon
service: ops
status: active
tags:
  - archon
  - ops
  - agent-log
  - daily
---

# Agent Log - Wednesday, October 09, 2025

## 📋 Session Overview

**Start Time:** 14:30
**Agent:** Claude Code
**Focus Area:**

### 14:30 - Session Start

✅ Connected via Claude Code MCP

## 🎯 Objectives
...
```

## Integration with Obsidian

Once created, the log is immediately available in Obsidian:

- **Path**: `Logs/Agents/2025-10-09.md`
- **Frontmatter**: Pre-filled with `area: archon`, `service: ops`, `status: active`
- **Tags**: Automatically tagged for easy filtering
- **Metadata**: Ready for RAG indexing with proper governance

## Opening the Log

The script outputs an Obsidian URI for quick access:

```bash
obsidian://open?vault=ArchonVault&file=Logs/Agents/2025-10-09.md
```

Click to open directly in Obsidian, or use in Alfred/Raycast workflows.

## Fallback Mode

If the template isn't found, the script creates a basic log with all essential sections:

- Session Overview
- Objectives
- Progress Log
- Key Insights
- Completed
- Notes
- Related links

## Environment Variables

- `OBSIDIAN_VAULT`: Path to your Obsidian vault (required)
  - Default: `/Users/ciarancox/Documents/ArchonVault`

## Claude Code Slash Command

The `.claude/commands/daily-log.md` file enables the `/daily-log` command in Claude Code.

When you type `/daily-log`, Claude Code will:
1. Execute the script
2. Show you the file path
3. Display the contents
4. Offer to open it in your editor

## Example Workflow

**Morning:**
```bash
/daily-log
# Creates new log with template
# Add your objectives for the day
```

**Throughout the day:**
```bash
/daily-log
# Adds timestamped heartbeat
# Continue logging in Obsidian
```

**End of day:**
- Review completed objectives
- Add key insights
- Update status to "completed" if done

## Metadata Governance

All logs are created with proper frontmatter:
- `area: archon` - Top-level categorization
- `service: ops` - Archon service/component
- `status: active` - Lifecycle state
- `tags: [archon, ops, agent-log, daily]` - Searchable tags

This ensures:
- ✅ No missing metadata warnings
- ✅ Proper RAG filtering when indexed
- ✅ Consistent structure across all logs
- ✅ Easy querying in Obsidian Dataview

## Tips

1. **Alias the script:**
   ```bash
   echo 'alias daily-log="OBSIDIAN_VAULT=/path/to/vault /path/to/daily_agent_log.sh"' >> ~/.zshrc
   ```

2. **Morning automation:**
   ```bash
   # Add to ~/.zshrc or fish config
   if [[ $(date +%H) -eq 09 ]] && [[ ! -f "$OBSIDIAN_VAULT/Logs/Agents/$(date +%Y-%m-%d).md" ]]; then
       ~/Archon/scripts/daily_agent_log.sh
   fi
   ```

3. **Alfred workflow:**
   - Keyword: `log`
   - Script: `/path/to/daily_agent_log.sh`
   - Open result in Obsidian or VS Code

## Troubleshooting

**Template not found:**
```bash
# Run installer first
./scripts/install_obsidian_templates.sh
```

**Permission denied:**
```bash
chmod +x scripts/daily_agent_log.sh
```

**Wrong vault path:**
```bash
export OBSIDIAN_VAULT="/path/to/your/vault"
# Or edit the script's default VAULT variable
```

## Related

- `install_obsidian_templates.sh` - Install Templater templates
- `templates/obsidian/Agent Log.md` - Template used by this script
- `OBSIDIAN_INTEGRATION.md` - Full integration documentation
