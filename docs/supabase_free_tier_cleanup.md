# Supabase Free-Tier Cleanup Playbook

Keep the Archon Supabase project below the 1.1 GB database ceiling without upgrading by running the scripted retention routine and scheduling it to repeat automatically.

## 1. One-Time Setup

- Ensure `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` exist in `.env`; the service key must have database access.  
- Install `psql` (macOS: `brew install libpq && echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc`).  
- Make the runner executable once:

```bash
chmod +x scripts/run_supabase_cleanup.sh
```

## 2. Run the Cleanup

The script loads `.env`, connects through the Supabase connection pooler, prunes cold data, and vacuums touched tables so space is truly reclaimed.

```bash
./scripts/run_supabase_cleanup.sh
```

Default retention rules (overrides shown below) already match common Archon workloads:

- Drop crawl chunks older than **60 days**.
- Cap each source to **400** chunks (lowest chunk numbers survive).
- Keep the **5** newest `archon_document_versions` per `(project_id, field_name, document_id)`.
- Keep the **2000** most recent `prp_docs` of kind `doc` (personas/prp rows are preserved).
- Vacuum/analyze the pruned tables so the size drops immediately.

### Override Retention Limits

```bash
MAX_CHUNKS_PER_SOURCE=250 \
MAX_VERSIONS_PER_DOC=3 \
MAX_PRP_DOCS=1500 \
./scripts/run_supabase_cleanup.sh
```

## 3. Schedule It

Pick a scheduler you control (GitHub Actions, cron on a small VPS, Fly.io task, etc.). Example nightly cron on macOS/Linux:

```bash
0 2 * * * cd /Users/ciarancox/Archon && ./scripts/run_supabase_cleanup.sh >> /Users/ciarancox/archon_cleanup.log 2>&1
```

For GitHub Actions, store `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` as repository secrets and enable the scheduled workflow at `.github/workflows/supabase-cleanup.yml` (runs daily at 03:00 UTC, and can be triggered manually via **Run workflow**).

## 4. Verify After Each Run

Immediately re-run the script—it prints pre/post table sizes. Confirm the total size drops under 1.1 GB in the Supabase dashboard. If not, lower the retention caps or delete additional low-value sources.

## 5. Optional Tunings

- Adjust crawler settings so initial chunks stay lean (shorter chunk length, strip boilerplate HTML before storage).  
- Store bulky attachments in Supabase Storage and persist only metadata/URLs in Postgres.  
- Add per-source quotas inside the ingestion pipeline to prevent runaway crawls from breaching the limit before the nightly cleanup executes.
