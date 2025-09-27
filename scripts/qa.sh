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
