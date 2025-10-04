# 🎯 START HERE: PRP System Setup

## What Just Happened?

The complete PRP (Product Requirement Prompt) system for Archon has been created and is ready to use! All code, database schemas, documentation, and examples are in place.

## What You Need To Do Now: 4 Steps (5 minutes)

### Step 1: Apply the Database Migration ⚡

The migration file has been created at: `migration/prp_system.sql`

**Copy it to Supabase:**

1. Open: https://supabase.com/dashboard
2. Select your Archon project
3. Click **"SQL Editor"** in the sidebar
4. Click **"New Query"**
5. Open `migration/prp_system.sql` in your editor
6. **Copy ALL 257 lines**
7. Paste into Supabase SQL Editor
8. Click **"Run"**

You should see: ✅ `"PRP system setup complete!"`

<details>
<summary>💡 Alternative: View the migration file</summary>

```bash
# On your machine
cat migration/prp_system.sql

# Or open it in your editor
code migration/prp_system.sql
```

Then copy and paste to Supabase SQL Editor.
</details>

---

### Step 2: Index PRPs and Documentation 📚

```bash
cd python
uv run python -m src.scripts.prp_embed_sync
```

**Expected output:**
```
✓ Indexed prp: PRPs/00_archon_prp_system.prp.md
✓ Indexed doc: docs/...
✓ Indexed persona: personas/chat_gpt_like.yaml
============================================================
Embedding sync complete!
  PRPs indexed: 1
  Docs indexed: 15
  Personas indexed: 1
  Total: 17
============================================================
```

---

### Step 3: Restart Agents Service 🔄

```bash
docker compose restart archon-agents
```

Wait 5 seconds, then verify:

```bash
curl http://localhost:8052/health
```

Look for **`"prp"`** in the `agents_available` array.

---

### Step 4: Test It! 🎉

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
    "output": "The PRP system is a Product Requirement Prompt system...",
    "sources": [
      {"type": "prp", "path": "PRPs/00_archon_prp_system.prp.md"}
    ]
  }
}
```

---

## ✅ Verification Checklist

After the 4 steps, verify everything works:

```bash
# 1. Check tables exist
curl -s "http://localhost:8052/health" | jq .agents_available
# Should include: "prp"

# 2. Test basic chat
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "Hello!", "context": {"session_id": "test"}}'

# 3. Test conversation continuity
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "Tell me about Archon", "context": {"session_id": "conv-1"}}'

curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "What features does it have?", "context": {"session_id": "conv-1"}}'
# Should remember context from previous message
```

---

## 🎯 What You Can Do Now

### Chat with Your PRPs

```bash
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "How do I add a new agent to Archon?",
    "context": {"session_id": "user-456"}
  }' | jq .result.output
```

### Add Your Own PRPs

1. Create a new PRP file:
   ```bash
   nano PRPs/01_my_feature.prp.md
   ```

2. Write your PRP (see `PRPs/README.md` for format)

3. Re-index:
   ```bash
   cd python && uv run python -m src.scripts.prp_embed_sync
   ```

4. Ask about your feature!

### Check Conversation History

Query Supabase:
```sql
SELECT session_id, role, LEFT(content, 50) as preview
FROM prp_messages
ORDER BY created_at DESC
LIMIT 10;
```

---

## 📚 Documentation

All documentation has been created:

- **🎯 This File**: `START_HERE.md` - You are here!
- **⚡ Quick Start**: `QUICK_START_PRP.md` - 5-minute setup guide
- **📖 Full Setup**: `SETUP_PRP.md` - Detailed instructions
- **✅ Integration Complete**: `PRP_INTEGRATION_COMPLETE.md` - What was created
- **📝 PRP Guide**: `PRPs/README.md` - How to create PRPs
- **🔧 Example PRP**: `PRPs/00_archon_prp_system.prp.md` - Reference

---

## 🎨 What Was Created?

### Code Files
- ✅ `python/src/agents/prp_agent.py` - PRP Agent
- ✅ `python/src/server/services/prp_service.py` - RAG Service
- ✅ `python/src/scripts/prp_embed_sync.py` - Embedding indexer
- ✅ Updated: `python/src/agents/server.py` - Registered PRP agent

### Database
- ✅ `migration/prp_system.sql` - Complete schema (257 lines)
  - `prp_messages` table - Chat history
  - `prp_docs` table - PRP documents
  - `prp_personas` table - Agent configs
  - Vector search functions
  - Default persona

### Documentation & Examples
- ✅ `PRPs/00_archon_prp_system.prp.md` - System docs PRP
- ✅ `PRPs/README.md` - PRP creation guide
- ✅ `personas/chat_gpt_like.yaml` - Default persona
- ✅ 6 documentation files (this and others)

---

## 🐛 Something Not Working?

### Migration Fails
- Check if `update_updated_at_column()` function exists
- This should be from Archon's main migration (`complete_setup.sql`)
- If missing, comment out the trigger lines in the migration

### Embedding Sync Fails
- Ensure `OPENAI_API_KEY` is set in `.env`
- Run from `python/` directory: `cd python && uv run ...`
- Check you have internet connection for OpenAI API

### Agent Not Available
- Check logs: `docker compose logs archon-agents`
- Look for import errors or model initialization failures
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are set

### Still Stuck?
- Check `QUICK_START_PRP.md` troubleshooting section
- Check `SETUP_PRP.md` for detailed debugging
- Review the code in `python/src/agents/prp_agent.py`

---

## 🚀 Ready to Start?

1. ⬆️ **Go to Step 1** above
2. Complete all 4 steps (5 minutes)
3. Start chatting with your PRPs!

---

## 💡 Pro Tips

- Use consistent `session_id` for conversation continuity
- PRPs are retrieved automatically via vector similarity
- Check `prp_messages` table to see conversation history
- Re-run embedding sync after editing PRPs
- Keep PRPs focused on one feature per file

---

**Questions?** Read the detailed guides:
- `QUICK_START_PRP.md` - Quick setup with troubleshooting
- `SETUP_PRP.md` - Complete guide with examples
- `PRP_INTEGRATION_COMPLETE.md` - Technical details

**Ready?** Start with **Step 1** above! 🎉