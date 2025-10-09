# 🎯 Complete PRP System Setup Guide

## All Scripts & Commands in One Place

---

## Quick Setup (3 Commands)

```bash
cd /Users/ciarancox/Archon

# 1. Verify migration (after applying in Supabase)
./verify_prp_migration.sh

# 2. Run complete setup
./setup_prp.sh

# 3. Test everything
./test_prp.sh
```

---

## Step-by-Step Setup

### Step 0: Prerequisites

Ensure you have in your `.env`:
```bash
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
```

---

### Step 1: Apply Database Migration

**⚠️ MANUAL STEP - Cannot be automated**

1. Open: https://supabase.com/dashboard
2. Select your project
3. Click **SQL Editor** → **New Query**
4. Copy **ALL** of this file:
   ```
   /Users/ciarancox/Archon/migration/prp_system.sql
   ```
5. Paste and click **Run**

**Expected output:**
```
✅ NOTICE: PRP system setup complete!
✅ NOTICE: Tables created: prp_messages, prp_docs, prp_personas
```

**Verify it worked:**
```bash
./verify_prp_migration.sh
```

Should show:
```
✓ prp_messages
✓ prp_docs
✓ prp_personas
All good.
```

---

### Step 2: Run Setup Script

```bash
./setup_prp.sh
```

**What this does:**
1. ✅ Verifies environment variables
2. ✅ Checks database tables exist
3. ✅ Indexes PRPs and documentation
4. ✅ Restarts agents service
5. ✅ Health check
6. ✅ Smoke test

**Expected output:**
```
============================================================
✅ PRP System Setup Complete!
============================================================
```

---

### Step 3: Test It

```bash
./test_prp.sh
```

**What this does:**
- Test 1: Basic question answering
- Test 2: Conversation continuity (multi-turn)
- Test 3: PRP context retrieval

**Expected output:**
```
✓ Test 1 passed
✓ Test 2 passed
✓ Test 3 passed
✓ Successfully retrieved PRP context
```

---

## All Available Scripts

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `verify_prp_migration.sh` | Check if migration applied | Before setup |
| `setup_prp.sh` | Complete setup | After migration |
| `test_prp.sh` | Run all tests | Verify it works |
| `reindex_prps.sh` | Re-index PRPs | After adding/editing PRPs |

---

## Manual Commands

### Check Agent Health

```bash
curl http://localhost:8052/health | jq '.agents_available'
```

Look for `"prp"` in the array.

---

### Quick Test

```bash
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is Archon?",
    "context": {"session_id": "quick-test"}
  }' | jq -r '.result.output'
```

---

### Test Conversation Memory

```bash
# First message
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "Tell me about agents", "context": {"session_id": "memory-test"}}' \
  | jq -r '.result.output'

echo ""
echo "---"
echo ""

# Follow-up (should remember context)
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "How do I add a new one?", "context": {"session_id": "memory-test"}}' \
  | jq -r '.result.output'
```

---

### View Logs

```bash
# Agents service logs
docker compose logs archon-agents --tail=50 --follow

# Recent errors
docker compose logs archon-agents --tail=100 | grep -i error
```

---

## Adding Your Own PRPs

### 1. Create PRP File

```bash
cat > PRPs/01_my_feature.prp.md << 'EOF'
# PRP — My Feature Name

**Owner:** Your Name
**Primary LLM:** GPT-4o-mini
**Goal:** Brief description of what this achieves

## Problem & Intent
What problem does this solve and why?

## Outcomes (Success Criteria)
1. Measurable outcome 1
2. Measurable outcome 2
3. Measurable outcome 3

## Technical Architecture
How is this implemented?

## Usage Patterns
Examples of how to use this feature.

## Best Practices
Guidelines for effective use.
EOF
```

### 2. Re-index

```bash
./reindex_prps.sh
```

### 3. Test It

```bash
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "Tell me about [your feature]",
    "context": {"session_id": "test"}
  }' | jq -r '.result.output'
```

---

## Troubleshooting

### Migration Not Applied

```bash
# Run verification
./verify_prp_migration.sh

# If it fails:
# 1. Check Supabase Dashboard → SQL Editor
# 2. Look for errors when you ran the migration
# 3. Make sure you copied ALL 257 lines
```

---

### Setup Script Fails

```bash
# Check environment
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:10}..."
echo "SUPABASE_URL: $SUPABASE_URL"

# Re-run with verbose output
bash -x ./setup_prp.sh
```

---

### Agent Not Available

```bash
# Check service status
docker compose ps archon-agents

# Restart
docker compose restart archon-agents

# Check logs for errors
docker compose logs archon-agents --tail=100 | grep -i error
```

---

### Embedding Sync Fails

```bash
# Run directly to see errors
cd python
uv run python -m src.scripts.prp_embed_sync

# Common issues:
# - OPENAI_API_KEY not set
# - Database tables don't exist
# - Network/firewall blocking OpenAI API
```

---

### No Context Retrieved

```bash
# Check if PRPs were indexed
curl -s -H "apikey: $SUPABASE_SERVICE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
  "$SUPABASE_URL/rest/v1/prp_docs?select=kind,path,title&kind=eq.prp" \
  | jq .

# Should show your PRP files
```

---

## Database Queries

Run these in Supabase SQL Editor:

### Check Indexed PRPs

```sql
SELECT kind, COUNT(*) as count
FROM prp_docs
GROUP BY kind;
```

### View Recent Messages

```sql
SELECT session_id, role, LEFT(content, 100) as preview, created_at
FROM prp_messages
ORDER BY created_at DESC
LIMIT 20;
```

### Check Embeddings

```sql
SELECT path,
       CASE WHEN embedding IS NULL THEN 'missing' ELSE 'present' END as has_embedding
FROM prp_docs
WHERE kind = 'prp';
```

---

## File Structure

```
/Users/ciarancox/Archon/
│
├── Scripts (executable)
│   ├── verify_prp_migration.sh    # Check migration applied
│   ├── setup_prp.sh               # Main setup
│   ├── test_prp.sh                # Run tests
│   └── reindex_prps.sh            # Re-index PRPs
│
├── Documentation
│   ├── COMPLETE_SETUP_GUIDE.md    # This file ⭐
│   ├── RUN_THIS_FIRST.md          # Quick start
│   ├── SCRIPTS_SUMMARY.md         # Script reference
│   ├── QUICK_START_PRP.md         # Detailed guide
│   └── SETUP_PRP.md               # Complete reference
│
├── Database
│   └── migration/prp_system.sql   # Apply this first!
│
├── PRPs/
│   ├── README.md                  # How to write PRPs
│   └── 00_archon_prp_system.prp.md
│
├── personas/
│   └── chat_gpt_like.yaml
│
└── python/src/
    ├── agents/prp_agent.py
    ├── server/services/prp_service.py
    └── scripts/prp_embed_sync.py
```

---

## Common Workflows

### Daily Usage

```bash
# Add a new PRP
vim PRPs/02_new_feature.prp.md

# Re-index
./reindex_prps.sh

# Test
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "Tell me about [feature]", "context": {"session_id": "test"}}'
```

---

### Debugging

```bash
# 1. Check migration
./verify_prp_migration.sh

# 2. Check agent health
curl http://localhost:8052/health | jq .

# 3. Check logs
docker compose logs archon-agents --tail=50

# 4. Test directly
./test_prp.sh
```

---

### Updating PRPs

```bash
# 1. Edit PRP file
vim PRPs/01_my_feature.prp.md

# 2. Re-index (upserts existing)
./reindex_prps.sh

# 3. Test updated content
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "What changed in [feature]?", "context": {"session_id": "test"}}'
```

---

## Success Checklist

- [ ] Environment variables set in `.env`
- [ ] Migration applied in Supabase
- [ ] `./verify_prp_migration.sh` passes
- [ ] `./setup_prp.sh` completes successfully
- [ ] `./test_prp.sh` shows all tests passing
- [ ] Agent appears in health check
- [ ] Can ask questions and get responses
- [ ] Conversation continuity works
- [ ] PRPs are retrieved as context

---

## Next Steps

1. ✅ Complete all setup steps above
2. 📝 Add your PRPs to `PRPs/` directory
3. 🎨 Customize personas in `personas/`
4. 🧪 Test with your use cases
5. 🔄 Iterate and improve PRPs based on agent responses

---

## Quick Reference Card

```bash
# Setup (once)
./verify_prp_migration.sh
./setup_prp.sh
./test_prp.sh

# Daily (after editing PRPs)
./reindex_prps.sh

# Debugging
docker compose logs archon-agents --tail=50
curl http://localhost:8052/health | jq .

# Testing
./test_prp.sh
```

---

## Getting Help

- **Quick issues:** Check `SCRIPTS_SUMMARY.md`
- **Detailed setup:** Read `SETUP_PRP.md`
- **PRP writing:** See `PRPs/README.md`
- **Technical details:** Review `PRP_INTEGRATION_COMPLETE.md`

---

**Ready to start?** 🚀

1. Apply the migration in Supabase
2. Run `./verify_prp_migration.sh`
3. Run `./setup_prp.sh`
4. Start chatting with your PRPs!