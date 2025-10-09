# Hybrid Orchestration System

**Codex/Claude + Ollama** orchestration for Archon + Obsidian integration.

## Overview

The orchestration system implements **Reduce & Delegate (R&D)** principles to route tasks between:

1. **Cloud Claude** (local/IDE) - Filesystem ops, code edits, Obsidian notes, privacy-sensitive work
2. **Cloud Codex** (cloud) - Web APIs, batch automation, multi-service glue
3. **Local Ollama** (local models) - Cheap parallel LLM work (tagging, summarizing, extracting)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Orchestrator Agent                        │
│  - Plans tasks with routing decisions                       │
│  - Applies routing policy (privacy, cost, latency)          │
│  - Generates execution manifest                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Task Executor                            │
│  - Topological sort (dependency resolution)                 │
│  - Parallel execution where possible                        │
│  - Artifact management                                      │
└─────────────────────────────────────────────────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │  Claude  │      │  Codex   │      │  Ollama  │
    │ Executor │      │ Executor │      │ Executor │
    └──────────┘      └──────────┘      └──────────┘
```

## Components

### 1. Orchestrator Agent (`orchestrator_agent.py`)

**Purpose:** High-level task planning and routing decisions.

**Key Classes:**
- `OrchestratorAgent` - PydanticAI agent for plan generation
- `ExecutorType` - Enum for Claude, Codex, Ollama
- `Task` - Individual task with routing, dependencies, acceptance criteria
- `OrchestratorOutput` - Complete plan with tasks and metadata

**Routing Policy:**
1. **Privacy Guard** - Confidential data → Local (Ollama or Claude)
2. **Tooling** - Shell/filesystem → Claude
3. **Web/Cloud** - APIs, scraping → Codex
4. **Cheap Parallel** - Tagging, summarization → Ollama
5. **Default** - General tasks → Claude

### 2. Ollama Client (`ollama_client.py`)

**Purpose:** Integration with local Ollama models.

**Features:**
- Text generation with optional JSON schema
- Batch processing with concurrency control
- Model listing and health checks
- Async/await support

**Example:**
```python
from agents.ollama_client import OllamaClient

async with OllamaClient(base_url="http://localhost:11434") as client:
    result = await client.generate(
        model="qwen2.5:3b",
        prompt="Summarize this note...",
        system="You are a concise summarizer."
    )
```

### 3. Task Executor (`task_executor.py`)

**Purpose:** Execute orchestrated plans with dependency resolution.

**Features:**
- Topological sort for task ordering
- Parallel execution of independent tasks
- Progress tracking and callbacks
- Artifact management (saves outputs to `artifacts/`)
- Detailed execution reports

**Example:**
```python
from agents.task_executor import TaskExecutor, ExecutorConfig

config = ExecutorConfig(workspace_root="/path/to/workspace")
executor = TaskExecutor(config)

report = await executor.execute_plan(orchestrator_output)
print(f"Completed {report.tasks_completed}/{report.tasks_total} tasks")
```

### 4. Obsidian Tools (`obsidian_tools.py`)

**Purpose:** Vault scanning, tagging, and indexing.

**Features:**
- Scan entire vault and extract metadata
- Parse YAML frontmatter
- Update frontmatter programmatically
- Auto-tag notes using Ollama
- Create index notes (MOC)

**Example:**
```python
from agents.obsidian_tools import ObsidianTools

tools = ObsidianTools(vault_path="/Users/you/vault")
index = tools.scan_vault()

print(f"Found {index.notes_count} notes")
print(f"Tags: {index.tags_summary}")
```

### 5. Archon Memory Sync (`archon_memory_sync.py`)

**Purpose:** Sync Obsidian data into Archon's database for RAG.

**Features:**
- Store vault index as searchable document
- Index individual notes with embeddings
- Tag and area indexing
- Query synced notes

**Example:**
```python
from agents.archon_memory_sync import ArchonMemorySync

sync = ArchonMemorySync(supabase_client, embedding_service)
report = await sync.sync_vault_index(vault_index, create_embeddings=True)

print(f"Synced {report['synced_notes']} notes")
```

## Usage

### Quick Start: Obsidian Vault Sync

The `orchestrate_obsidian_sync.py` script demonstrates the full workflow:

```bash
# Dry run (plan only)
python python/src/scripts/orchestrate_obsidian_sync.py --vault /path/to/vault --dry-run

# Full sync
python python/src/scripts/orchestrate_obsidian_sync.py --vault /path/to/vault

# With auto-tagging (uses Ollama)
python python/src/scripts/orchestrate_obsidian_sync.py --vault /path/to/vault --auto-tag

# With embeddings (for RAG)
python python/src/scripts/orchestrate_obsidian_sync.py --vault /path/to/vault --create-embeddings

# Full workflow
python python/src/scripts/orchestrate_obsidian_sync.py \
  --vault /path/to/vault \
  --auto-tag \
  --create-embeddings
```

**Environment Variables:**
```bash
OBSIDIAN_VAULT=/Users/you/Documents/vault
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OPENAI_API_KEY=sk-...  # For embeddings
```

### Workflow Steps

The Obsidian sync workflow executes these tasks:

1. **T1: Scan Vault** (Claude)
   - Recursively scan all `.md` files
   - Extract frontmatter, tags, headings
   - Build vault index

2. **T2: Auto-Tag** (Ollama) - *Optional*
   - Batch process notes with Ollama
   - Classify by area (MEP, BIM, Revit, etc.)
   - Suggest service tags
   - Determine status

3. **T3: Update Frontmatter** (Claude) - *Optional*
   - Apply suggested tags to notes
   - Update `area`, `service`, `status` fields
   - Add `source: archon`, `updated: <timestamp>`

4. **T4: Sync to Archon** (Claude)
   - Store vault index in database
   - Index individual notes (with embeddings if enabled)
   - Create tag index
   - Generate MOC (Map of Content) note

### Outputs

All outputs are saved to `artifacts/obsidian_sync_<date>/`:

```
artifacts/obsidian_sync_2025-01-07/
├── vault_index.json           # Complete vault scan
├── tag_suggestions.json       # Ollama tag suggestions
├── archon_sync_report.json    # Database sync results
└── T1_output.json             # Task outputs
```

Plus in your Obsidian vault:
```
<vault>/Archon/index.md        # Master index note (MOC)
```

## Configuration

### Tag Schema

Default tag schema (customizable):

```python
TagSchema(
    area=["MEP", "BIM", "Revit", "NavisWorks", "Spanish", "Community"],
    service=["agents", "crawler", "mcp", "ui", "database"],
    status=["draft", "review", "published", "archived"],
    source=["archon", "manual", "imported"]
)
```

### Routing Policy Matrix

| Condition | Executor | Reason |
|-----------|----------|--------|
| Privacy = confidential | Ollama | Local processing required |
| Requires shell/filesystem | Claude | Local IDE integration |
| Web/API calls | Codex | Cloud automation |
| Batch tagging/summarization | Ollama | Cheap parallel work |
| General tasks | Claude | Default choice |

### Cost Optimization

The orchestrator minimizes cost by:
- Using Ollama for bulk operations (free, local)
- Batching Ollama calls with concurrency limits
- Only using cloud models when necessary
- Creating embeddings only when requested

**Estimated Costs (per 1000 notes):**
- Scan + Index: $0 (local)
- Auto-tag (Ollama): $0 (local)
- Embeddings (OpenAI): ~$0.10-0.50 (depends on note length)

## Advanced Usage

### Custom Orchestration

```python
from agents.orchestrator_agent import OrchestratorAgent, OrchestratorDependencies

# Create orchestrator
agent = OrchestratorAgent()

# Define dependencies
deps = OrchestratorDependencies(
    workspace_root="/path/to/workspace",
    obsidian_vault="/path/to/vault",
    max_cost=2.50,
    privacy_level="internal"
)

# Plan a custom task
plan = await agent.plan_task(
    goal="Extract all code examples from my vault and index them",
    deps=deps
)

# Execute plan
from agents.task_executor import TaskExecutor, ExecutorConfig

executor = TaskExecutor(ExecutorConfig(workspace_root="/path/to/workspace"))
report = await executor.execute_plan(plan)
```

### Direct Ollama Usage

```python
from agents.ollama_client import OllamaClient

async with OllamaClient() as client:
    # Check available models
    models = await client.list_models()

    # Generate text
    result = await client.generate(
        model="llama3.1",
        prompt="Explain Reduce & Delegate",
        system="You are a concise explainer."
    )

    # Batch processing
    prompts = ["Summarize note 1", "Summarize note 2", ...]
    results = await client.batch_generate(
        model="qwen2.5:3b",
        prompts=prompts,
        max_concurrent=5
    )
```

### Obsidian Frontmatter Updates

```python
from agents.obsidian_tools import ObsidianTools

tools = ObsidianTools("/path/to/vault")

# Update a note's frontmatter
tools.update_frontmatter(
    note_path=Path("vault/notes/my-note.md"),
    updates={
        "area": "BIM",
        "status": "review",
        "source": "archon",
        "tags": ["revit", "mep", "automation"]
    },
    merge=True  # Merge with existing frontmatter
)
```

## Requirements

### System Requirements
- Python 3.12+
- Ollama installed and running (for local execution)
- Supabase instance (for Archon memory sync)

### Python Dependencies
```bash
uv sync --group all  # Installs all dependencies
```

Key packages:
- `pydantic-ai` - Agent framework
- `httpx` - Async HTTP client
- `pyyaml` - YAML frontmatter parsing
- `supabase` - Database client

### Ollama Setup

1. Install Ollama: https://ollama.ai
2. Pull recommended models:
```bash
ollama pull qwen2.5:3b      # Fast, good quality
ollama pull llama3.1        # Larger, better quality
ollama pull nomic-embed-text # For embeddings (optional)
```

3. Verify health:
```bash
curl http://localhost:11434/api/tags
```

## Troubleshooting

### Ollama Connection Issues

```python
from agents.ollama_client import OllamaClient

async with OllamaClient() as client:
    healthy = await client.health_check()
    if not healthy:
        print("Ollama not running. Start with: ollama serve")
```

### Frontmatter Parsing Errors

If notes have malformed YAML, the parser will skip them with a warning:
```
WARNING - Failed to parse frontmatter: ...
```

Fix the YAML manually or use a validator.

### Database Sync Errors

Check Supabase credentials:
```bash
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_KEY
```

Ensure `prp_docs` table exists with required columns.

## Testing

Run the dry-run to validate the workflow without executing:

```bash
python python/src/scripts/orchestrate_obsidian_sync.py \
  --vault $OBSIDIAN_VAULT \
  --dry-run
```

Expected output:
```json
{
  "dry_run": true,
  "plan": {
    "goal": "Index Obsidian vault...",
    "tasks": [...]
  }
}
```

## Next Steps

1. **Integrate with MCP** - Expose orchestration as MCP tools
2. **Add SharePoint sync** - Sync vault to SharePoint
3. **Code extraction** - Extract code blocks from notes
4. **Cross-vault linking** - Link related notes across vaults
5. **Excalidraw parsing** - Index Excalidraw diagrams

## References

- [Orchestrator Agent](../python/src/agents/orchestrator_agent.py)
- [Ollama Client](../python/src/agents/ollama_client.py)
- [Task Executor](../python/src/agents/task_executor.py)
- [Obsidian Tools](../python/src/agents/obsidian_tools.py)
- [Archon Memory Sync](../python/src/agents/archon_memory_sync.py)
- [Workflow Script](../python/src/scripts/orchestrate_obsidian_sync.py)
