PY=uv run python
ROOT:=$(CURDIR)
VAULT?=$(ROOT)/vault
GOLDEN=$(ROOT)/python/golden_set_archon.json
PRED=$(ROOT)/artifacts/predictions_golden.json
API?=http://127.0.0.1:5050

.PHONY: help preflight preds unlabeled label label-auto label-csv merge-labels qa qa-seeded playwright api-start api-stop rag api mcp daily-log obsidian-audit

help:
	@echo "Targets:"
	@echo ""
	@echo "Daily Operations:"
	@echo "  api            - start API server on 8181 (standard port)"
	@echo "  mcp            - start MCP server on 8051"
	@echo "  daily-log      - create/update today's agent log"
	@echo "  obsidian-audit - audit vault for missing metadata"
	@echo ""
	@echo "Golden Set / Predictions:"
	@echo "  preflight      - check paths & files"
	@echo "  preds          - resume predictions for golden"
	@echo "  unlabeled      - list count/first 50 unlabeled notes in golden"
	@echo "  label          - interactive CLI to apply labels"
	@echo "  label-auto     - auto-fill labels from predictions for unlabeled notes"
	@echo "  label-csv      - write artifacts/golden_label_todo.csv (with suggestions)"
	@echo "  merge-labels   - merge CSV labels back into $(GOLDEN)"
	@echo "  qa             - run QA against REAL golden"
	@echo "  qa-seeded      - sanity QA using predictions-seeded copy"
	@echo ""
	@echo "Legacy/Tools:"
	@echo "  playwright     - install chromium for crawler"
	@echo "  api-start      - start API (uvicorn) on 127.0.0.1:5050 [legacy port]"
	@echo "  api-stop       - stop API"
	@echo "  rag Q='query'  - run a RAG query (default top_k=25, pass K=... to change)"

preflight:
	@test -f $(GOLDEN) && echo "✓ golden: $(GOLDEN)" || echo "✗ missing golden"
	@test -f $(PRED)   && echo "✓ predictions: $(PRED)" || echo "✗ missing predictions"
	@if [ -d "$(VAULT)" ]; then echo "✓ vault: $(VAULT)"; else echo "✗ missing vault (set VAULT=/path/to/vault)"; fi

preds:
	@test -d "$(VAULT)" || { echo "✗ missing vault at $(VAULT) (override with VAULT=/path/to/vault)"; exit 1; }
	cd $(ROOT)/python && $(PY) src/scripts/predict_for_golden.py \
	  --vault $(VAULT) --golden $(GOLDEN) --resume --save-every 8 --concurrency 4 \
	  --out $(PRED)
	@echo -n "pred count: "; jq 'length' $(PRED)

unlabeled:
	cd $(ROOT)/python && $(PY) -m src.scripts.golden_tools unlabeled

label:
	cd $(ROOT)/python && $(PY) -m src.scripts.golden_tools label

label-auto:
	cd $(ROOT)/python && $(PY) -m src.scripts.golden_tools label-auto

label-csv:
	cd $(ROOT)/python && $(PY) -m src.scripts.golden_tools label-csv
	@echo "→ Fill area/service/status columns, then: make merge-labels"

merge-labels:
	cd $(ROOT)/python && $(PY) -m src.scripts.golden_tools merge-labels

qa:
	cd $(ROOT)/python && $(PY) src/scripts/qa_harness.py \
	  --golden $(ROOT)/python/golden_set_archon.json --predictions $(PRED) --threshold 0.90 || true

qa-seeded:
	cd $(ROOT)/python && $(PY) -m src.scripts.golden_tools seed-golden
	cd $(ROOT)/python && $(PY) src/scripts/qa_harness.py \
	  --golden $(ROOT)/python/golden_seeded.json --predictions $(PRED) --threshold 0.90 || true

playwright:
	cd $(ROOT)/python && $(PY) -m playwright install chromium || true

api-start:
	@if ! pgrep -f "uvicorn .*src.server.main:app" >/dev/null; then \
		cd $(ROOT)/python && nohup uv run uvicorn src.server.main:app --host 127.0.0.1 --port 5050 > ../artifacts/uvicorn_5050.log 2>&1 & \
		echo "API starting on 127.0.0.1:5050 (log: artifacts/uvicorn_5050.log)"; \
	fi

api-stop:
	-pkill -f "uvicorn .*src.server.main:app" || true
	@echo "API stopped (if it was running)."

# Usage: make rag Q="your query" K=25
Q ?= Obsidian vault sync
K ?= 25
rag: api-start
	@SESSION=$$(curl -fsS -X POST $(API)/api/agent-chat/sessions \
	  -H 'Content-Type: application/json' -d '{"agent_type":"rag"}' | jq -r .session_id); \
	echo "SESSION=$$SESSION"; \
	curl -fsS -X POST $(API)/api/rag/query \
	  -H 'Content-Type: application/json' -H "X-Session-Id: $$SESSION" \
	  -d "$$(jq -nc --arg q '$(Q)' --argjson k $(K) '{query:$$q, top_k:$$k}')" | jq .

moc-plan:
	@MODE=plan VAULT_DIR="$(VAULT_DIR)" bash scripts/obsidian_moc_ops.sh

moc-apply:
	@MODE=apply VAULT_DIR="$(VAULT_DIR)" bash scripts/obsidian_moc_ops.sh

# Standard API server on port 8181
api:
	@echo "🚀 Starting Nexarch API server on http://127.0.0.1:8181"
	@if pgrep -f "uvicorn .*src.server.main:app.*8181" >/dev/null; then \
		echo "⚠️  API already running on port 8181"; \
		exit 0; \
	fi
	@export OBSIDIAN_VAULT="$(VAULT)" && \
		cd $(ROOT)/python && \
		nohup uv run uvicorn src.server.main:app --host 127.0.0.1 --port 8181 --reload \
		> ../artifacts/uvicorn_8181.log 2>&1 & \
		echo "✅ API started (log: artifacts/uvicorn_8181.log)"
	@sleep 2
	@curl -s http://127.0.0.1:8181/health | jq -r '.status' && echo "✅ Health check passed" || echo "⚠️  Health check failed"

# MCP server on port 8051
mcp:
	@echo "🔌 Starting Nexarch MCP server on http://127.0.0.1:8051"
	@if pgrep -f "python.*mcp_server" >/dev/null; then \
		echo "⚠️  MCP server already running"; \
		exit 0; \
	fi
	@cd $(ROOT)/python && \
		nohup uv run python -m src.mcp_server \
		> ../artifacts/mcp_server.log 2>&1 & \
		echo "✅ MCP server started (log: artifacts/mcp_server.log)"
	@sleep 2
	@curl -s http://127.0.0.1:8051/health && echo "" && echo "✅ MCP health check passed" || echo "⚠️  MCP health check failed"

# Create or update today's agent log
daily-log:
	@export OBSIDIAN_VAULT="$(VAULT)" && bash $(ROOT)/scripts/daily_agent_log.sh

# Audit Obsidian vault for missing metadata
obsidian-audit:
	@echo "📊 Auditing Obsidian vault for missing metadata..."
	@curl -s http://127.0.0.1:8181/api/obsidian/review/missing-tags | jq -r '"Total notes missing metadata: \(.total)"'
	@echo ""
	@echo "Run 'curl http://127.0.0.1:8181/api/obsidian/review/missing-tags | jq' for full list"
