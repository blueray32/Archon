# Obsidian → Archon Integration

**Status:** ✅ Active - Bulk sync in progress

## Overview

Your Obsidian vault is now the **source of truth** for your knowledge base, with Archon providing semantic search and AI-powered retrieval capabilities.

## Architecture

```
┌──────────────────────────────────────────────┐
│  Obsidian Vault (Master Copy)               │
│  /Users/ciarancox/Documents/ArchonVault/     │
│  - 5,150+ markdown files                     │
│  - Full editing capabilities                 │
│  - Version control via Git                   │
│  - Bidirectional links, graph view           │
└─────────────┬────────────────────────────────┘
              │
              │ Sync Script
              │ /tmp/upload_obsidian_to_archon.sh
              │
              ▼
┌──────────────────────────────────────────────┐
│  Archon Knowledge Base (Search Index)        │
│  - Supabase pgvector for embeddings          │
│  - Fast semantic search                      │
│  - RAG for AI agents                         │
│  - Filenames preserve source paths           │
└──────────────────────────────────────────────┘
```

## Current Sync Status

- **Started:** Fri Oct 3, 2025 23:37 IST
- **Process ID:** 16477
- **Total Files:** 5,150 markdown files
- **Progress:** Check with `/tmp/monitor_obsidian_sync.sh`
- **Log File:** `/tmp/archon_obsidian_sync.log`
- **ETA:** ~1.5 hours (1 file/second)

## How It Works

### 1. Source of Truth: Obsidian
- Edit files in Obsidian normally
- Files live in: `/Users/ciarancox/Documents/ArchonVault/Processed/`
- All changes stay local until you sync

### 2. Sync to Archon
- Run: `/tmp/upload_obsidian_to_archon.sh`
- Each file uploaded with metadata:
  - Original filename (preserves path info)
  - Relative path from vault root
  - Timestamp of sync
- Files are chunked and embedded for semantic search

### 3. Search in Archon
- Open: http://localhost:3737/knowledge-base
- Semantic search across all 5,150+ documents
- RAG queries retrieve relevant chunks
- Results link back to source files

## Sync Script Usage

### Run Full Sync
```bash
# Start sync in background
nohup /tmp/upload_obsidian_to_archon.sh > /dev/null 2>&1 &

# Monitor progress
/tmp/monitor_obsidian_sync.sh

# Check progress file
cat /tmp/archon_obsidian_sync_progress.txt

# View recent uploads
tail -f /tmp/archon_obsidian_sync.log
```

### Sync Workflow
1. **Edit files in Obsidian** - your vault is the master copy
2. **Run sync script** when you want changes in Archon
3. **Wait for completion** (~1.5 hours for full vault)
4. **Search in Archon** - all changes now searchable

## File Tracking

Each uploaded file maintains traceability:

- **Filename:** Original name preserved (e.g., `12.2 - Production hall spotters.md`)
- **Source Path:** Stored in filename for tracking
- **Vault Location:** `Processed/filename.md`
- **Obsidian URI:** `obsidian://open?vault=ArchonVault&file=Processed/filename.md`

## Future Enhancements

### Phase 2: Open in Obsidian (Planned)
Add UI button to open files directly from Archon search results:
```javascript
// In search results
<button onClick={() => window.open('obsidian://open?vault=ArchonVault&file=...')}>
  Open in Obsidian
</button>
```

### Phase 3: Dockling Integration (Optional)
Enhance document processing for PDFs with:
- Image descriptions using vision models
- Hybrid chunking for better semantic boundaries
- Table extraction with better formatting
- Support for complex document layouts

### Phase 4: Auto-Sync (Optional)
File watcher for automatic sync:
```bash
# Watch Obsidian vault for changes
fswatch -o $VAULT_ROOT | while read; do
  /tmp/upload_obsidian_to_archon.sh
done
```

### Phase 5: Bidirectional Sync (Advanced)
- Archon edits write back to Obsidian
- Conflict resolution
- Real-time collaboration

## Benefits of This Architecture

✅ **Obsidian Benefits Retained:**
- Offline access to all files
- Git version control
- Plugin ecosystem
- Graph view and backlinks
- Fast local editing

✅ **Archon Benefits Added:**
- Semantic search across 5,150+ files
- Vector embeddings for similarity
- RAG for AI agent queries
- Multi-user access via web UI
- Scalable search (vs file-based grep)

✅ **Best of Both Worlds:**
- Edit in Obsidian (local, fast, powerful)
- Search in Archon (semantic, AI-powered)
- No vendor lock-in (all files are markdown)
- Supabase handles complex queries

## Troubleshooting

### Sync Not Working
```bash
# Check if process is running
ps aux | grep upload_obsidian_to_archon.sh

# Check server is healthy
curl -s http://localhost:8181/health

# Restart Archon server if needed
docker compose restart archon-server
```

### Files Not Appearing in UI
- Wait 10-15 minutes after upload for embedding generation
- Check: http://localhost:3737/knowledge-base
- Refresh browser (Cmd+Shift+R)
- Check server logs: `docker compose logs archon-server`

### Network Connectivity Issues
```bash
# Restart Archon to fix DNS issues
docker compose restart archon-server

# Verify Supabase connection
docker compose logs archon-server | grep -i supabase
```

## Technical Details

### Upload Endpoint
- **API:** `POST http://localhost:8181/api/documents/upload`
- **Parameters:**
  - `file`: Markdown file
  - `knowledge_type`: "technical"
  - `tags`: JSON array (optional)

### Storage
- **Table:** `archon_crawled_pages`
- **Embeddings:** OpenAI text-embedding-3-small (1536 dimensions)
- **Chunks:** Smart splitting (configurable size)
- **Metadata:** Stored with each chunk

### Search
- **Vector Similarity:** Cosine distance in pgvector
- **Hybrid Search:** Combines semantic + keyword
- **Reranking:** Optional for improved relevance

## Monitoring

### Check Sync Progress
```bash
# Current count
cat /tmp/archon_obsidian_sync_progress.txt

# Percentage complete
echo "scale=2; $(cat /tmp/archon_obsidian_sync_progress.txt) * 100 / 5150" | bc

# Recent uploads
tail -20 /tmp/archon_obsidian_sync.log | grep "✓ Synced"

# Failed uploads
grep "✗ Failed" /tmp/archon_obsidian_sync.log
```

### Server Health
```bash
# Check all services
docker compose ps

# Server health
curl http://localhost:8181/health | jq

# View knowledge base
open http://localhost:3737/knowledge-base
```

## Maintenance

### Regular Sync Schedule
Consider setting up a cron job for daily syncs:
```bash
# Edit crontab
crontab -e

# Add daily sync at 2am
0 2 * * * /tmp/upload_obsidian_to_archon.sh > /dev/null 2>&1
```

### Cleanup Old Syncs
```bash
# Remove old log files
find /tmp -name "archon_obsidian_sync*.log" -mtime +7 -delete
```

## Resources

- **Archon Docs:** http://localhost:3737/
- **Supabase Dashboard:** (your Supabase URL)
- **Obsidian Vault:** `/Users/ciarancox/Documents/ArchonVault/`
- **Sync Scripts:** `/tmp/upload_obsidian_to_archon.sh`

---

**Last Updated:** Oct 3, 2025
**Sync Status:** Initial bulk upload in progress (PID 16477)
