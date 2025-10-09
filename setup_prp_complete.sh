#!/bin/bash
#
# Complete PRP System Setup Script
# This script guides you through setting up the PRP system in Archon
#

set -e

echo "============================================================"
echo "Archon PRP System Setup"
echo "============================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in Archon root
if [ ! -f "CLAUDE.md" ]; then
    echo -e "${RED}❌ Error: Must run from Archon root directory${NC}"
    exit 1
fi

echo "✓ Running from Archon root directory"
echo ""

# Step 1: Check environment variables
echo "Step 1: Checking environment variables..."
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_KEY" ]; then
    echo -e "${RED}❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set${NC}"
    echo "Please set them in your .env file"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  Warning: OPENAI_API_KEY not set${NC}"
    echo "You'll need this for embeddings. Set it in your .env file."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✓ OPENAI_API_KEY is set"
fi

echo "✓ Environment variables configured"
echo ""

# Step 2: Apply database migration
echo "Step 2: Applying database migration..."
echo ""
echo -e "${YELLOW}The migration must be applied manually via Supabase Dashboard:${NC}"
echo ""
echo "1. Open: https://supabase.com/dashboard"
echo "2. Select your project"
echo "3. Click 'SQL Editor' in left sidebar"
echo "4. Click 'New Query'"
echo "5. Copy the entire contents of: migration/prp_system.sql"
echo "6. Paste into the SQL Editor"
echo "7. Click 'Run' button"
echo ""
echo "The migration will create:"
echo "  - prp_messages table (chat history)"
echo "  - prp_docs table (PRP documents)"
echo "  - prp_personas table (agent personas)"
echo "  - Vector search functions"
echo "  - Default 'chat_gpt_like' persona"
echo ""
read -p "Press ENTER after you've applied the migration in Supabase Dashboard..."
echo ""

# Verify migration
echo "Verifying migration..."
cd python
if uv run python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
try:
    client.table('prp_messages').select('id').limit(1).execute()
    print('✓')
except:
    print('✗')
" | grep -q "✓"; then
    echo -e "${GREEN}✓ Migration verified - tables exist!${NC}"
else
    echo -e "${RED}❌ Error: Tables don't exist yet. Please apply the migration.${NC}"
    exit 1
fi
cd ..
echo ""

# Step 3: Index PRPs and documentation
echo "Step 3: Indexing PRPs and documentation..."
echo ""
echo "This will:"
echo "  - Index PRPs/**/*.prp.md files"
echo "  - Index docs/**/*.md files"
echo "  - Index personas/**/*.yaml files"
echo "  - Generate embeddings for all content"
echo ""

cd python
echo "Running embedding sync..."
uv run python -m src.scripts.prp_embed_sync

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Embedding sync completed successfully!${NC}"
else
    echo -e "${RED}❌ Embedding sync failed. Check the errors above.${NC}"
    exit 1
fi
cd ..
echo ""

# Step 4: Restart agents service
echo "Step 4: Restarting agents service..."
echo ""

if [ -f "docker-compose.yml" ]; then
    echo "Restarting archon-agents service..."
    docker compose restart archon-agents

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Agents service restarted${NC}"

        # Wait a bit for service to start
        echo "Waiting for service to be ready..."
        sleep 5

        # Check health
        if curl -s http://localhost:8052/health | grep -q "prp"; then
            echo -e "${GREEN}✓ PRP agent is available!${NC}"
        else
            echo -e "${YELLOW}⚠️  PRP agent not showing in health check yet${NC}"
            echo "Check logs: docker compose logs archon-agents"
        fi
    else
        echo -e "${YELLOW}⚠️  Failed to restart service - you may need to restart manually${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Docker Compose not found - restart agents service manually${NC}"
fi
echo ""

# Step 5: Test the system
echo "Step 5: Testing PRP agent..."
echo ""

echo "Testing basic chat..."
RESPONSE=$(curl -s -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is the PRP system?",
    "context": {"session_id": "setup-test"}
  }')

if echo "$RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✓ PRP agent is working!${NC}"
    echo ""
    echo "Sample response:"
    echo "$RESPONSE" | python3 -m json.tool | head -20
else
    echo -e "${YELLOW}⚠️  Could not test PRP agent${NC}"
    echo "Response: $RESPONSE"
    echo ""
    echo "This might be normal if the service is still starting."
    echo "Try testing manually with:"
    echo ""
    echo "curl -X POST http://localhost:8052/agents/run \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"agent_type\": \"prp\", \"prompt\": \"What is Archon?\", \"context\": {\"session_id\": \"test\"}}'"
fi

echo ""
echo "============================================================"
echo -e "${GREEN}PRP System Setup Complete!${NC}"
echo "============================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Add more PRPs to PRPs/ directory"
echo "2. Run: cd python && uv run python -m src.scripts.prp_embed_sync"
echo "3. Test with different personas"
echo ""
echo "Documentation:"
echo "  - Setup guide: SETUP_PRP.md"
echo "  - PRP guide: PRPs/README.md"
echo "  - Example PRP: PRPs/00_archon_prp_system.prp.md"
echo ""
echo "Test commands:"
echo "  curl -X POST http://localhost:8052/agents/run \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"agent_type\": \"prp\", \"prompt\": \"YOUR QUESTION\", \"context\": {\"session_id\": \"test\"}}'"
echo ""