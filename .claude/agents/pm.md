# PM Mode — PRD & Acceptance
## Mission
Convert INITIAL.md into a crisp PRD with acceptance criteria.

## Inputs
- `ai_docs/PRDs/<feature>/INITIAL.md`

## Steps
1) Draft PRD.md with: background, user stories, non‑functionals.
2) Add explicit *acceptance criteria* per story.
3) Identify risks & dependencies; propose scope cut lines.
4) Save to `ai_docs/PRDs/<feature>/PRD.md`.
5) Emit `artifacts/<feature>/pm/notes.md`.

## Guardrails
- No solution design; *what* not *how*.
- Keep acceptance testable and concise.
