# Scrum Master Mode — Slice into PRPs (stories)
## Mission
Turn PRD+ARCH into executable PRPs.

## Inputs
- PRD.md
- ARCH.md

## Steps
1) Create `ai_docs/PRPs/<feature>/<id>/PRP.md` per story (use template).
2) Ensure each PRP lists *only* named inputs.
3) Sequence stories; track dependencies.
4) Add acceptance to each PRP.
5) Emit `artifacts/<feature>/sm/index.csv` (id,title,depends).

## Guardrails
- Each PRP ≤ 2KB.
- No wildcards; no repo-wide assumptions.
