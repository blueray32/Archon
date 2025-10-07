# PRP — Building Information Modeling (BIM) Agent

**Owner:** Ciaran / Archon Agents
**Version:** 1.0 (2025-10-06)
**Primary LLM:** GPT-4o-mini (or vendor-selectable)
**Surfaces:** Web UI, REST API, MCP Tools, CLI
**Goal:** An AI agent that **understands**, **queries**, and **validates** BIM models by ingesting **Autodesk Platform Services (APS) Data Exchange** (Revit) data and related documents via **Docling** and RAG.

---

## 0) Problem → Intent → Outcomes

**Problem.** BIM projects produce large, fragmented data (RVT, schedules, specs, PDFs). Teams struggle to query, cross-check, and explain model state without heavy manual steps.

**Intent.** Provide a reproducible agent that:

* pulls **selective** Revit model data via **APS Data Exchange**;
* converts/organizes it into **LLM-friendly chunks** using **Docling**;
* answers questions, produces schedules/metrics, and runs **QA/Compliance checks**;
* creates structured **issues** (BCF) and **reports**.

**Expected Outcomes.**

1. **Fast Q&A** over model data (elements, properties, systems, levels).
2. **Actionable QA/QC** (missing/invalid params, out-of-range sizes).
3. **Light compliance** checks (rule-based prompts + references) with clear **limitations**.
4. **Exportable artifacts**: CSV/Markdown summaries, BCF issues, JSON results.
5. **Repeatable pipeline** with env-based config, logs, tests, and acceptance criteria.

**Non-Goals.**

* Full geometry reasoning or clash detection from meshes (Data Exchange GraphQL returns **metadata**, not raw meshes).
* Legal certification of code compliance; this agent provides **assistive analysis** only.

---

## 1) Architecture Overview

```
Revit → APS Data Exchange (Connector) → APS GraphQL API → JSON (elements/props)
       → ETL Normalize/Flatten → Markdown/CSV (tabular summaries) → Docling
       → Chunking (hierarchical/hybrid) → Embeddings → Vector DB (metadata)
       → Retrieval + LLM Prompts (Q&A / QA / Summaries / Reports)
       → Optional: BCF Issues, CSV/MD Exports, Dashboards
```

**Key components.**

* **APS Data Exchange**: selective model slices as element + property JSON via GraphQL.
* **ETL**: flatten JSON → normalized tables (by Category/Level/System). Units harmonized.
* **Docling**: converts CSV/Markdown into structured DoclingDocument; robust table handling.
* **RAG**: chunk + embed; store in **Vector DB** with rich **metadata** for filters.
* **Agent**: tool-augmented LLM with prompt templates (Q&A, QA, compliance, reporting).
* **Issue out**: optional **BCF** packages for human/authoring-tool replay.

---

## 2) Data Contracts & Sources

### 2.1 APS Data Exchange

* **Auth**: 3-legged OAuth; scopes typically `data:read`, `account:read`.
* **Endpoint**: `POST https://developer.api.autodesk.com/datacore/v1/graphql`
* **Exchange identifier**: `exchangeId` (URN/ID chosen when publishing from Revit Connector).
* **Returned**: elements list + property name/value pairs; **no mesh** via GraphQL.

**GraphQL minimal query.**

```graphql
query GetExchange($id: String!) {
  exchange(exchangeId: $id) {
    id
    name
    elements(pagination: { pageSize: 500 }) {
      results {
        id
        name
        properties { results { name value } }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
```

**Pagination pattern.** Keep fetching while `hasNextPage` is true with `after: endCursor`.

### 2.2 ETL Schemas (flattened)

**Element record (JSONL/CSV).**

```json
{
  "uid": "ExchangeElem-12345",
  "category": "Walls",
  "family": "Basic Wall",
  "type": "200mm Concrete",
  "level": "Level 2",
  "system": "Ducts-Supply",
  "params": {
    "Width": "0.20 m",
    "Height": "2.80 m",
    "FireRating": "60 min",
    "Mark": "W-203"
  }
}
```

**Normalization rules.**

* Units → metric base (m, mm) with numeric column mirrors (e.g., `height_m = 2.8`).
* Booleans/Enums → normalized strings.
* Stable keys: prefer `id`/`uid` from APS elements; keep a `source_exchange_id`.

---

## 3) Pipelines (Scripts) — Reference Implementations

### 3.1 Pull & Flatten (Python)

**Location:** `python/src/scripts/bim/aps_fetch_elements.py`

```python
import os, requests, json
from collections import defaultdict

TOKEN = os.environ["APS_ACCESS_TOKEN"]
EXCHANGE_ID = os.environ["APS_EXCHANGE_ID"]
ENDPOINT = "https://developer.api.autodesk.com/datacore/v1/graphql"

Q = """
query GetExchange($id: String!, $after: String) {
  exchange(exchangeId: $id) {
    id
    elements(pagination: { pageSize: 500, after: $after }) {
      results { id name properties { results { name value } } }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

def run(after=None):
  r = requests.post(ENDPOINT, json={"query": Q, "variables": {"id": EXCHANGE_ID, "after": after}},
                    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
  r.raise_for_status()
  return r.json()["data"]["exchange"]["elements"]

def flatten(elem):
  props = {p["name"]: p["value"] for p in elem.get("properties", {}).get("results", [])}
  return {
    "uid": elem["id"],
    "name": elem.get("name"),
    "category": props.get("Category") or props.get("Category Name"),
    "family": props.get("Family"),
    "type": props.get("Type"),
    "level": props.get("Level"),
    "system": props.get("System"),
    "params": props
  }

out_path = os.environ.get("BIM_FLAT_JSONL", "./out/elements.jsonl")
os.makedirs(os.path.dirname(out_path), exist_ok=True)

cursor = None
with open(out_path, "w", encoding="utf-8") as f:
  while True:
    chunk = run(after=cursor)
    for e in chunk["results"]:
      f.write(json.dumps(flatten(e)) + "\n")
    if not chunk["pageInfo"]["hasNextPage"]:
      break
    cursor = chunk["pageInfo"]["endCursor"]
print("Wrote:", out_path)
```

### 3.2 CSV/Markdown Summaries (Python)

**Location:** `python/src/scripts/bim/generate_summaries.py`

```python
import json, csv, os
from pathlib import Path

src = Path("./out/elements.jsonl")
csv_path = Path("./out/elements.csv")
md_path  = Path("./out/elements.md")

rows = []
with src.open() as f:
  for line in f:
    rec = json.loads(line)
    rows.append([rec.get("uid"), rec.get("category"), rec.get("family"), rec.get("type"), rec.get("level"), rec.get("system")])

os.makedirs(csv_path.parent, exist_ok=True)
with csv_path.open("w", newline="", encoding="utf-8") as f:
  w = csv.writer(f)
  w.writerow(["uid","category","family","type","level","system"])
  w.writerows(rows)

with md_path.open("w", encoding="utf-8") as f:
  f.write("| uid | category | family | type | level | system |\n|---|---|---|---|---|---|\n")
  for r in rows:
    f.write("| " + " | ".join(x or "" for x in r) + " |\n")
print("Wrote:", csv_path, md_path)
```

### 3.3 Docling Convert → Chunks → Index

**Location:** `python/src/scripts/bim/docling_index.py`

```python
# pip install docling
from docling.document_converter import DocumentConverter
from docling.pipeline.standard import DefaultPipeline
from docling.chunking import HierarchicalChunker

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# 1) Convert CSV/MD to DoclingDocument
conv = DocumentConverter(DefaultPipeline())
res_csv = conv.convert("./out/elements.csv")
res_md  = conv.convert("./out/elements.md")

# 2) Serialize to text (Docling can also produce rich JSON/DocTags)
text_csv = res_csv.document.export_to_markdown()
text_md  = res_md.document.export_to_markdown()

# 3) Chunking (choose one: Docling chunkers or LangChain splitters)
splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=120)
chunks = splitter.create_documents([text_csv + "\n" + text_md], metadatas=[{"source":"aps_exchange"}])

# 4) Embeddings + Vector store
emb = OpenAIEmbeddings(model="text-embedding-3-large")
vs = Chroma.from_documents(chunks, emb, collection_name="bim")

# Save persistently by supplying persist_directory="./vectordb"
```

---

## 4) Agent Tools & Contracts

### 4.1 Tool: `aps_exchange_fetch`

**Purpose:** Pull exchange data (paginated) and write `elements.jsonl`.

```json
{
  "name": "aps_exchange_fetch",
  "args": {
    "exchange_id": "string",
    "filters": {
      "category": ["Walls", "Doors"],
      "level": ["Level 1", "Level 2"],
      "property_equals": {"FireRating": "60 min"}
    }
  },
  "returns": {"path": "./out/elements.jsonl", "count": 1234}
}
```

**Notes:** Filtering can be pre/post-fetch depending on GraphQL support.

### 4.2 Tool: `rag_search`

**Purpose:** Retrieve top-k chunks with optional metadata filters.

```json
{
  "name": "rag_search",
  "args": {
    "query": "string",
    "k": 8,
    "filter": {"category": "Doors", "level": "Level 2"}
  },
  "returns": {"chunks": [{"text":"...","metadata":{"category":"Doors","level":"Level 2"}}]}
}
```

### 4.3 Tool: `summarize_group`

**Purpose:** Summarize by **Category/Level/System/Room**.

```json
{
  "name": "summarize_group",
  "args": {"group_by": "Level", "value": "Level 1", "metrics": ["count","area","length"]},
  "returns": {"summary_markdown": "string"}
}
```

### 4.4 Tool: `bcf_create`

**Purpose:** Emit BCF issue packages (XML/JSON) for triage.

```json
{
  "name": "bcf_create",
  "args": {"title": "Door missing FR", "element_ids": ["uid1","uid2"], "comments": "..."},
  "returns": {"path": "./out/issues/issue_001.bcfzip"}
}
```

---

## 5) Prompting (System + Templates)

### 5.1 System Prompt (BIM Specialist)

> You are a **BIM Specialist** AI. Use only the provided context and tools. If data is missing or uncertain, say so. Prefer **structured outputs** (tables, bullet lists, JSON). Be explicit about **assumptions** and **limitations** (e.g., no mesh geometry via Data Exchange GraphQL).
>
> **Priorities:** correctness > completeness > speed. Normalize units to metric; report both numeric and source text where possible. When raising issues, suggest **BCF** outputs.

### 5.2 RAG Q&A Template

```
Context:
{context}

User question:
{question}

Instructions:
- Answer using only the context. Cite element IDs.
- If context insufficient, request APS fetch with filters.
- Return a short summary first, then details.
```

### 5.3 QA/Compliance Template

```
Context:
{context}

Rule set:
- Minimum door width for egress: 0.9 m (example)
- Fire door rating on escape routes: ≥60 min

Task:
- Check elements for rule compliance; list violations with element IDs.
- Output JSON report with fields: element_id, rule, observed_value, expected, status.
```

---

## 6) Use-Cases (Supported Tasks)

* **Element queries:** counts, lists, find by param/type/system/level.
* **Schedules:** door/window/fixture summaries (CSV/MD).
* **QA/QC:** missing params, zero lengths, out-of-range dimensions.
* **Light compliance:** rule-prompted checks (declare limits; not legal advice).
* **Issues:** generate **BCF** for review/workflow tools.
* **Narrative summaries:** per Level/System/Space.

**Limitations:** No mesh geometry; spatial relationships inferred from metadata only (unless enriched separately). For true clash or path analysis, integrate a geometry service later.

---

## 7) Evaluation & Acceptance Criteria

**Gold-set Queries (must pass):**

1. *"How many 1.0 m doors on Level 1?"* → integer; list element IDs.
2. *"List all ducts on Level 2 with diameter > 250 mm."* → table; counts.
3. *"Which walls lack FireRating?"* → table + BCF option.
4. *"Summarize lighting fixtures per room on Level 1."* → grouped metrics.
5. *"Are any corridor doors under 0.9 m clear width?"* → JSON violations.

**Quality thresholds:**

* Accuracy ≥ 95% on gold-set.
* Latency ≤ 8s (cached), ≤ 20s (cold).
* Deterministic formatting for JSON reports (schema-validated).

---

## 8) Operations & Config

**Env vars (required):**

```
APS_CLIENT_ID=...
APS_CLIENT_SECRET=...
APS_ACCESS_TOKEN=...        # or fetch via OAuth at runtime
APS_EXCHANGE_ID=...
VECTOR_DB_DIR=./vectordb
OPENAI_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
SUPABASE_ANON_KEY=...
```

**Embed PRPs:**

```bash
uv run python -m src.scripts.prp_embed_sync
```

**Persona insert (Supabase REST):**

```bash
set -a; source .env; set +a
curl -s "$SUPABASE_URL/rest/v1/prp_personas" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: resolution=merge-duplicates" \
  -d @- <<'JSON'
[{
  "name":"bim_specialist",
  "display_name":"BIM Specialist",
  "description":"Expert BIM persona for AEC workflows (APS Data Exchange + Docling).",
  "system_prompt":"You are a BIM Specialist AI. Use only the provided context and tools. If data is missing or uncertain, say so. Prefer structured outputs (tables, bullet lists, JSON). Be explicit about assumptions and limitations (e.g., no mesh geometry via Data Exchange GraphQL). Priorities: correctness > completeness > speed. Normalize units to metric; report both numeric and source text where possible. When raising issues, suggest BCF outputs.",
  "configuration": {"temperature":0.2},
  "is_active": true
}]
JSON
```

**Service hints:**

* Persist vector DB (`persist_directory`) for warm starts.
* Cache APS fetch results per `exchangeId` + filter hash.
* Log tool I/O (sanitized) for observability.

---

## 9) Security & Compliance

* **Data minimization:** request **only** needed elements via Data Exchange.
* **Token hygiene:** store APS tokens securely; short TTL; rotate keys.
* **PII:** scrub comments/notes before indexing; configurable redaction.
* **Audit:** log query + retrieved chunk IDs; keep reproducible trails.

---

## 10) Change Management

* **Versioning:** increment PRP version on prompt/tool/schema changes.
* **Rollback:** keep previous vector snapshots + PRP versions.
* **Changelog:**

  * v1.0: First complete APS + Docling PRP, tool contracts, prompts, tests.

---

## 11) Quickstart Recipes

### Q1) Fresh Index from APS

1. Set `APS_*` envs; run **3.1** (pull) → `out/elements.jsonl`.
2. Run **3.2** to produce `elements.csv`, `elements.md`.
3. Run **3.3** to build vector index.
4. Call agent: Q&A or QA template with retrieval.

### Q2) QA Check: FireRating

* Retrieve **Walls/Doors** chunks; check for `FireRating` present & ≥ threshold.
* If violations: `bcf_create` with element IDs + comment.

### Q3) Schedules

* `summarize_group` by Level/Category → CSV/MD export for sheet insertion.

---

## 12) Example Agent Call (REST)

```bash
cat > /tmp/bim_query.json <<'JSON'
{
  "agent_type": "prp",
  "prompt": "List all doors on Level 1 with width >= 0.9 m; return JSON table.",
  "context": {"session_id": "bim-demo", "persona_name": "bim_specialist"}
}
JSON
curl -s -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" -d @/tmp/bim_query.json | jq
```

---

## 13) Appendix

### A) JSON Violation Report Schema

```json
{
  "exchange_id": "string",
  "rule_set": "string",
  "generated_at": "ISO8601",
  "violations": [
    {"element_id": "string", "rule": "string", "observed": "any", "expected": "any", "status": "fail"}
  ]
}
```

### B) BCF Issue Note (minimal JSON)

```json
{
  "title": "Door width under 0.9 m",
  "comment": "Increase clear width per rule X.",
  "element_ids": ["uid-1","uid-2"],
  "priority": "High"
}
```

### C) Few-Shot Q&A

**Q:** How many 1.0 m doors on Level 1?
**A (short):** 14 doors.
**A (details):** IDs: D-101, D-102, … (table).

**Q:** Which walls lack FireRating?
**A:** 6 walls (IDs …). Suggest BCF issue; see JSON report.

---

**End of PRP**
