# Quick Start: PRP System Setup

## ✅ What's Been Created

All PRP system files have been created and are ready to use:

### Code
- ✅ `python/src/agents/prp_agent.py` - PRP Agent
- ✅ `python/src/server/services/prp_service.py` - PRP Service (RAG retrieval)
- ✅ `python/src/scripts/prp_embed_sync.py` - Embedding sync script
- ✅ Agent registered in `python/src/agents/server.py`

### Database
- ✅ `migration/prp_system.sql` - Complete database migration

### Documentation
- ✅ `PRPs/00_archon_prp_system.prp.md` - System overview PRP
- ✅ `PRPs/README.md` - PRP management guide
- ✅ `personas/chat_gpt_like.yaml` - Default persona
- ✅ `SETUP_PRP.md` - Detailed setup guide
- ✅ `setup_prp_complete.sh` - Automated setup script

## 🚀 Setup Steps (5 minutes)

### Step 1: Apply Database Migration

**Copy the migration SQL to Supabase:**

1. Open [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project
3. Click **"SQL Editor"** in the left sidebar
4. Click **"New Query"**
5. Open the file: `migration/prp_system.sql`
6. Copy **ALL** the contents (257 lines)
7. Paste into the SQL Editor
8. Click **"Run"**

You should see: "PRP system setup complete!" in the results.

**What this creates:**
- `prp_messages` - Chat history with vector embeddings
- `prp_docs` - PRP documents with vector embeddings
- `prp_personas` - Agent persona configurations
- Vector search functions
- Default "chat_gpt_like" persona

### Step 2: Index PRPs and Documentation

```bash
cd python
uv run python -m src.scripts.prp_embed_sync
```

**Expected output:**
```
INFO - Starting PRP embedding sync...
INFO - ✓ Indexed prp: PRPs/00_archon_prp_system.prp.md
INFO - ✓ Indexed doc: docs/...
INFO - ✓ Indexed persona: personas/chat_gpt_like.yaml
INFO - Embedding sync complete!
INFO -   PRPs indexed: 1
INFO -   Docs indexed: XX
INFO -   Personas indexed: 1
```

### Step 3: Restart Agents Service

```bash
docker compose restart archon-agents

# Wait a few seconds, then check health
curl http://localhost:8052/health
```

Look for `"prp"` in the `agents_available` list.

### Step 4: Test It!

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

## ✅ Verification Checklist

After completing the steps, verify:

- [ ] Migration applied - Check Supabase SQL Editor shows success
- [ ] Tables exist - Query `SELECT * FROM prp_messages LIMIT 1` works
- [ ] Embeddings indexed - Script completed without errors
- [ ] Agent available - `/health` shows "prp" in agents list
- [ ] Agent works - Test curl returns success

## 📚 What You Can Do Now

### Add More PRPs

```bash
# 1. Create new PRP
echo "# PRP — My Feature" > PRPs/01_my_feature.prp.md

# 2. Write your PRP (see PRPs/README.md for format)

# 3. Re-index
cd python && uv run python -m src.scripts.prp_embed_sync
```

### Chat with PRP Agent

```bash
# Basic chat
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "Tell me about Archon",
    "context": {"session_id": "user-123"}
  }'

# With custom persona
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "How do I add a new agent?",
    "context": {
      "session_id": "user-123",
      "persona_name": "chat_gpt_like"
    }
  }'
```

### Check Conversation History

```sql
-- In Supabase SQL Editor
SELECT session_id, role, LEFT(content, 100) as preview, created_at
FROM prp_messages
WHERE session_id = 'user-123'
ORDER BY created_at DESC;
```

## 🔧 Troubleshooting

### Migration Fails

**Error: `function update_updated_at_column() does not exist`**
- This function should exist from Archon's main migration
- Check if `complete_setup.sql` was applied
- If not, you'll need to create the function or comment out those triggers

**Error: `extension "vector" is not available`**
- pgvector extension not installed
- In Supabase: Go to Database > Extensions > Enable "vector"

### Embedding Sync Fails

**Error: `No module named 'supabase'`**
- Run from `python/` directory: `cd python && uv run python -m src.scripts.prp_embed_sync`

**Error: `Missing OPENAI_API_KEY`**
- Set in `.env` file: `OPENAI_API_KEY=sk-...`
- Restart terminal to reload environment

### Agent Not Available

**Check logs:**
```bash
docker compose logs archon-agents | tail -50
```

**Common issues:**
- Import error in `server.py` - Check PRPAgent import
- Model not available - Check OpenAI API key
- Supabase connection issue - Check SUPABASE_URL and key

### Agent Returns Errors

**"No context retrieved"**
- Run embedding sync again
- Check `prp_docs` table has records with embeddings
- Verify OpenAI API key is valid

**"Session not found"**
- Normal for first message - session is created automatically
- Ensure consistent `session_id` across requests

## 📖 Documentation

- **Detailed Setup**: `SETUP_PRP.md`
- **PRP Guide**: `PRPs/README.md`
- **Example PRP**: `PRPs/00_archon_prp_system.prp.md`
- **Automated Setup**: `./setup_prp_complete.sh`

## 🎯 Next Steps

1. ✅ Complete the 4 setup steps above
2. 📝 Create PRPs for your Archon features
3. 🤖 Test different conversation flows
4. 🎨 Create custom personas for specific use cases
5. 🔗 Integrate with your UI (future work)

## 💡 Pro Tips

- Keep PRPs focused (one feature per file)
- Use descriptive filenames: `01_feature_name.prp.md`
- Re-run embedding sync after editing PRPs
- Use consistent session IDs for conversation continuity
- Check `prp_messages` table to see conversation history
- Monitor OpenAI API usage for embedding costs

## 🆘 Need Help?

Check these resources:
- Full setup guide: `SETUP_PRP.md`
- PRP format guide: `PRPs/README.md`
- Agent code: `python/src/agents/prp_agent.py`
- Service code: `python/src/server/services/prp_service.py`

Ready to start? Go to **Step 1** above! 🚀