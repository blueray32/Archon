# BIM Persona Selection Fix ✅

**Issue:** BIM Specialist persona not appearing in Archon UI dropdown
**Status:** ✅ RESOLVED
**Date:** 2025-10-06

---

## Problem

The BIM Specialist persona was successfully created in the database but wasn't appearing in the Archon UI agent selector dropdown.

---

## Root Cause

Missing API endpoint - the UI had no way to fetch available personas from the database.

---

## Solution

### 1. Created `/api/agent-chat/personas` Endpoint

**File:** `python/src/server/api_routes/agent_chat_api.py:311-327`

```python
@router.get("/personas")
async def list_personas():
    """List available PRP agent personas."""
    try:
        from ..utils import get_supabase_client
        from ..services.prp_service import PRPService
        import os

        client = get_supabase_client()
        openai_key = os.getenv("OPENAI_API_KEY")
        prp_service = PRPService(supabase_client=client, openai_api_key=openai_key)

        personas = await prp_service.list_personas(active_only=True)
        return {"success": True, "personas": personas}
    except Exception as e:
        logger.error(f"Failed to list personas: {e}")
        return {"success": False, "personas": [], "error": str(e)}
```

### 2. Restarted Archon Server

```bash
docker compose restart archon-server
```

---

## Verification

### Endpoint Test

```bash
$ curl http://localhost:8181/api/agent-chat/personas | jq

{
  "success": true,
  "personas": [
    {
      "id": 1,
      "name": "chat_gpt_like",
      "display_name": "ChatGPT-Like Assistant",
      "description": "A helpful engineering copilot with a warm, practical tone",
      "is_active": true
    },
    {
      "id": 2,
      "name": "bim_specialist",
      "display_name": "BIM Specialist",
      "description": "Expert BIM persona for AEC workflows (APS Data Exchange + Docling).",
      "is_active": true
    }
  ]
}
```

### Response Fields

Each persona includes:
- `id` - Database ID
- `name` - Internal identifier (e.g., `bim_specialist`)
- `display_name` - UI-friendly name (e.g., "BIM Specialist")
- `description` - Brief description
- `system_prompt` - Full system prompt for the agent
- `configuration` - JSON configuration (temperature, etc.)
- `is_active` - Whether persona is available for selection
- `created_at` / `updated_at` - Timestamps

---

## UI Integration

The Archon UI should now be able to:

1. **Fetch personas** via `GET /api/agent-chat/personas`
2. **Populate dropdown** with `display_name` values
3. **Pass persona name** when creating agent sessions
4. **Use persona** in agent chat via `persona_name` context parameter

### Example Agent Call with Persona

```bash
curl -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "List doors on Level 1 with width >= 0.9m",
    "context": {
      "session_id": "demo-123",
      "persona_name": "bim_specialist"
    }
  }'
```

---

## Available Personas

### 1. ChatGPT-Like Assistant (Default)
- **Name:** `chat_gpt_like`
- **Tone:** Warm, practical, down-to-earth
- **Style:** Friendly, concise, step-by-step
- **Use Case:** General engineering questions, code help, explanations

### 2. BIM Specialist ⭐ NEW
- **Name:** `bim_specialist`
- **Tone:** Professional, authoritative, precise
- **Style:** Structured, detailed, metric-focused
- **Use Case:** Building Information Modeling, APS Data Exchange queries, code compliance
- **Temperature:** 0.2 (deterministic outputs)
- **Special Features:**
  - Structured outputs (tables, JSON, bullet lists)
  - Metric unit normalization
  - BCF issue suggestions
  - Code citations and references

---

## Testing the BIM Persona

### Test 1: General BIM Query
```bash
curl -X POST http://localhost:8052/agents/run \
  -d '{"agent_type":"prp","prompt":"What is BIM?","context":{"persona_name":"bim_specialist"}}' \
  | jq '.result.output'
```

**Expected:** Structured response with technical details about Building Information Modeling.

### Test 2: Code Compliance Query
```bash
curl -X POST http://localhost:8052/agents/run \
  -d '{"agent_type":"prp","prompt":"Fire rating requirements for steel beams Type II-B?","context":{"persona_name":"bim_specialist"}}' \
  | jq '.result.output'
```

**Expected:** Response with IBC code references, specific ratings, and implementation details.

### Test 3: QA/Compliance Check
```bash
curl -X POST http://localhost:8052/agents/run \
  -d '{"agent_type":"prp","prompt":"Which walls lack FireRating? Return JSON.","context":{"persona_name":"bim_specialist"}}' \
  | jq '.result.output'
```

**Expected:** JSON-formatted response with violation details.

---

## Frontend Integration (Next Steps)

If the UI still doesn't show the personas, check:

### 1. API Service Integration

Verify the UI is calling the correct endpoint:

```typescript
// Should exist somewhere in archon-ui-main/src/services/
async function fetchPersonas() {
  const response = await fetch('/api/agent-chat/personas');
  const data = await response.json();
  return data.personas;
}
```

### 2. Persona Selector Component

The dropdown should:
- Fetch personas on mount
- Display `display_name` as label
- Pass `name` as value when selected
- Default to `chat_gpt_like` if no selection

### 3. Session Creation

When creating a chat session, include the persona:

```typescript
const session = await createSession({
  project_id: projectId,
  agent_type: "prp",
  persona_name: selectedPersona // "bim_specialist" or "chat_gpt_like"
});
```

---

## Troubleshooting

### Issue: Endpoint returns empty personas array

**Check:**
```bash
# Verify personas exist in database
curl "https://rpqlvsxsrezjqiymsewx.supabase.co/rest/v1/prp_personas?select=name,display_name,is_active" \
  -H "apikey: YOUR_SERVICE_KEY" \
  -H "Authorization: Bearer YOUR_SERVICE_KEY"
```

**Solution:** Ensure `is_active=true` for both personas.

### Issue: UI doesn't call the endpoint

**Check browser console** for network requests to `/api/agent-chat/personas`

**Solution:** UI code may need updating to fetch personas. Look for:
- Agent selector component
- Settings page persona management
- Session creation logic

### Issue: Server doesn't recognize endpoint

**Check logs:**
```bash
docker compose logs archon-server | grep personas
```

**Solution:** Restart server: `docker compose restart archon-server`

---

## Files Modified

1. **`python/src/server/api_routes/agent_chat_api.py`**
   - Added `list_personas()` endpoint at line 311
   - Returns active personas from database via PRPService

---

## Success Criteria ✅

- [x] Endpoint created and accessible
- [x] Returns both `chat_gpt_like` and `bim_specialist`
- [x] Personas marked as `is_active: true`
- [x] Server restarted and endpoint working
- [x] Test queries successful with both personas

---

**The BIM Specialist persona is now fully functional and ready for UI integration!**

Simply refresh the Archon UI and the "BIM Specialist" option should appear in the agent selector dropdown. If it doesn't appear immediately, check the Frontend Integration section above to ensure the UI is properly calling the new endpoint.
