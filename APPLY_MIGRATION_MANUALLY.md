# ⚠️ Manual Migration Required

## Why Manual?

The Supabase Python client doesn't support executing raw SQL. You need to apply the migration via:
1. **Supabase Dashboard SQL Editor** (recommended), or
2. **Direct PostgreSQL connection**

## Option 1: Supabase Dashboard (Easiest) ⭐

1. Open: https://supabase.com/dashboard
2. Select your Archon project
3. Click **"SQL Editor"** in the left sidebar
4. Click **"New Query"**
5. Open file: `/Users/ciarancox/Archon/migration/prp_system.sql`
6. **Select ALL** (CMD+A) and copy
7. Paste into SQL Editor
8. Click **"Run"** button

**Expected Output:**
```
NOTICE: PRP system setup complete!
NOTICE: Tables created: prp_messages, prp_docs, prp_personas
NOTICE: Helper functions created: search_prp_messages, search_prp_docs
NOTICE: Default persona created: chat_gpt_like
```

## Option 2: Direct PostgreSQL Connection

If you have the direct database connection string:

```bash
psql 'postgresql://postgres:[YOUR-PASSWORD]@[YOUR-HOST]:5432/postgres' \
  -f /Users/ciarancox/Archon/migration/prp_system.sql
```

Get your connection string from:
- Supabase Dashboard → Project Settings → Database → Connection string

## After Applying

Run the verification:

```bash
cd /Users/ciarancox/Archon/python
uv run python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
print('Checking tables...')
for t in ['prp_messages', 'prp_docs', 'prp_personas']:
    r = client.table(t).select('id').limit(1).execute()
    print(f'✓ {t} exists')
print('✅ Migration verified!')
"
```

## Then Continue Setup

Once verified, continue with:

```bash
# Step 2: Index PRPs
cd python
uv run python -m src.scripts.prp_embed_sync

# Step 3: Restart agents
docker compose restart archon-agents

# Step 4: Test
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "prp", "prompt": "Hello!", "context": {"session_id": "test"}}'
```

## Migration File Location

📁 `/Users/ciarancox/Archon/migration/prp_system.sql`

View it:
```bash
cat /Users/ciarancox/Archon/migration/prp_system.sql
```

Or open in editor:
```bash
code /Users/ciarancox/Archon/migration/prp_system.sql
```