# Archon + PRP/R‑D Starter

**Purpose:** a minimal, reproducible blueprint to run a PRP/R‑D workflow on top of **Archon**, with Obsidian as your narrative store and Claude Code as the execution engine.

## How it fits
- **Archon**: orchestrator, task board, MCP hubs
- **.claude/agents/**: agent *modes* (Analyst/PM/Architect/SM/Dev/QA)
- **ai_docs/**: PRDs, ARCH docs, PRPs, ADRs
- **artifacts/**: outputs per task (paper trail)
- **memory/concise.md**: tiny universal memory (CI limits size)
- **.github/workflows/**: CI guardrails

## Quickstart
```bash
# 1) add to a repo (top-level)
unzip archon-prp-starter.zip -d .
git add .
git commit -m "chore: add Archon + PRP starter"

# 2) local review (optional)
make review || true

# 3) run the flow (example feature)
make story ANALYST F=feature-weekly-review
make story ARCH F=feature-weekly-review
make story SM F=feature-weekly-review
make dev STORY=feature-weekly-review/001
make qa STORY=feature-weekly-review/001
```

## BIM Standards
[BIM naming and sheet standards](data/bim/standards/) - YAML-based standards for Revit projects

## Definition of Done (DoD) per story
- PR references a **PRP** and (optionally) an **ADR**
- `artifacts/<feature>/<story>/` exists with `notes.md`, `changed_files.csv`, `diffs/`
- Tests + lints green; CI guardrails pass
- Obsidian note updated when user-visible behavior changes

*Generated: 2025-09-26T23:11:47Z*
