#!/bin/bash
# Re-index PRPs after adding or editing PRP files

set -euo pipefail

echo "============================================================"
echo "Re-indexing PRPs and Documentation"
echo "============================================================"
echo ""

# Check we're in Archon root
if [ ! -d "python/src" ]; then
  echo "❌ Must run from Archon root directory"
  exit 1
fi

# Load .env
if [ -f ".env" ]; then
  set -o allexport; source .env; set +o allexport
fi

# Check required env vars
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "❌ OPENAI_API_KEY not set"
  exit 1
fi

# Count PRPs
PRP_COUNT=$(find PRPs -name "*.prp.md" 2>/dev/null | wc -l | tr -d ' ')
DOC_COUNT=$(find docs -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
PERSONA_COUNT=$(find personas -name "*.yaml" 2>/dev/null | wc -l | tr -d ' ')

echo "Found:"
echo "  • $PRP_COUNT PRP files"
echo "  • $DOC_COUNT documentation files"
echo "  • $PERSONA_COUNT persona files"
echo ""

if [ "$PRP_COUNT" -eq 0 ] && [ "$DOC_COUNT" -eq 0 ] && [ "$PERSONA_COUNT" -eq 0 ]; then
  echo "⚠️  No files found to index"
  exit 0
fi

echo "Starting embedding sync..."
echo ""

cd python
uv run python -m src.scripts.prp_embed_sync

if [ $? -eq 0 ]; then
  echo ""
  echo "✅ Re-indexing complete!"
  echo ""
  echo "PRPs are now available for retrieval in agent conversations."
else
  echo ""
  echo "❌ Re-indexing failed"
  exit 1
fi