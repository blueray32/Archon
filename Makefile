# Make targets for PRP/R‑D flow
.PHONY: review verify-prp context-bundle story dev qa ingest-vault export-summaries

review:
	@bash scripts/project_review.sh || echo "review script optional; skip if absent"

verify-prp:
	@python3 .github/scripts/verify_prp.py

context-bundle:
	@bash scripts/context_bundle.sh

# Agent mode helpers (wired via Archon buttons)
story:
	@bash scripts/story.sh $(ANALYST) $(ARCH) $(SM) $(F)

dev:
	@bash scripts/dev.sh $(STORY)

qa:
	@bash scripts/qa.sh $(STORY)

ingest-vault:
	@bash scripts/ingest_vault.sh

export-summaries:
	@bash scripts/export_summaries.sh

publish:
	@OBSIDIAN_VAULT="$$OBSIDIAN_VAULT" bash scripts/publish_to_obsidian.sh

spec:
	@bash scripts/speckit.sh $(NAME)

check-bmad:
	@grep -Rqs "BMAD" ai_docs/PRPs || echo "(warn) add 'BMAD' facet line to PRPs"
