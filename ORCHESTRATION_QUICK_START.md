# Orchestration System - Quick Start

## What Was Built

I've implemented a complete **Hybrid Orchestration System** for Archon that routes tasks between:

1. **Cloud Claude** (local/IDE) - For filesystem, code edits, Obsidian notes, privacy-sensitive work
2. **Cloud Codex** (cloud) - For web APIs, batch automation, multi-service glue
3. **Local Ollama** (local models) - For cheap parallel LLM work (tagging, summarizing, extracting)

## Components Created

### Core Agents & Tools

1. **`orchestrator_agent.py`** - High-level task planning with routing policy
2. **`ollama_client.py`** - Integration for local Ollama models
3. **`task_executor.py`** - Executes plans with dependency resolution
4. **`obsidian_tools.py`** - Vault scanning, tagging, frontmatter management
5. **`archon_memory_sync.py`** - Syncs Obsidian data to Archon database

### Workflow Script

**`orchestrate_obsidian_sync.py`** - End-to-end demo that:
- Scans your Obsidian vault
- Auto-tags notes using Ollama (optional)
- Updates frontmatter with tags
- Syncs everything to Archon's database
- Creates a master index note (MOC)

## Quick Test (Dry Run)

```bash
cd /Users/ciarancox/Archon/python

# Basic dry run (plan only, no execution)
uv run python src/scripts/orchestrate_obsidian_sync.py \
  --vault /Users/ciarancox/Documents/ArchonVault \
  --dry-run

# Full dry run with all features
uv run python src/scripts/orchestrate_obsidian_sync.py \
  --vault /Users/ciarancox/Documents/ArchonVault \
  --auto-tag \
  --create-embeddings \
  --dry-run
```

**Output:**
```json
{
  "goal": "Index Obsidian vault at /path/to/vault, auto-tag notes, sync to Archon",
  "tasks": [
    {
      "id": "T1",
      "description": "Scan Obsidian vault and collect note paths, headings, tags",
      "route": "claude",
      "inputs": ["/path/to/vault"],
      "outputs": ["vault_index.json"],
      "accept_criteria": "JSON file with complete vault index",
      "priority": "high"
    },
    {
      "id": "T4",
      "description": "Sync vault index and notes to Archon memory",
      "route": "claude",
      "inputs": ["vault_index.json"],
      "outputs": ["sync_report.json", "archon_index.md"],
      "depends_on": ["T1"],
      "priority": "high"
    }
  ]
}
```

## Full Execution

### Prerequisites

1. **Ollama** (for auto-tagging):
```bash
# Install Ollama (if not already installed)
# Visit https://ollama.ai

# Pull recommended model
ollama pull qwen2.5:3b

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

2. **Supabase** (for Archon memory sync):
```bash
# Check environment variables
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_KEY
```

### Run the Full Workflow

```bash
cd /Users/ciarancox/Archon/python

# Basic sync (scan vault + sync to Archon)
uv run python src/scripts/orchestrate_obsidian_sync.py \
  --vault /Users/ciarancox/Documents/ArchonVault

# With auto-tagging via Ollama
uv run python src/scripts/orchestrate_obsidian_sync.py \
  --vault /Users/ciarancox/Documents/ArchonVault \
  --auto-tag

# Full workflow with embeddings for RAG
uv run python src/scripts/orchestrate_obsidian_sync.py \
  --vault /Users/ciarancox/Documents/ArchonVault \
  --auto-tag \
  --create-embeddings
```

### Expected Workflow

1. **[1/4] Creating orchestration plan**
   - Plans 2-4 tasks depending on flags
   - Routes tasks to Claude (filesystem) or Ollama (tagging)

2. **[2/4] Scanning Obsidian vault**
   - Recursively scans all `.md` files
   - Extracts frontmatter, tags, headings
   - Saves `vault_index.json`

3. **[3/4] Auto-tagging notes** (if `--auto-tag`)
   - Batches notes through Ollama
   - Suggests: `area`, `service`, `status` tags
   - Updates frontmatter in notes
   - Saves `tag_suggestions.json`

4. **[4/4] Syncing to Archon memory**
   - Stores vault index in `prp_docs` table
   - Indexes individual notes (with embeddings if requested)
   - Creates tag index
   - Generates MOC at `<vault>/Archon/index.md`

### Outputs

All artifacts saved to `artifacts/obsidian_sync_<date>/`:

```
artifacts/obsidian_sync_2025-01-07/
├── vault_index.json              # Complete vault metadata
├── tag_suggestions.json          # Ollama tag suggestions (if --auto-tag)
├── archon_sync_report.json       # Database sync results
└── obsidian_orchestration_report.json  # Final execution report
```

Plus in your Obsidian vault:
```
/Users/ciarancox/Documents/ArchonVault/Archon/
└── index.md                      # Master index note (MOC)
```

## Tag Schema

Auto-tagging classifies notes into:

- **area**: MEP, BIM, Revit, NavisWorks, Spanish, Community, Engineering, Architecture, Construction
- **service**: agents, crawler, mcp, ui, database, embedding, search
- **status**: draft, review, published, archived
- **source**: archon, manual, imported, generated

Example frontmatter after auto-tagging:

```yaml
---
title: My Note About Revit MEP
area: MEP
service: null
status: draft
source: archon
updated: 2025-01-07T19:40:17.123456
tags:
  - revit
  - mep
  - automation
---
```

## Using the Components Standalone

### Obsidian Tools

```python
from agents.obsidian_tools import ObsidianTools

tools = ObsidianTools("/path/to/vault")

# Scan entire vault
index = tools.scan_vault()
print(f"Found {index.notes_count} notes")

# Update a note's frontmatter
tools.update_frontmatter(
    note_path=Path("vault/notes/my-note.md"),
    updates={"area": "BIM", "status": "review"},
    merge=True
)

# Create index note
index_path = tools.create_index_note(index)
```

### Ollama Client

```python
from agents.ollama_client import OllamaClient

async with OllamaClient() as client:
    # Single generation
    result = await client.generate(
        model="qwen2.5:3b",
        prompt="Summarize this note...",
        system="You are a concise summarizer."
    )

    # Batch processing
    prompts = ["Summarize note 1", "Summarize note 2", ...]
    results = await client.batch_generate(
        model="qwen2.5:3b",
        prompts=prompts,
        max_concurrent=5
    )
```

### Archon Memory Sync

```python
from agents.archon_memory_sync import ArchonMemorySync
from server.services.client_manager import get_supabase_client

supabase = get_supabase_client()
sync = ArchonMemorySync(supabase)

# Sync vault to Archon
report = await sync.sync_vault_index(vault_index, create_embeddings=False)
print(f"Synced {report['synced_notes']} notes")

# Query synced notes
notes = await sync.query_vault_notes(
    query="revit mep",
    vault_path="/path/to/vault",
    limit=10
)
```

## Routing Policy

The orchestrator automatically routes tasks based on:

| Condition | Executor | Reason |
|-----------|----------|--------|
| Privacy = confidential | Ollama | Local processing required |
| Requires shell/filesystem | Claude | Local IDE integration |
| Web/API calls | Codex | Cloud automation |
| Batch tagging/summarization | Ollama | Cheap parallel work |
| General tasks | Claude | Default choice |

## Cost Optimization

**Per 1000 notes:**
- Scan + Index: **$0** (local operations)
- Auto-tag (Ollama): **$0** (local model)
- Embeddings (OpenAI): **~$0.10-0.50** (depends on note length)

## Troubleshooting

### Ollama Not Available

```bash
# Check health
curl http://localhost:11434/api/tags

# If not running, start Ollama
ollama serve
```

### Import Errors

```bash
# Make sure dependencies are installed
cd /Users/ciarancox/Archon/python
uv sync --group agents --group server
```

### Supabase Connection Issues

```bash
# Verify credentials in .env
cat .env | grep SUPABASE
```

## Next Steps

1. **Run the full workflow** with auto-tagging
2. **Explore the generated index** at `<vault>/Archon/index.md`
3. **Query synced notes** via Archon's RAG system
4. **Customize tag schema** in `obsidian_tools.py`
5. **Create custom orchestrations** for other workflows

## Documentation

Full documentation: [docs/ORCHESTRATION.md](docs/ORCHESTRATION.md)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Orchestrator Agent                        │
│  - Plans tasks with routing decisions                       │
│  - Applies routing policy (privacy, cost, latency)          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Task Executor                            │
│  - Topological sort (dependency resolution)                 │
│  - Parallel execution where possible                        │
└─────────────────────────────────────────────────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │  Claude  │      │  Codex   │      │  Ollama  │
    │ Executor │      │ Executor │      │ Executor │
    └──────────┘      └──────────┘      └──────────┘
```

## Files Created

```
python/src/agents/
├── orchestrator_agent.py       # Main orchestrator with routing policy
├── ollama_client.py            # Ollama integration
├── task_executor.py            # Execution engine
├── obsidian_tools.py           # Vault scanning & tagging
└── archon_memory_sync.py       # Database sync

python/src/scripts/
└── orchestrate_obsidian_sync.py  # End-to-end workflow demo

docs/
├── ORCHESTRATION.md            # Full documentation
└── ORCHESTRATION_QUICK_START.md  # This file
```

---

**Ready to run!** Start with the dry-run to verify everything works, then execute the full workflow.
