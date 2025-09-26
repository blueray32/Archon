# Dev Mode — Implement via Claude Code (file tools)
## Mission
Implement a PRP as minimal, test‑covered diffs.

## Inputs
- `ai_docs/PRPs/<feature>/<id>/PRP.md`

## Steps
1) Plan: list intended file edits (small).
2) Implement code + tests.
3) Run lints/tests locally if available.
4) Update docs as required by PRP.
5) Emit artifacts:
   - `artifacts/<feature>/<id>/changed_files.csv`
   - `artifacts/<feature>/<id>/diffs/`
   - `artifacts/<feature>/<id>/notes.md`

## Guardrails
- Only open files named by the PRP.
- Keep diffs focused; no drive‑by refactors.
- Never commit secrets or large binaries.
