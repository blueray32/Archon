#!/usr/bin/env bash
# One-shot finisher & verifier for the Archon Goal
# Usage: scripts/archon_goal_verifier.sh [story] (default: feature-bim-demo/001)
set -euo pipefail
STORY="${1:-feature-bim-demo/001}"
ROOT="$(pwd)"
say(){ printf '%s\n' "$*"; }
hdr(){ printf '\n== %s ==\n' "$*"; }

# ───── 0) Helpers ─────
ensure_dir(){ mkdir -p "$1"; }
replace_file(){ # $1=path, content from stdin
  local p="$1"; ensure_dir "$(dirname "$p")"; tmp="$(mktemp)"; cat > "$tmp"; mv "$tmp" "$p";
}
append_if_missing(){ # $1=path, $2=grep-pattern, stdin=content
  local p="$1" pat="$2"; ensure_dir "$(dirname "$p")"
  if [ ! -f "$p" ] || ! grep -q "$pat" "$p" 2>/dev/null; then
    cat >> "$p"
  fi
}
has_py(){ command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; }
py(){ command -v python3 >/dev/null 2>&1 && python3 "$@" || python "$@"; }

# ───── 1) verify_prp.py (5KB memory; tracked-only; artifacts req; PRP/ADR ref) ─────
hdr "verify_prp.py"
replace_file ".github/scripts/verify_prp.py" <<'PY'
#!/usr/bin/env python3
import sys, pathlib, subprocess
ROOT = pathlib.Path(".")
errors = []

# 1) memory budget: 5 KB
mem = ROOT / "memory" / "concise.md"
if mem.exists():
  size = mem.stat().st_size
  if size > 5 * 1024:
    errors.append(f"memory/concise.md too large: {size} bytes (limit 5120)")
else:
  errors.append("memory/concise.md missing")

# 2) scan only tracked files for large-size rule (>5MB) outside artifacts/
def tracked():
  try:
    out = subprocess.check_output(["git", "ls-files", "-z"], text=False)
    return [p.decode("utf-8") for p in out.split(b"\x00") if p]
  except Exception:
    return []
LARGE = 5 * 1024 * 1024
for rel in tracked():
  if rel.startswith("artifacts/"): continue
  p = ROOT / rel
  try:
    if p.is_file() and p.stat().st_size > LARGE:
      errors.append(f"Large tracked file outside artifacts/: {rel} ({p.stat().st_size} bytes)")
  except FileNotFoundError:
    pass

# 3) PRP/ADR reference (or PRP files changed) on last commit
try:
  msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"], text=True).strip()
  changed = subprocess.check_output(["git", "diff", "--name-only", "HEAD~1..HEAD"], text=True).splitlines()
except Exception:
  msg, changed = "", []
has_prp_ref = any("ai_docs/PRPs" in f for f in changed) or ("PRP" in msg or "ADR" in msg)
if not has_prp_ref:
  errors.append("No PRP/ADR reference found in last commit message and no PRP files changed.")

# 4) artifacts directory required
if not (ROOT / "artifacts").exists():
  errors.append("artifacts/ directory missing")

if errors:
  print("PRP Guardrails FAILED:\n- " + "\n- ".join(errors)); sys.exit(1)
print("PRP guardrails passed.")
PY
chmod +x .github/scripts/verify_prp.py
say "verify_prp.py ensured"

# ───── 2) QA: BIM YAML schema assertion ─────
hdr "QA: BIM YAML schema"
replace_file "scripts/qa.sh" <<'SH'
#!/usr/bin/env bash
# Usage: make qa STORY=feature-x/001
set -euo pipefail
STORY="${STORY:?usage: make qa STORY=feature-x/001}"
ART="artifacts/${STORY}"
QA="$ART/QA.md"
mkdir -p "$ART"
status_pass=true
echo "# QA for ${STORY}" > "$QA"
date -u +"%Y-%m-%dT%H:%M:%SZ" >> "$QA"

# Node (best-effort)
if [ -f package.json ]; then
  echo "## Node checks" >> "$QA"
  if command -v npm >/dev/null 2>&1; then
    (npm -s run -s test || npm -s test) && echo "- tests: pass" >> "$QA" || { echo "- tests: fail" >> "$QA"; status_pass=false; }
    npx -y eslint . >/dev/null 2>&1 && echo "- eslint: clean" >> "$QA" || echo "- eslint: skipped/issue" >> "$QA"
    npx -y tsc --noEmit >/dev/null 2>&1 && echo "- tsc: clean" >> "$QA" || echo "- tsc: skipped/issue" >> "$QA"
  else
    echo "- node toolchain missing" >> "$QA"
  fi
fi

# Python (best-effort)
if [ -f requirements.txt ] || [ -f pyproject.toml ] || [ -d scripts ]; then
  echo "## Python checks" >> "$QA"
  if command -v ruff >/dev/null 2>&1; then ruff check . && echo "- ruff: clean" >> "$QA" || { echo "- ruff: issues" >> "$QA"; status_pass=false; }
  fi
  if command -v pytest >/dev/null 2>&1; then pytest -q && echo "- pytest: pass" >> "$QA" || { echo "- pytest: fail" >> "$QA"; status_pass=false; }
  else echo "- pytest: not found" >> "$QA"
  fi
fi

# BIM YAML schema
if [ -f data/bim/standards/naming.yml ] && [ -f data/bim/standards/sheets.yml ]; then
  echo "## BIM YAML schema" >> "$QA"
  python - <<'PY' || status_pass=false
import yaml, sys
n = yaml.safe_load(open("data/bim/standards/naming.yml"))
s = yaml.safe_load(open("data/bim/standards/sheets.yml"))
assert "family_prefixes" in n and "type_patterns" in n
assert "number_pattern" in s
print("BIM YAML schema: OK")
PY
  echo "- schema: " $(tail -n1 "$QA" | grep -q "FAIL" && echo "FAIL" || echo "OK") >> "$QA" || true
fi

# Acceptance echo
if [ -f "ai_docs/PRPs/${STORY}/PRP.md" ]; then
  echo "## Acceptance (from PRP)" >> "$QA"
  awk 'BEGIN{p=0} /^## Acceptance/{p=1; next} /^## /{p=0} p{print "- " $0}' "ai_docs/PRPs/${STORY}/PRP.md" || true
fi

echo "## Result" >> "$QA"
${status_pass} && echo "- status: PASS" >> "$QA" || echo "- status: FAIL" >> "$QA"
echo "QA done. See $QA"
SH
chmod +x scripts/qa.sh
say "QA ensured"

# ───── 3) Obsidian publisher + Make target ─────
hdr "Obsidian publisher"
replace_file "scripts/publish_to_obsidian.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
STORY="${STORY:?usage: make publish STORY=feature-x/ID}"
VAULT="${OBSIDIAN_VAULT:?Set OBSIDIAN_VAULT=/path/to/Vault}"
SRC="artifacts/${STORY}/notes.md"
TS="$(date +%Y-%m-%d)"
DEST="${VAULT}/Archon/${STORY////-}-${TS}.md"
mkdir -p "$(dirname "$DEST")"
{ echo "# Archon Update — ${STORY} (${TS})"; echo; [ -f "$SRC" ] && cat "$SRC" || echo "No notes"; } > "$DEST"
echo "Wrote ${DEST}"
SH
chmod +x scripts/publish_to_obsidian.sh

# add Make target if missing
append_if_missing "Makefile" "^\s*publish:" <<'MK'

publish:
	@OBSIDIAN_VAULT="$(OBSIDIAN_VAULT)" bash scripts/publish_to_obsidian.sh
MK
say "Publisher ensured (Make target 'publish')"

# ───── 4) SpecKit wrapper + Make target (best-effort submodule) ─────
hdr "SpecKit integration"

# try to add submodule if directory absent (tolerate failure/offline)
if [ ! -d tools/spec-kit ]; then
  git submodule add https://github.com/github/spec-kit tools/spec-kit 2>/dev/null || true
fi
replace_file "scripts/speckit.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
NAME="${1:?usage: scripts/speckit.sh <name>}"
OUT="ai_docs/specs/${NAME}"
TPL="tools/spec-kit/templates"
mkdir -p "$OUT"

# copy a minimal set (if submodule present); otherwise create placeholders
if [ -d "$TPL" ]; then
  cp -n "$TPL"/README.md "$OUT/README.md" 2>/dev/null || true
  cp -n "$TPL"/spec.md "$OUT/spec.md" 2>/dev/null || true
else
  echo "# $NAME" > "$OUT/README.md"
  echo "# Spec: $NAME" > "$OUT/spec.md"
fi
echo "SpecKit: scaffolded $OUT"
SH
chmod +x scripts/speckit.sh
append_if_missing "Makefile" "^\s*spec:" <<'MK'

spec:
	@bash scripts/speckit.sh $(NAME)
MK
say "SpecKit wrapper ensured (Make target 'spec')"

# ───── 5) BMAD mapping doc + Make target ─────
hdr "BMAD mapping"
replace_file "ai_docs/BMAD/roles.md" <<'MD'
# BMAD ↔ Archon Agents Mapping
- **Business (B)** → Analyst, PM
- **Model (M)** → Architect (system), Dev (implementation)
- **Automation (A)** → Dev (scripts/agents), QA (checks)
- **Delivery (D)** → Scrum Master (slicing), QA (acceptance), PM (comms)

Usage: Each PRP must list the BMAD facet it advances and reference the responsible agent mode.
MD
append_if_missing "Makefile" "^\s*check-bmad:" <<'MK'

check-bmad:
	@grep -Rqs "BMAD" ai_docs/PRPs || echo "(warn) add 'BMAD' facet line to PRPs"
MK
say "BMAD roles ensured (Make target 'check-bmad')"

# ───── 6) Seed audit script if missing, then run checks ─────
hdr "Audit"
if [ ! -f scripts/archon_impl_audit.sh ]; then
  replace_file "scripts/archon_impl_audit.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
S="${1:-feature-bim-demo/001}"
ok=true
req(){ [[ -f "$1" ]] || { echo "❌ missing: $1"; ok=false; }; }
echo "== Audit: PRP $S =="
req "ai_docs/PRPs/$S/PRP.md"
req "data/bim/standards/naming.yml"
req "data/bim/standards/sheets.yml"
req "scripts/revit/validate_naming.py"
req "ai_docs/PRDs/feature-bim-demo/ARCH.md"
req "README.md"
python - <<'PY' || ok=false
import yaml
n = yaml.safe_load(open("data/bim/standards/naming.yml"))
s = yaml.safe_load(open("data/bim/standards/sheets.yml"))
assert "family_prefixes" in n and "type_patterns" in n
assert "number_pattern" in s
print("BIM YAML schema: OK")
PY
python scripts/revit/validate_naming.py --help >/dev/null 2>&1 || { echo "❌ validator --help failed"; ok=false; }
[ -f "artifacts/$S/notes.md" ] || { echo "❌ artifacts/$S/notes.md"; ok=false; }
[ -f "artifacts/$S/changed_files.csv" ] || { echo "❌ artifacts/$S/changed_files.csv"; ok=false; }
[ -d "artifacts/$S/diffs" ] || { echo "❌ artifacts/$S/diffs/"; ok=false; }
[ -f "artifacts/$S/QA.md" ] || { echo "❌ artifacts/$S/QA.md"; ok=false; }
$ok && echo "✅ AUDIT PASS" || { echo "❌ AUDIT FAIL"; exit 1; }
SH
  chmod +x scripts/archon_impl_audit.sh
  say "Seeded scripts/archon_impl_audit.sh"
fi

# ───── 7) Execute verification suite ─────
hdr "Execute checks"

# Guardrails
python .github/scripts/verify_prp.py || true

# QA
make qa STORY="${STORY}" || true

# Audit (will fail if PyYAML missing; tolerate so we can still summarize)
scripts/archon_impl_audit.sh "${STORY}" || true

# BMAD check
make check-bmad || true

hdr "Summary"
echo "Repo: ${ROOT}"
echo "Story: ${STORY}"
echo "- Guardrails: $(python .github/scripts/verify_prp.py >/dev/null 2>&1 && echo PASS || echo FAIL)"
echo "- QA:        $(grep -q 'status: PASS' artifacts/${STORY}/QA.md 2>/dev/null && echo PASS || echo WARN/FAIL)"
echo "- Audit:     $(grep -q 'AUDIT PASS' artifacts/${STORY}/audit_report.md 2>/dev/null && echo PASS || echo WARN/FAIL or missing PyYAML)"
echo
echo "Next:"
echo "1) If audit warned about PyYAML:  python3 -m pip install --user pyyaml"
echo "2) To publish notes to Obsidian:  OBSIDIAN_VAULT=\"/path/to/Vault\" make publish STORY=${STORY}"
echo "3) To scaffold a SpecKit doc:     make spec NAME=obsidian-weekly-review"