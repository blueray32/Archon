#!/usr/bin/env bash
# Archon implementation audit — checks the BIM PRP slice and guardrails
# Usage: scripts/archon_impl_audit.sh [feature-x/ID] (default: feature-bim-demo/001)
set -euo pipefail

STORY="${1:-feature-bim-demo/001}"
ROOT="$(pwd)"
ART="artifacts/${STORY}"
mkdir -p "$ART"

# Choose python interpreter
PYBIN="$(command -v python3 || command -v python || true)"
if [ -z "${PYBIN}" ]; then
  echo "⚠️  No python interpreter found; YAML checks will be skipped." >&2
fi

pass=true
summary_lines=()

section() { echo "== $1 =="; }
req_file() { if [ ! -f "$1" ]; then echo "❌ missing: $1"; pass=false; else echo "✅ $1"; fi; }
req_dir()  { if [ ! -d "$1" ]; then echo "❌ missing dir: $1"; pass=false; else echo "✅ $1/"; fi; }

section "PRP & Named Files"
req_file "ai_docs/PRPs/${STORY}/PRP.md"
req_file "data/bim/standards/naming.yml"
req_file "data/bim/standards/sheets.yml"
req_file "scripts/revit/validate_naming.py"
req_file "ai_docs/PRDs/feature-bim-demo/ARCH.md"
req_file "README.md"

section "Docs sanity"
if grep -q "## Naming Standards" ai_docs/PRDs/feature-bim-demo/ARCH.md 2>/dev/null; then
  echo "✅ ARCH.md has 'Naming Standards' section"
else
  echo "❌ ARCH.md missing 'Naming Standards' section"; pass=false
fi
if grep -q "BIM Standards" README.md 2>/dev/null; then
  echo "✅ README references BIM Standards"
else
  echo "❌ README missing BIM Standards reference"; pass=false
fi

section "YAML schema"
if [ -n "${PYBIN}" ]; then
  "${PYBIN}" - <<'PY' || exit_code=$?
import yaml, sys
n = yaml.safe_load(open("data/bim/standards/naming.yml"))
s = yaml.safe_load(open("data/bim/standards/sheets.yml"))
assert "family_prefixes" in n, "family_prefixes missing in naming.yml"
assert "type_patterns"  in n, "type_patterns missing in naming.yml"
assert "number_pattern" in s, "number_pattern missing in sheets.yml"
print("✅ BIM YAML schema OK")
PY
  if [ -n "${exit_code:-}" ]; then echo "❌ BIM YAML schema check failed"; pass=false; unset exit_code; fi
else
  echo "⚠️  Skipped (python not found)"
fi

section "Validator smoke tests"
if [ -n "${PYBIN}" ]; then
  if "${PYBIN}" scripts/revit/validate_naming.py --help >/dev/null 2>&1; then
    echo "✅ validator --help"
  else
    echo "❌ validator --help failed"; pass=false
  fi
  if "${PYBIN}" scripts/revit/validate_naming.py >/dev/null 2>&1; then
    echo "✅ validator summary run"
  else
    echo "❌ validator summary run failed"; pass=false
  fi
else
  echo "⚠️  Skipped (python not found)"
fi

section "Guardrails"
if [ -f ".github/scripts/verify_prp.py" ]; then
  # sanity: ensure 5 KB memory limit (not 5 MB)
  if grep -q "5 \* 1024" .github/scripts/verify_prp.py && ! grep -q "5 \* 1024 \* 1024" .github/scripts/verify_prp.py; then
    echo "✅ memory limit appears to be 5 KB"
  else
    echo "⚠️  verify_prp.py may not enforce 5 KB memory limit — review recommended"
  fi
  if "${PYBIN:-python3}" .github/scripts/verify_prp.py >/dev/null 2>&1; then
    echo "✅ verify_prp.py run PASSED"
  else
    echo "❌ verify_prp.py run FAILED"; pass=false
  fi
else
  echo "❌ missing: .github/scripts/verify_prp.py"; pass=false
fi

section "Artifacts"
req_file "${ART}/notes.md"
req_file "${ART}/changed_files.csv"
req_dir  "${ART}/diffs"
# QA may or may not exist yet; try to run it best-effort
if make -v >/dev/null 2>&1; then
  make qa STORY="${STORY}" >/dev/null 2>&1 || true
fi
req_file "${ART}/QA.md"

# Write a markdown report
REPORT_MD="${ART}/audit_report.md"
{
  echo "# Audit Report — ${STORY}"
  echo "- Time (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- Repo: ${ROOT}"
  echo
  echo "## Summary"
} > "$REPORT_MD"

# Capture the on-screen lines into report (re-run quickly for capture)
{
  echo "### PRP & Files"
  for f in \
    "ai_docs/PRPs/${STORY}/PRP.md" \
    "data/bim/standards/naming.yml" \
    "data/bim/standards/sheets.yml" \
    "scripts/revit/validate_naming.py" \
    "ai_docs/PRDs/feature-bim-demo/ARCH.md" \
    "README.md"; do
    [ -f "$f" ] && echo "- ✅ $f" || echo "- ❌ $f"
  done
  echo
  echo "### Artifacts"
  for f in \
    "${ART}/notes.md" \
    "${ART}/changed_files.csv" \
    "${ART}/QA.md"; do
    [ -f "$f" ] && echo "- ✅ $f" || echo "- ❌ $f"
  done
  [ -d "${ART}/diffs" ] && echo "- ✅ ${ART}/diffs/" || echo "- ❌ ${ART}/diffs/"
} >> "$REPORT_MD"

# Emit a machine-readable JSON too
REPORT_JSON="${ART}/audit_report.json"
"${PYBIN:-python3}" - <<PY || true
import json, os, sys
story = os.environ.get("STORY", "${STORY}")
def exists(p): return os.path.isfile(p)
def dexists(p): return os.path.isdir(p)
report = {
  "story": story,
  "time_utc": __import__("datetime").datetime.utcnow().isoformat()+"Z",
  "files": {
    "prp": exists(f"ai_docs/PRPs/{story}/PRP.md"),
    "naming_yml": exists("data/bim/standards/naming.yml"),
    "sheets_yml": exists("data/bim/standards/sheets.yml"),
    "validator_py": exists("scripts/revit/validate_naming.py"),
    "arch_md": exists("ai_docs/PRDs/feature-bim-demo/ARCH.md"),
    "readme": exists("README.md"),
  },
  "artifacts": {
    "notes": exists("artifacts/%s/notes.md" % story),
    "changed_files": exists("artifacts/%s/changed_files.csv" % story),
    "diffs_dir": dexists("artifacts/%s/diffs" % story),
    "qa_md": exists("artifacts/%s/QA.md" % story),
  }
}
open("${ART}/audit_report.json","w").write(json.dumps(report, indent=2))
print("Wrote ${ART}/audit_report.json")
PY

echo
if $pass; then
  echo "✅ AUDIT PASS — see ${ART}/audit_report.md and ${ART}/audit_report.json"
else
  echo "❌ AUDIT FAIL — check ${ART}/audit_report.md for missing items"
  exit 1
fi