# Attribution & Acknowledgments

## Upstream Project: Archon

Nexarch is built upon [Archon](https://github.com/coleam00/Archon), an open-source AI coding assistant command center created by [@coleam00](https://github.com/coleam00).

**Archon Repository:** https://github.com/coleam00/Archon
**License:** MIT License
**Original Author:** Cole Medin ([@coleam00](https://github.com/coleam00))

---

## What We Inherit from Archon

### Core Architecture
- **RAG (Retrieval-Augmented Generation)** system with Supabase + pgvector
- **MCP (Model Context Protocol)** implementation for AI assistant integration
- **Multi-LLM Provider Support** - OpenAI, Anthropic, Ollama, Google Gemini, Groq
- **Web Crawling** infrastructure powered by Crawl4AI
- **FastAPI backend** with HTTP polling architecture
- **React + TypeScript frontend** with TanStack Query
- **Docker Compose** orchestration for microservices

### Key Features
- Semantic search with vector embeddings (OpenAI text-embedding-3-small)
- Hybrid search combining vector similarity with BM25 keyword search
- Optional reranking with sentence-transformers
- Contextual embeddings for improved retrieval
- Document processing (PDF, DOCX, Markdown)
- Source management with crawl status tracking
- Settings UI for LLM provider configuration
- Knowledge base browsing and exploration

### Technical Components
- **Database:** Supabase (PostgreSQL with pgvector extension)
- **Backend Services:**
  - Main Server (port 8181) - FastAPI with business logic
  - MCP Server (port 8051) - Lightweight protocol server
  - Agents Service (port 8052) - PydanticAI agents (optional)
- **Frontend:** Vite + React with Tron-inspired glassmorphism UI
- **Testing:** Pytest (backend), Vitest (frontend)
- **Linting:** Ruff + MyPy (Python), Biome + ESLint (TypeScript)

---

## Nexarch Extensions

### Original Contributions (Not in Upstream)

**Obsidian Integration (Production-Grade)**
- Bidirectional vault synchronization
- Hash-based change detection (prevents false re-indexing)
- Frontmatter metadata governance (area/service/status schema)
- Filesystem watcher with safe event loop coordination
- Daily agent logging with MCP heartbeat tracking
- Templater template system for structured notes
- Metadata audit and batch update MCP tools

**PRP/R-D Workflow System**
- Agent mode definitions (Analyst, PM, Architect, SM, Dev, QA)
- Story-driven task execution framework
- Artifact tracking (notes, diffs, changed files)
- CI guardrails via GitHub Actions
- Automated feature breakdown and orchestration
- Integration with Claude Code slash commands

**BIM (Building Information Modeling)**
- APS (Autodesk Platform Services) Data Exchange integration
- BIM-specific agent persona
- YAML-based standards for Revit projects
- Industry-specific workflow templates

**Production Hardening**
- 768D embedding migration for Ollama compatibility
- Tag normalization (scalar/array frontmatter handling)
- Deletion handler in filesystem watcher
- Makefile shortcuts for daily operations
- MCP config for multiple server orchestration

---

## Upstream Sync Strategy

### Our Approach
Nexarch maintains a **selective sync** strategy with upstream Archon:

**What We Cherry-Pick:**
- ✅ Security fixes
- ✅ Critical bug fixes (container issues, database timeouts)
- ✅ Stability improvements (Playwright paths, race conditions)
- ✅ Core RAG/MCP enhancements

**What We Don't Sync:**
- ❌ UI refactoring (we have custom pages for Obsidian, BIM, PRP)
- ❌ Features conflicting with our extensions
- ❌ Provider discovery changes (we have custom integrations)

**Sync Frequency:** Quarterly review of upstream changes

### Recent Upstream Fixes Applied
*See commit history for specific cherry-picks*

**2025-01-12:**
- Container race condition fix (02e72d9)
- Playwright browser path fix (3168c8b)

---

## Third-Party Dependencies

### Direct Upstream Archon Dependencies
All Python and JavaScript dependencies listed in `pyproject.toml` and `package.json` were inherited from Archon and are covered by their respective licenses.

### Additional Dependencies Added by Nexarch
- **watchdog** - Python filesystem monitoring (MIT License)
- **pydantic-ai** - Enhanced agent framework (MIT License)

---

## License

Both Nexarch and Archon are released under the **MIT License**.

**Key Points:**
- ✅ Free to use, modify, and distribute
- ✅ Commercial use permitted
- ✅ Attribution to both Nexarch and Archon required
- ✅ No warranty provided

See [LICENSE](LICENSE) file for full text.

---

## Community Contributions

### Archon Community
We gratefully acknowledge the Archon community's contributions to the upstream project that made Nexarch possible.

### Nexarch Contributors
*Future contributors will be listed here*

---

## Contact & Resources

**Nexarch:**
- Repository: https://github.com/blueray32/Archon
- Issues: https://github.com/blueray32/Archon/issues
- Maintainer: [@blueray32](https://github.com/blueray32)

**Upstream Archon:**
- Repository: https://github.com/coleam00/Archon
- Issues: https://github.com/coleam00/Archon/issues
- Creator: [@coleam00](https://github.com/coleam00)

---

## Acknowledgments

**Special thanks to:**
- **Cole Medin ([@coleam00](https://github.com/coleam00))** - For creating Archon and making it open source
- **Archon Contributors** - For building the foundation we extended
- **Anthropic** - For Claude and the MCP protocol
- **Obsidian** - For the knowledge management inspiration

---

*This attribution document is maintained to ensure proper credit to all contributors and upstream projects that made Nexarch possible.*

*Last Updated: 2025-01-12*
