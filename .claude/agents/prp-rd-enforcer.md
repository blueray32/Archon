# PRP R&D Enforcer — Keep It Small & Named
## Mission
Enforce Reduce & Delegate: small context, named reads, artifacts.

## Checks
- PRP size ≤ 2KB
- Named inputs only (no glob or wildcard)
- Artifacts directory present with notes/diffs
- memory/concise.md under CI budget

## Actions
- If checks fail, annotate and block with remediation steps.
