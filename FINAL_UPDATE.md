# Pipeline Results (QA & RAG)

- Predictions: **200/200** note predictions present; **meta keys** in golden: 4.
- QA (real golden): likely low F1 because **200** notes have empty labels (area/service/status).
- QA (seeded golden): evaluator wiring OK (should pass).
- Playwright: installed (chromium); crawler warnings should be gone on next boot.
- RAG: endpoint healthy; queries returned **success: true** (results may be empty; try higher `top_k` or broader queries).

Next steps:
1. Label the real golden (`python/golden_set_archon.json`) — aim for ≥0.90 F1.
2. If RAG results are sparse, increase `top_k` (e.g., 25–50) and verify embeddings exist for target notes.
3. (Optional) Add Make targets (`make qa`, `make rag`, `make unlabeled`) for one-liners.
