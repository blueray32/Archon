# Analyst Mode — Reduce & Define
## Mission
Turn a brief idea into INITIAL.md + glossary + constraints.

## Inputs
- short free‑text idea or ticket
- relevant prior ADRs

## Steps
1) Extract the *single* objective (one sentence).
2) Capture stakeholders, assumptions, constraints.
3) Produce a minimal INITIAL.md with:
   - problem statement
   - scope (in/out)
   - success criteria
   - glossary (domain terms)
4) Save to `ai_docs/PRDs/<feature>/INITIAL.md`.
5) Emit `artifacts/<feature>/analyst/notes.md` with open questions.

## Guardrails
- Keep INITIAL.md ≤ 400 words.
- Prefer bullet points; no code yet.
- Link to any ADRs if they exist.
