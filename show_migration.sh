#!/bin/bash
# Display migration SQL for copying to Supabase

cat << 'EOF'
============================================================
COPY THIS ENTIRE OUTPUT TO SUPABASE SQL EDITOR
============================================================

1. Open: https://supabase.com/dashboard
2. Go to: SQL Editor → New Query
3. Copy everything below (from CREATE EXTENSION to END $$;)
4. Paste and click "Run"

============================================================

EOF

cat /Users/ciarancox/Archon/migration/prp_system.sql

cat << 'EOF'

============================================================
END OF MIGRATION SQL
============================================================

After applying in Supabase, run:

  ./verify_prp_migration.sh && ./setup_prp.sh && ./quick_test_prp.sh

============================================================
EOF