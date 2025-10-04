# 🎯 RUN THIS FIRST - PRP System Setup

## TL;DR - 3 Steps to Get PRP System Running

### Step 1: Apply Database Migration (MANUAL)

**Copy this file to Supabase SQL Editor:**
```
migration/prp_system.sql
```

1. Open https://supabase.com/dashboard
2. Select your project
3. Click **SQL Editor** → **New Query**
4. Copy **ALL 257 lines** from `migration/prp_system.sql`
5. Paste and click **Run**

You should see:
```
✅ NOTICE: PRP system setup complete!
```

---

### Step 2: Run Setup Script (AUTOMATED)

```bash
cd /Users/ciarancox/Archon
./setup_prp.sh
```

This script:
- ✅ Verifies the migration was applied
- ✅ Indexes PRPs and documentation (creates embeddings)
- ✅ Restarts agents service
- ✅ Runs health check
- ✅ Tests the PRP agent

**Expected output:**
```
✅ PRP System Setup Complete!
```

---

### Step 3: Test It (OPTIONAL)

```bash
./test_prp.sh
```

This runs comprehensive tests:
- Basic question answering
- Conversation continuity
- PRP context retrieval

---

## Available Scripts

All scripts are in `/Users/ciarancox/Archon/`:

| Script | Purpose |
|--------|---------|
| `setup_prp.sh` | **Main setup** - Run after migration |
| `test_prp.sh` | Test PRP agent functionality |
| `reindex_prps.sh` | Re-index after adding/editing PRPs |

### Usage Examples

```bash
# First time setup (after migration)
./setup_prp.sh

# Test everything works
./test_prp.sh

# After adding new PRP files
./reindex_prps.sh

# Check agent health
curl http://localhost:8052/health | jq .agents_available

# Manual test
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is Archon?",
    "context": {"session_id": "manual-test"}
  }' | jq .
```

---

## What Gets Created

The migration creates:
- **3 tables:** `prp_messages`, `prp_docs`, `prp_personas`
- **2 functions:** `search_prp_messages()`, `search_prp_docs()`
- **7 settings:** PRP configuration in `archon_settings`
- **1 persona:** Default "chat_gpt_like" persona

The setup script:
- **Indexes:** PRPs, docs, and personas with embeddings
- **Verifies:** Database tables exist
- **Tests:** Agent responds correctly

---

## Troubleshooting

### Migration Not Applied
```bash
# Verify tables exist
curl -s -H "apikey: $SUPABASE_SERVICE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
  "$SUPABASE_URL/rest/v1/prp_messages?select=id&limit=1"
```

If you get 404, the migration wasn't applied.

### Embedding Sync Fails
```bash
# Check if OpenAI API key is set
echo $OPENAI_API_KEY

# Run with verbose output
cd python
uv run python -m src.scripts.prp_embed_sync
```

### Agent Not Available
```bash
# Check logs
docker compose logs archon-agents --tail=100

# Restart service
docker compose restart archon-agents
```

---

## Quick Reference

**Files you need to know:**
- `migration/prp_system.sql` - Database migration ⚡
- `setup_prp.sh` - Main setup script ⚡
- `test_prp.sh` - Test script
- `reindex_prps.sh` - Re-index script
- `PRPs/` - Add your PRP files here
- `personas/` - Add custom personas here

**Commands:**
```bash
# Setup (once)
./setup_prp.sh

# Add PRP
echo "# PRP — My Feature" > PRPs/01_my_feature.prp.md
./reindex_prps.sh

# Test
./test_prp.sh
```

---

## Next Steps

1. ✅ Complete Step 1 (apply migration)
2. ✅ Complete Step 2 (run setup script)
3. 📝 Add your PRPs to `PRPs/` directory
4. 🔄 Run `./reindex_prps.sh` after adding PRPs
5. 🧪 Test with `./test_prp.sh`

---

## Full Documentation

- **QUICK_START_PRP.md** - Detailed setup guide
- **SETUP_PRP.md** - Complete reference
- **PRPs/README.md** - How to write PRPs
- **PRP_INTEGRATION_COMPLETE.md** - Technical details

---

**Ready? Start with Step 1 above!** 🚀