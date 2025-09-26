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

# Node checks
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

# Python checks
if [ -f requirements.txt ] || [ -f pyproject.toml ]; then
  echo "## Python checks" >> "$QA"
  if command -v ruff >/dev/null 2>&1; then ruff check . && echo "- ruff: clean" >> "$QA" || { echo "- ruff: issues" >> "$QA"; status_pass=false; }
  fi
  if command -v pytest >/dev/null 2>&1; then pytest -q && echo "- pytest: pass" >> "$QA" || { echo "- pytest: fail" >> "$QA"; status_pass=false; }
  else echo "- pytest: not found" >> "$QA"
  fi
fi

# PRP acceptance echo (manual for now)
if [ -f "ai_docs/PRPs/${STORY}/PRP.md" ]; then
  echo "## Acceptance (from PRP)" >> "$QA"
  grep -n "^## Acceptance" -n "ai_docs/PRPs/${STORY}/PRP.md" -n || echo "- (fill acceptance in PRP)"
fi

echo "## Result" >> "$QA"
$status_pass && echo "- status: PASS" >> "$QA" || echo "- status: FAIL" >> "$QA"
echo "QA done. See $QA"
