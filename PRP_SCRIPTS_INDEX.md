# 📜 PRP System Scripts Index

## All Scripts at a Glance

### 🚀 Setup & Verification

| Script | Purpose | Usage |
|--------|---------|-------|
| **`verify_prp_migration.sh`** | Verify migration applied | `./verify_prp_migration.sh` |
| **`setup_prp.sh`** | Complete setup (after migration) | `./setup_prp.sh` |

### 🧪 Testing

| Script | Purpose | Usage |
|--------|---------|-------|
| **`quick_test_prp.sh`** | Fast smoke tests (2 tests) | `./quick_test_prp.sh` |
| **`test_prp.sh`** | Full test suite (3 tests) | `./test_prp.sh` |

### 🔄 Maintenance

| Script | Purpose | Usage |
|--------|---------|-------|
| **`reindex_prps.sh`** | Re-index after editing PRPs | `./reindex_prps.sh` |

---

## Quick Start Sequence

```bash
# 1. Apply migration in Supabase SQL Editor (MANUAL)
#    File: migration/prp_system.sql

# 2. Verify migration
./verify_prp_migration.sh

# 3. Run setup
./setup_prp.sh

# 4. Quick test
./quick_test_prp.sh
```

---

## Script Details

### verify_prp_migration.sh
**What it does:** Checks if database tables exist via REST API (no Python)
**Requirements:** `.env` with SUPABASE_URL and SUPABASE_SERVICE_KEY
**Output:**
```
✓ prp_messages
✓ prp_docs
✓ prp_personas
All good.
```

---

### setup_prp.sh
**What it does:**
1. Verifies environment variables
2. Checks migration applied
3. Indexes PRPs, docs, personas
4. Restarts agents service
5. Health check
6. Smoke test

**Requirements:**
- Migration applied
- Docker Compose running
- `.env` configured

**Output:**
```
✅ PRP System Setup Complete!
```

---

### quick_test_prp.sh
**What it does:**
- Test 1: Basic question
- Test 2: Conversation continuity (2 messages)

**Requirements:** Agents service running on port 8052

**Output:** Direct agent responses

---

### test_prp.sh
**What it does:**
- Test 1: Basic question
- Test 2: Conversation continuity (2 messages)
- Test 3: PRP-specific question with context check

**Requirements:** Agents service running, jq installed

**Output:**
```
✓ Test 1 passed
✓ Test 2 passed
✓ Test 3 passed
✓ Successfully retrieved PRP context
```

---

### reindex_prps.sh
**What it does:**
- Counts PRPs, docs, personas
- Runs embedding sync
- Updates database

**When to use:**
- After adding new PRPs
- After editing existing PRPs
- After updating docs or personas

**Output:**
```
Found:
  • 3 PRP files
  • 15 documentation files
  • 2 persona files

✅ Re-indexing complete!
```

---

## One-Liner Commands

```bash
# Full setup after migration
./verify_prp_migration.sh && ./setup_prp.sh && ./quick_test_prp.sh

# Add PRP and test
vim PRPs/02_my_feature.prp.md && ./reindex_prps.sh && ./quick_test_prp.sh

# Check everything
./verify_prp_migration.sh && curl http://localhost:8052/health | jq .agents_available
```

---

## Troubleshooting Scripts

```bash
# Check migration applied
./verify_prp_migration.sh

# Check agent health
curl http://localhost:8052/health | jq .

# View logs
docker compose logs archon-agents --tail=50

# Re-run setup
./setup_prp.sh

# Quick test
./quick_test_prp.sh
```

---

## File Locations

All scripts are in: `/Users/ciarancox/Archon/`

```
├── verify_prp_migration.sh  # Verify migration
├── setup_prp.sh             # Main setup
├── quick_test_prp.sh        # Fast tests ⚡
├── test_prp.sh              # Full tests
└── reindex_prps.sh          # Re-index PRPs
```

---

## Documentation

| File | Purpose |
|------|---------|
| `PRP_SCRIPTS_INDEX.md` | This file - script overview |
| `COMPLETE_SETUP_GUIDE.md` | Complete reference |
| `RUN_THIS_FIRST.md` | Quick start guide |
| `SCRIPTS_SUMMARY.md` | Detailed script reference |

---

## Common Patterns

### First Time Setup
```bash
# After applying migration in Supabase
./verify_prp_migration.sh
./setup_prp.sh
./quick_test_prp.sh
```

### Daily Development
```bash
# Edit PRP
vim PRPs/02_feature.prp.md

# Re-index
./reindex_prps.sh

# Test
./quick_test_prp.sh
```

### Debugging
```bash
# 1. Verify migration
./verify_prp_migration.sh

# 2. Check health
curl http://localhost:8052/health | jq .

# 3. View logs
docker compose logs archon-agents --tail=50

# 4. Test
./quick_test_prp.sh
```

---

## Quick Reference

```bash
# Setup
./setup_prp.sh

# Test (fast)
./quick_test_prp.sh

# Test (full)
./test_prp.sh

# Re-index
./reindex_prps.sh

# Verify
./verify_prp_migration.sh
```

---

**All scripts are ready to use!** 🚀

Run `./quick_test_prp.sh` for a fast check anytime!