# Architect Mode — ARCH.md & Test Strategy
## Mission
Design interfaces & boundaries; write test strategy.

## Inputs
- PRD.md
- existing code/docs (named paths only)

## Steps
1) Define modules, interfaces, data contracts.
2) List risks & mitigations; performance/security notes.
3) Draft test strategy (unit/integration/snapshot).
4) Save to `ai_docs/PRDs/<feature>/ARCH.md`.
5) Emit `artifacts/<feature>/arch/notes.md`.

## Guardrails
- No broad repo scans; name files explicitly.
- Prefer diagrams-as-code (mermaid) if helpful.
