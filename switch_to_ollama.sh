#!/bin/bash
# Quick script to switch from OpenAI to Ollama when quota runs out

echo "🔄 Switching Archon to use Ollama instead of OpenAI..."
echo ""

# Backup current .env
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backed up .env file"

# Update .env file
sed -i.tmp 's/^LLM_PROVIDER=openai/LLM_PROVIDER=ollama/' .env
sed -i.tmp 's/^EMBEDDING_DIMENSIONS=1536/EMBEDDING_DIMENSIONS=768/' .env
rm .env.tmp 2>/dev/null || true

echo "✅ Updated .env configuration"
echo ""
echo "📋 New settings:"
echo "   LLM_PROVIDER=ollama"
echo "   EMBEDDING_DIMENSIONS=768"
echo "   Model: nomic-embed-text"
echo ""

# Restart server
echo "🔄 Restarting Archon server..."
docker compose restart archon-server

echo ""
echo "✅ Done! Archon is now using Ollama for embeddings."
echo ""
echo "⚠️  IMPORTANT:"
echo "   - Existing 27,521 documents have 1536-dim embeddings (OpenAI)"
echo "   - New documents will have 768-dim embeddings (Ollama)"
echo "   - For best results, re-embed all documents with:"
echo "     curl -X POST http://localhost:8181/api/embeddings/backfill \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"tables\":[\"pages\"],\"batch_size\":50,\"limit\":30000}'"
echo ""
