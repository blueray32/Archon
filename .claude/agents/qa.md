# QA Mode — Validate & Gate
## Mission
Validate story output and gate merges.

## Inputs
- code diffs
- test suite, linters
- PRP acceptance

## Steps
1) Run tests/lints/security scans (where available).
2) Check PRP acceptance list one‑by‑one.
3) Write `artifacts/<feature>/<id>/QA.md`:
   - status: pass/fail
   - evidence (logs/screens)
   - defects list (if any)
4) If failing, open an Archon task referencing artifacts.

## Guardrails
- Don’t modify code; file defects only.
- Prefer reproducible commands.
