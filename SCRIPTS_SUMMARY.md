# 📜 PRP System Scripts Summary

## All Scripts Ready to Use

### Main Scripts (in Archon root)

| Script | Purpose | When to Run |
|--------|---------|-------------|
| **setup_prp.sh** | Complete setup after migration | Once (after applying SQL) |
| **test_prp.sh** | Test PRP agent functionality | Anytime to verify it works |
| **reindex_prps.sh** | Re-index PRPs after changes | After adding/editing PRPs |

---

## 🚀 Quick Start Commands

### 1. First Time Setup

```bash
# Step 1: Apply migration in Supabase (MANUAL)
# - Open https://supabase.com/dashboard
# - Go to SQL Editor → New Query
# - Copy ALL of migration/prp_system.sql
# - Paste and Run

# Step 2: Run automated setup
cd /Users/ciarancox/Archon
./setup_prp.sh
```

### 2. Test Everything Works

```bash
./test_prp.sh
```

### 3. Add Your PRPs

```bash
# Create a new PRP
cat > PRPs/01_my_feature.prp.md << 'EOF'
# PRP — My Feature Name

**Owner:** Your Name
**Goal:** Brief description

## Problem & Intent
What problem does this solve?

## Outcomes
1. Success criteria 1
2. Success criteria 2

## Technical Details
How it works...
EOF

# Re-index
./reindex_prps.sh
```

---

## 📝 Script Details

### setup_prp.sh

**What it does:**
1. Verifies environment variables (OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY)
2. Checks database tables exist via REST API
3. Runs embedding sync (indexes PRPs, docs, personas)
4. Restarts agents service
5. Runs health check
6. Tests PRP agent with sample query

**Requirements:**
- Migration must be applied first
- Environment variables in `.env`
- Docker Compose running

**Output:**
```
✅ PRP System Setup Complete!
```

---

### test_prp.sh

**What it does:**
1. Checks agent availability
2. Test 1: Basic question answering
3. Test 2: Conversation continuity (multi-turn)
4. Test 3: PRP-specific questions with context retrieval

**Sample output:**
```
✓ PRP agent is available
✓ Test 1 passed
✓ Test 2 passed
✓ Test 3 passed
✓ Successfully retrieved PRP context
```

---

### reindex_prps.sh

**What it does:**
1. Counts PRPs, docs, and persona files
2. Runs embedding sync script
3. Updates all embeddings in database

**When to use:**
- After adding new PRP files
- After editing existing PRPs
- After changing documentation
- After updating personas

**Output:**
```
Found:
  • 3 PRP files
  • 15 documentation files
  • 2 persona files

✅ Re-indexing complete!
```

---

## 🔧 Manual Commands

### Check Agent Health

```bash
curl http://localhost:8052/health | jq .
```

Look for `"prp"` in `agents_available` array.

---

### Test PRP Agent Manually

```bash
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is the PRP system?",
    "context": {"session_id": "manual-test"}
  }' | jq .
```

---

### Test Conversation Continuity

```bash
# First message
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "Tell me about Archon",
    "context": {"session_id": "conv-test"}
  }' | jq -r '.result.output'

# Follow-up (should remember context)
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What are its main features?",
    "context": {"session_id": "conv-test"}
  }' | jq -r '.result.output'
```

---

### View Logs

```bash
# Agents service logs
docker compose logs archon-agents --tail=100 --follow

# Recent errors only
docker compose logs archon-agents --tail=100 | grep -i error
```

---

### Verify Database Tables

```bash
# Using curl + Supabase REST API
curl -s -H "apikey: $SUPABASE_SERVICE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
  "$SUPABASE_URL/rest/v1/prp_messages?select=count" | jq .

curl -s -H "apikey: $SUPABASE_SERVICE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
  "$SUPABASE_URL/rest/v1/prp_docs?select=count" | jq .
```

---

### List PRPs

```bash
find PRPs -name "*.prp.md" -type f
```

---

### Count Indexed Documents

```bash
# In Supabase SQL Editor:
SELECT kind, COUNT(*) as count
FROM prp_docs
GROUP BY kind;
```

---

## 🐛 Troubleshooting Commands

### Migration Not Applied

```bash
# Check if tables exist
curl -s -H "apikey: $SUPABASE_SERVICE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
  "$SUPABASE_URL/rest/v1/prp_messages?select=id&limit=1"

# Should return 200 OK, not 404
```

---

### Embedding Sync Issues

```bash
# Check OpenAI API key
echo $OPENAI_API_KEY

# Run with full output
cd python
uv run python -m src.scripts.prp_embed_sync

# Check for errors in logs
```

---

### Agent Not Responding

```bash
# Check service is running
docker compose ps archon-agents

# Restart service
docker compose restart archon-agents

# Check logs for errors
docker compose logs archon-agents --tail=50
```

---

### Environment Variables

```bash
# Check all required vars are set
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:10}..."
echo "SUPABASE_URL: $SUPABASE_URL"
echo "SUPABASE_SERVICE_KEY: ${SUPABASE_SERVICE_KEY:0:20}..."
```

---

## 📂 File Locations

```
/Users/ciarancox/Archon/
├── setup_prp.sh              # Main setup script
├── test_prp.sh               # Test script
├── reindex_prps.sh           # Re-index script
├── RUN_THIS_FIRST.md        # Quick start guide
├── SCRIPTS_SUMMARY.md       # This file
├── migration/
│   └── prp_system.sql       # Database migration
├── PRPs/
│   ├── README.md
│   └── *.prp.md             # Your PRP files
├── personas/
│   └── *.yaml               # Persona configs
└── python/src/scripts/
    └── prp_embed_sync.py    # Embedding indexer
```

---

## 🎯 Common Workflows

### Adding a New Feature PRP

```bash
# 1. Create PRP
cat > PRPs/02_authentication.prp.md << 'EOF'
# PRP — User Authentication

**Owner:** Security Team
**Goal:** Implement JWT-based authentication

## Problem & Intent
Users need secure authentication...

## Outcomes
1. JWT tokens with 1-hour expiry
2. Refresh token support
3. OAuth2 integration

## Technical Details
...
EOF

# 2. Re-index
./reindex_prps.sh

# 3. Test it
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "How does authentication work?", "context": {"session_id": "test"}}'
```

---

### Creating a Custom Persona

```bash
# 1. Create persona YAML
cat > personas/technical_architect.yaml << 'EOF'
name: "Technical Architect"
goals:
  - Provide detailed technical guidance
  - Focus on system design and architecture
style:
  tone: professional, detailed
prompt_blocks:
  - role: system
    content: |
      You are a senior technical architect...
EOF

# 2. Re-index
./reindex_prps.sh

# 3. Add to database (in Supabase SQL Editor)
INSERT INTO prp_personas (name, display_name, system_prompt, configuration)
VALUES (
  'technical_architect',
  'Technical Architect',
  'You are a senior technical architect...',
  '{"tone": "professional"}'::jsonb
);

# 4. Test with new persona
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "Design a microservices architecture",
    "context": {"persona_name": "technical_architect"}
  }'
```

---

## ✅ Success Checklist

- [ ] Migration applied in Supabase
- [ ] `./setup_prp.sh` completed successfully
- [ ] `./test_prp.sh` shows all tests passing
- [ ] Agent shows in health check: `curl http://localhost:8052/health`
- [ ] Can ask questions and get responses
- [ ] Conversation continuity works
- [ ] PRPs are retrieved as context

---

## 📚 More Documentation

- **RUN_THIS_FIRST.md** - Start here!
- **QUICK_START_PRP.md** - Detailed setup guide
- **SETUP_PRP.md** - Complete reference
- **PRPs/README.md** - How to write PRPs
- **PRP_INTEGRATION_COMPLETE.md** - Technical details

---

**Questions?** Run `./test_prp.sh` to verify everything works! 🚀