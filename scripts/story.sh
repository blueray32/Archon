#!/usr/bin/env bash
# Usage:
#   make story ANALYST=1 F=feature-x
#   make story ARCH=1     F=feature-x
#   make story SM=1       F=feature-x [TYPE=BIM]
set -euo pipefail
F="${F:?usage: make story F=<feature> [ANALYST=1|ARCH=1|SM=1] [TYPE=BIM]}"
TYPE="${TYPE:-GEN}"
TPL_GEN="ai_docs/PRPs/templates/PRP.md"
TPL_BIM="ai_docs/PRPs/templates/PRP_BIM.md"

if [[ "${ANALYST:-0}" == "1" ]]; then
  mkdir -p "ai_docs/PRDs/$F"
  [[ -f "ai_docs/PRDs/$F/INITIAL.md" ]] || cat > "ai_docs/PRDs/$F/INITIAL.md" <<EOF
# INITIAL — $F
- Problem:
- Scope (in/out):
- Success criteria:
- Glossary:
EOF
  echo "Analyst: wrote ai_docs/PRDs/$F/INITIAL.md"
fi

if [[ "${ARCH:-0}" == "1" ]]; then
  mkdir -p "ai_docs/PRDs/$F"
  [[ -f "ai_docs/PRDs/$F/ARCH.md" ]] || cat > "ai_docs/PRDs/$F/ARCH.md" <<EOF
# ARCH — $F
- Modules & interfaces:
- Data contracts:
- Risks & mitigations:
- Test strategy:
EOF
  echo "Architect: wrote ai_docs/PRDs/$F/ARCH.md"
fi

if [[ "${SM:-0}" == "1" ]]; then
  mkdir -p "ai_docs/PRPs/$F/001"
  TPL="$TPL_GEN"
  [[ "$TYPE" == "BIM" ]] && TPL="$TPL_BIM"
  if [[ ! -f "ai_docs/PRPs/$F/001/PRP.md" ]]; then
    cp "$TPL" "ai_docs/PRPs/$F/001/PRP.md"
    # Stamp feature/id into the template (macOS sed -i '')
    sed -i '' "s#<Feature>/<Story-ID>#$F/001#g" "ai_docs/PRPs/$F/001/PRP.md" || true
  fi
  echo "SM: wrote ai_docs/PRPs/$F/001/PRP.md (TYPE=$TYPE)"
fi
