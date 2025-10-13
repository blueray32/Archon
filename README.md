# Nexarch

> **Neural Architecture System**
> Production-ready AI development infrastructure combining knowledge management, structured workflows, and autonomous agent execution.

Nexarch is a **neural nexus** that architects the connection between your **knowledge layer** (Obsidian) and **AI execution** (LLM agents) through **structured workflows** (PRP/R-D methodology), creating an intelligent system from idea to implementation.

Originally forked from [Archon](https://github.com/coleam00/Archon), Nexarch extends the core RAG + MCP architecture with production-grade integrations for professional development workflows.

---

## What Makes Nexarch Different

### 🧠 **Knowledge Integration**
- **Obsidian Vault Sync** - Bidirectional integration with automatic indexing
- **Daily Agent Logs** - Automated session tracking with MCP heartbeats
- **Metadata Governance** - Frontmatter schema enforcement (area/service/status)
- **Change Detection** - Hash-based deduplication prevents false re-indexing

### 🔄 **Structured Workflows (PRP/R-D)**
- **Agent Modes** - Analyst, PM, Architect, Scrum Master, Dev, QA roles
- **Story Execution** - Automated feature breakdown and task orchestration
- **Artifact Tracking** - Full paper trail (notes, diffs, changed files)
- **CI Guardrails** - GitHub Actions enforce PRP compliance

### 🏗️ **Domain Specialization**
- **BIM Integration** - Building Information Modeling with APS Data Exchange
- **YAML Standards** - Revit project naming and sheet standards
- **Industry Personas** - Specialized agents for architecture workflows

### 🤖 **Archon Core** (Upstream)
- **RAG Search** - Semantic + hybrid search with reranking
- **MCP Protocol** - Claude Code, Cursor, Windsurf integration
- **Multi-LLM Support** - OpenAI, Anthropic, Ollama, Google, Groq
- **Web Crawling** - Crawl4AI with junk filtering
- **Task Management** - Project/task/document versioning

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Node.js 18+ (for frontend development)
- Python 3.12+ (for local development)
- Obsidian (optional, for knowledge integration)

### 1. Clone and Setup
```bash
git clone https://github.com/blueray32/Archon.git nexarch
cd nexarch
cp .env.example .env

# Edit .env with your Supabase credentials
# SUPABASE_URL and SUPABASE_SERVICE_KEY required
```

### 2. Start Services
```bash
# Start all services (API, MCP, Frontend)
docker compose up -d

# Or use Make shortcuts
make dev-docker

# Frontend: http://localhost:3737
# API: http://localhost:8181
# MCP: http://localhost:8051
```

### 3. Configure Obsidian (Optional)
```bash
# Set vault path
export OBSIDIAN_VAULT="/path/to/your/vault"

# Install templates
./scripts/install_obsidian_templates.sh

# Start daily logging
make daily-log
```

See [QUICK_START.md](QUICK_START.md) for detailed setup and [OBSIDIAN_INTEGRATION.md](OBSIDIAN_INTEGRATION.md) for vault configuration.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Nexarch                       │
├─────────────────────────────────────────────────┤
│                                                 │
│  Knowledge Layer          Execution Layer       │
│  ┌──────────────┐        ┌──────────────┐     │
│  │  Obsidian    │◄──────►│ Agent Modes  │     │
│  │  Vault Sync  │        │ (PRP/R-D)    │     │
│  └──────────────┘        └──────────────┘     │
│         │                        │             │
│         ▼                        ▼             │
│  ┌──────────────────────────────────────┐     │
│  │   Archon Core (RAG + MCP)            │     │
│  │   - Supabase (pgvector)              │     │
│  │   - FastAPI Server                   │     │
│  │   - MCP Protocol Server              │     │
│  │   - React Frontend                   │     │
│  └──────────────────────────────────────┘     │
│         │                        │             │
│         ▼                        ▼             │
│  ┌──────────────┐        ┌──────────────┐     │
│  │   BIM Tools  │        │  Task Board  │     │
│  │   APS/Revit  │        │  Projects    │     │
│  └──────────────┘        └──────────────┘     │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Tech Stack
- **Backend:** Python 3.12, FastAPI, Supabase (PostgreSQL + pgvector)
- **Frontend:** React 18, TypeScript, Vite, TailwindCSS, TanStack Query
- **AI/ML:** OpenAI, Anthropic, Ollama, sentence-transformers
- **Crawling:** Crawl4AI, Playwright
- **Integration:** MCP Protocol, Obsidian filesystem watcher

---

## Key Features

### 📚 Knowledge Management
- RAG search across web crawls, documents, and Obsidian notes
- Semantic embeddings with optional reranking
- Hybrid search (vector + keyword) with BM25
- Source management with metadata tagging
- Contextual embeddings for better retrieval

### 🔨 Development Workflow
```bash
# Create feature story
make story ANALYST F=feature-name

# Plan architecture
make story ARCH F=feature-name

# Break into tasks
make story SM F=feature-name

# Execute tasks
make dev STORY=feature-name/001

# Quality assurance
make qa STORY=feature-name/001
```

### 📝 Daily Operations
```bash
make api              # Start API server (8181)
make mcp              # Start MCP server (8051)
make daily-log        # Create/update today's agent log
make obsidian-audit   # Check vault metadata health
```

### 🧪 Testing & Quality
```bash
make test             # Run all tests
make lint             # Run all linters
make test-fe          # Frontend tests only
make test-be          # Backend tests only
```

---

## Documentation

### Getting Started
- [Quick Start Guide](QUICK_START.md) - Daily operations and setup
- [Obsidian Integration](OBSIDIAN_INTEGRATION.md) - Vault sync configuration
- [Contributing Guide](CONTRIBUTING.md) - Development guidelines

### Architecture & Design
- [Claude Code Instructions](CLAUDE.md) - AI pair programming guide
- [Agent System](AGENTS.md) - PRP/R-D agent modes
- [PRP Documentation](PRPs/README.md) - Structured prompt methodology

### Specialized Workflows
- [BIM Integration](BIM_APS_SETUP_COMPLETE.md) - Architecture workflows
- [Weekly Review](PRPs/ai_docs/ARCHITECTURE.md) - Team rituals

---

## MCP Tools

Nexarch exposes tools via Model Context Protocol for AI assistants:

**Knowledge & Search**
- `perform_rag_query` - Search knowledge base with filtering
- `search_code_examples` - Find relevant code snippets
- `get_available_sources` - List indexed sources

**Project Management**
- `create_project` / `list_projects` / `get_project`
- `create_task` / `list_tasks` / `update_task`
- `create_document` / `list_documents` / `get_document`

**Obsidian Integration**
- `list_obsidian_metadata_gaps` - Audit vault frontmatter
- `update_obsidian_frontmatter` - Batch update metadata
- `index_obsidian_vault` - Sync vault to knowledge base

**Versioning**
- `create_version` / `list_versions` / `restore_version`

---

## Contributing

Nexarch is built for teams who need structured AI-augmented development workflows.

**We welcome:**
- 🐛 Bug reports and fixes
- 📚 Documentation improvements
- 🎨 UI/UX enhancements
- 🔌 New MCP tools and integrations
- 🏗️ Domain-specific extensions (like BIM)

**Before contributing:**
1. Read [CONTRIBUTING.md](CONTRIBUTING.md)
2. Check [existing issues](https://github.com/blueray32/Archon/issues)
3. Follow [CLAUDE.md](CLAUDE.md) coding standards
4. Ensure tests pass: `make test`

---

## Upstream Attribution

Nexarch is built on [Archon](https://github.com/coleam00/Archon) by [@coleam00](https://github.com/coleam00).

**Key upstream features we inherit:**
- RAG architecture and MCP protocol implementation
- Multi-provider LLM support (OpenAI, Anthropic, Ollama, etc.)
- Web crawling with Crawl4AI
- React frontend with TanStack Query
- Supabase integration

**Our extensions:**
- Obsidian vault bidirectional sync
- PRP/R-D structured workflow system
- BIM/APS domain integration
- Daily agent logging automation
- Production hardening (hash-based change detection, metadata governance)

We periodically sync critical upstream fixes (security, stability) while maintaining our distinct feature set.

See [ATTRIBUTION.md](ATTRIBUTION.md) for detailed upstream acknowledgments.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

**Note:** This project includes code from [Archon](https://github.com/coleam00/Archon), also under MIT License.

---

## Support & Community

- **Issues:** [GitHub Issues](https://github.com/blueray32/Archon/issues)
- **Discussions:** [GitHub Discussions](https://github.com/blueray32/Archon/discussions)
- **Documentation:** http://localhost:3737/ (when running)

---

## Roadmap

### Current Focus (Q1 2025)
- ✅ Obsidian production hardening
- ✅ PRP/R-D workflow automation
- ✅ BIM integration foundations
- 🔄 Metadata governance enforcement
- 🔄 Agent execution reliability

### Planned Features
- [ ] Multi-vault support (personal + team vaults)
- [ ] Agent performance metrics
- [ ] Task dependency visualization
- [ ] BIM model versioning
- [ ] Team collaboration features

---

**Built by [@blueray32](https://github.com/blueray32) | Powered by [Archon](https://github.com/coleam00/Archon)**
