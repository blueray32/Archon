#!/bin/bash
# Quick script to switch back from Ollama to OpenAI

echo "🔄 Switching Archon back to OpenAI..."
echo ""

# Backup current .env
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backed up .env file"

# Update .env file
sed -i.tmp 's/^LLM_PROVIDER=ollama/LLM_PROVIDER=openai/' .env
sed -i.tmp 's/^EMBEDDING_DIMENSIONS=768/EMBEDDING_DIMENSIONS=1536/' .env
rm .env.tmp 2>/dev/null || true

echo "✅ Updated .env configuration"
echo ""
echo "📋 New settings:"
echo "   LLM_PROVIDER=openai"
echo "   EMBEDDING_DIMENSIONS=1536"
echo "   Model: text-embedding-3-small"
echo ""

# Restart server
echo "🔄 Restarting Archon server..."
docker compose restart archon-server

echo ""
echo "✅ Done! Archon is now using OpenAI for embeddings."
echo ""
