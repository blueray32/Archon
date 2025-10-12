# Nexarch Obsidian Integration - Quick Start

Everything you need to run daily operations with Nexarch and Obsidian.

## One-Time Setup

### 1. Install Templates
```bash
./scripts/install_obsidian_templates.sh
# Choose option 1 (Symlink - recommended)
```

### 2. Configure Obsidian
**Settings → Templater:**
- Template folder location: `.templates/archon`
- (Optional) Folder Templates:
  - Folder: `Logs/Agents`
  - Template: `.templates/archon/Agent Log.md`

### 3. Set Environment Variable
```bash
# Add to ~/.zshrc or ~/.bashrc
export OBSIDIAN_VAULT="/Users/ciarancox/Documents/ArchonVault"
```

### 4. Configure MCP (Claude Code)
Point your MCP client config to:
```
/Users/ciarancox/Archon/configs/mcp/archon.json
```

This provides both:
- **nexarch** MCP server (list_obsidian_metadata_gaps, update_obsidian_frontmatter)
- **obsidian** filesystem server (read/write vault files)

## Daily Operations

### Start Services

```bash
# Start API server (port 8181)
make api

# Start MCP server (port 8051)
make mcp
```

### Create Daily Log

**From terminal:**
```bash
make daily-log
```

**From Claude Code:**
```bash
/daily-log
```

**What it does:**
- First run: Creates `Logs/Agents/2025-10-09.md` with full template
- Subsequent runs: Adds timestamped "Connected via Claude Code MCP ✅" heartbeat

### Audit Vault Metadata

```bash
# Quick summary
make obsidian-audit

# Full list
curl http://127.0.0.1:8181/api/obsidian/review/missing-tags | jq
```

### Update Frontmatter

```bash
# Single note
curl -X POST http://127.0.0.1:8181/api/obsidian/frontmatter/update \
  -H 'Content-Type: application/json' \
  -d '{"path":"Daily/2025-10-09.md","updates":{"area":"archon","service":"ops","status":"active"},"merge":true}'
```

## Quick Reference

### Makefile Commands

```bash
make help           # Show all available commands
make api            # Start API server (8181)
make mcp            # Start MCP server (8051)
make daily-log      # Create/update today's log
make obsidian-audit # Audit vault metadata
```

### API Routes

**Base URL:** `http://127.0.0.1:8181`

- `GET /health` - Server health check
- `GET /api/obsidian/review/missing-tags` - Find notes missing metadata
- `POST /api/obsidian/frontmatter/update` - Update note frontmatter

### MCP Tools (via Claude Code)

- `list_obsidian_metadata_gaps` - Audit notes missing area/service/status
- `update_obsidian_frontmatter` - Batch update frontmatter fields

### Scripts

- `./scripts/daily_agent_log.sh [DATE]` - Create/update daily log
- `./scripts/install_obsidian_templates.sh` - Install Templater templates
- `./scripts/obsidian_moc_ops.sh` - Vault operations

### Ports

- **8181** - Main API server
- **8051** - MCP server
- **3737** - Frontend UI (nexarch-ui-main)

## Typical Workflow

**Morning:**
```bash
# 1. Start services
make api
make mcp

# 2. Create today's log
make daily-log

# 3. Open in Obsidian and add objectives
```

**Throughout Day:**
```bash
# Add session heartbeats
/daily-log  # From Claude Code

# Take notes in Obsidian
# Edit Logs/Agents/2025-10-09.md
```

**End of Day:**
```bash
# Review vault metadata health
make obsidian-audit

# Fix any missing metadata
curl -X POST http://127.0.0.1:8181/api/obsidian/frontmatter/update ...
```

## Frontmatter Schema

All notes should have:
```yaml
---
area: nexarch | personal | client-x
service: ops | research | docs | sales | crawler | mcp | ui | database | embedding | search
status: active | draft | review | published | archived
tags:
  - nexarch
  - other-tags
---
```

**Why:**
- ✅ RAG filtering by area/service/status
- ✅ Metadata governance compliance
- ✅ No missing metadata warnings
- ✅ Consistent structure for queries

## Troubleshooting

**API not starting:**
```bash
# Check if already running
ps aux | grep uvicorn | grep 8181

# Check logs
tail -f artifacts/uvicorn_8181.log
```

**MCP tools not showing:**
```bash
# Verify MCP server running
curl http://127.0.0.1:8051/health

# Check MCP config
cat configs/mcp/archon.json

# Restart Claude Code MCP connection
```

**Template not found:**
```bash
# Reinstall templates
./scripts/install_obsidian_templates.sh

# Verify symlink
ls -la /Users/ciarancox/Documents/ArchonVault/.templates/archon/
```

**Wrong vault path:**
```bash
# Check environment
echo $OBSIDIAN_VAULT

# Update if needed
export OBSIDIAN_VAULT="/path/to/your/vault"
```

## Documentation

- `OBSIDIAN_INTEGRATION.md` - Full integration guide
- `templates/obsidian/README.md` - Template documentation
- `scripts/README_DAILY_LOG.md` - Daily log automation details
- `.claude/commands/daily-log.md` - Slash command definition

## Features

✅ **Hash-based change detection** - Only re-index when content changes
✅ **Tag normalization** - Scalar/array frontmatter handled safely
✅ **Safe watcher** - Event loop won't crash
✅ **Deletion handler** - Removes indexed content when files deleted
✅ **Metadata extraction** - area/service/status for RAG filtering
✅ **MCP tools** - Audit and update frontmatter programmatically
✅ **Daily automation** - One command to create/update logs
✅ **Template system** - Consistent structure across all notes

## Support

- GitHub: https://github.com/blueray32/Nexarch
- Issues: Create in GitHub repo
- Docs: http://localhost:3737/ (when frontend running)

---

**Last Updated:** 2025-10-09
**Version:** Production (main branch)
