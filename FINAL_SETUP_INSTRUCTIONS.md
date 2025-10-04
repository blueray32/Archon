# 🚀 PRP System - Final Setup Instructions

## ✅ What's Complete

All code and files have been created! The PRP system is ready - you just need to apply the database migration.

### Files Created (18 total):
- ✅ PRPAgent (`python/src/agents/prp_agent.py`)
- ✅ PRPService (`python/src/server/services/prp_service.py`)
- ✅ Embedding sync script (`python/src/scripts/prp_embed_sync.py`)
- ✅ Database migration (`migration/prp_system.sql`)
- ✅ Agent registered in server.py
- ✅ Example PRP (`PRPs/00_archon_prp_system.prp.md`)
- ✅ Default persona (`personas/chat_gpt_like.yaml`)
- ✅ 11 documentation files

## 🎯 What You Need To Do

### STEP 1: Apply Database Migration (2 minutes) ⚡

**The migration file is here:**
```
/Users/ciarancox/Archon/migration/prp_system.sql
```

**Apply it via Supabase Dashboard:**

1. Open https://supabase.com/dashboard
2. Select your project
3. Click **"SQL Editor"** → **"New Query"**
4. Open the file `/Users/ciarancox/Archon/migration/prp_system.sql` in your editor
5. Select ALL (CMD+A) and copy
6. Paste into Supabase SQL Editor
7. Click **"Run"**

**You should see:**
```
NOTICE: PRP system setup complete!
NOTICE: Tables created: prp_messages, prp_docs, prp_personas
```

**What this creates:**
- `prp_messages` - Chat history with 1536-dim vector embeddings
- `prp_docs` - PRP documents with embeddings
- `prp_personas` - Agent persona configurations
- Vector search functions
- 7 PRP settings
- Default "chat_gpt_like" persona

---

### STEP 2: Run Embedding Sync (1 minute)

```bash
cd /Users/ciarancox/Archon/python
uv run python -m src.scripts.prp_embed_sync
```

**Expected output:**
```
INFO - ✓ Indexed prp: PRPs/00_archon_prp_system.prp.md
INFO - ✓ Indexed doc: docs/...
INFO - ✓ Indexed persona: personas/chat_gpt_like.yaml
INFO - Embedding sync complete!
INFO -   PRPs indexed: 1
INFO -   Docs indexed: 5
INFO -   Personas indexed: 1
INFO -   Total: 7
```

---

### STEP 3: Restart Agents Service (30 seconds)

```bash
docker compose restart archon-agents
```

Wait 5 seconds, then verify:

```bash
curl http://localhost:8052/health
```

Look for `"prp"` in the `agents_available` array.

---

### STEP 4: Test It! (30 seconds) 🎉

```bash
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is the PRP system and how does it work?",
    "context": {"session_id": "test-123"}
  }' | jq .
```

**Expected response:**
```json
{
  "success": true,
  "result": {
    "output": "The PRP system is...",
    "sources": [...]
  }
}
```

---

## 📋 Quick Copy-Paste Commands

Once migration is applied:

```bash
# Step 2: Index PRPs
cd /Users/ciarancox/Archon/python && uv run python -m src.scripts.prp_embed_sync

# Step 3: Restart agents
docker compose restart archon-agents && sleep 5 && curl http://localhost:8052/health | jq .agents_available

# Step 4: Test
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "What is Archon?", "context": {"session_id": "test"}}' | jq .
```

---

## ✅ Verification Checklist

- [ ] Migration applied in Supabase
- [ ] Tables created (verify in Supabase Dashboard → Table Editor)
- [ ] Embedding sync completed successfully
- [ ] Agents service restarted
- [ ] Health check shows "prp" agent
- [ ] Test curl returns success

---

## 🎨 What You Can Do After Setup

### Add More PRPs

```bash
# 1. Create file
echo "# PRP — My Feature" > PRPs/01_my_feature.prp.md

# 2. Edit and write your PRP

# 3. Re-index
cd python && uv run python -m src.scripts.prp_embed_sync
```

### Test Conversation Continuity

```bash
# First message
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "Tell me about agents in Archon", "context": {"session_id": "conv-1"}}'

# Follow-up (should remember context)
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "How do I add a new one?", "context": {"session_id": "conv-1"}}'
```

### View Conversation History

Query in Supabase SQL Editor:
```sql
SELECT session_id, role, LEFT(content, 100) as preview, created_at
FROM prp_messages
ORDER BY created_at DESC
LIMIT 20;
```

---

## 🐛 Troubleshooting

### Migration Fails

**Error: `function update_updated_at_column() does not exist`**
- This function should exist from Archon's main migration
- If not, comment out the trigger lines (lines 71-74 and 102-105)

**Error: `extension "vector" is not available`**
- Enable pgvector in Supabase: Database → Extensions → vector

### Embedding Sync Shows 0 Indexed

- Make sure migration was applied first
- Check `prp_docs` table exists in Supabase
- Verify `OPENAI_API_KEY` is set in `.env`

### Agent Not Available in Health Check

- Check logs: `docker compose logs archon-agents | tail -50`
- Look for Python import errors
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`

---

## 📚 Documentation Files

All documentation is ready in your Archon directory:

| File | Purpose |
|------|---------|
| `START_HERE.md` | Quick overview (read first!) |
| `QUICK_START_PRP.md` | 5-minute setup guide |
| `SETUP_PRP.md` | Detailed setup with troubleshooting |
| `FINAL_SETUP_INSTRUCTIONS.md` | This file - what to do now |
| `APPLY_MIGRATION_MANUALLY.md` | Migration help |
| `PRP_INTEGRATION_COMPLETE.md` | What was created |
| `PRPs/README.md` | How to create PRPs |
| `PRPs/00_archon_prp_system.prp.md` | Example PRP |

---

## 🎯 Summary

1. **Apply migration** in Supabase SQL Editor (2 min)
2. **Run embedding sync** (1 min)
3. **Restart agents service** (30 sec)
4. **Test** with curl (30 sec)

**Total time: 4 minutes** ⚡

All code is ready - just complete these 4 steps!

---

## 📞 Need Help?

- Check `QUICK_START_PRP.md` for troubleshooting
- Review `SETUP_PRP.md` for detailed instructions
- Examine the code in `python/src/agents/prp_agent.py`

---

**Ready to start? Open the migration file and copy it to Supabase!** 🚀

```bash
# View the migration
cat /Users/ciarancox/Archon/migration/prp_system.sql

# Or open in editor
code /Users/ciarancox/Archon/migration/prp_system.sql
```