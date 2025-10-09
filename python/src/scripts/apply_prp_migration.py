#!/usr/bin/env python3
"""
Apply PRP migration to Supabase database.

This script reads the PRP migration SQL and executes it via Supabase.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()


def main():
    """Apply the PRP migration."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        print("❌ ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
        sys.exit(1)

    print("✓ Connecting to Supabase...")
    client = create_client(supabase_url, supabase_key)

    # Check if already migrated
    try:
        result = client.table("prp_messages").select("id").limit(1).execute()
        print("✓ PRP tables already exist! Migration already applied.")
        print("\nExisting tables:")
        for table in ["prp_messages", "prp_docs", "prp_personas"]:
            try:
                count_result = client.table(table).select("id", count="exact").limit(0).execute()
                count = count_result.count
                print(f"  - {table}: {count} records")
            except Exception:
                print(f"  - {table}: exists")
        return
    except Exception:
        print("⚠️  PRP tables do not exist - applying migration...")

    # Read migration SQL
    migration_path = Path(__file__).parent.parent.parent.parent / "migration" / "prp_system.sql"
    print(f"✓ Reading migration from {migration_path}")

    with open(migration_path) as f:
        sql = f.read()

    print("\n" + "=" * 60)
    print("MANUAL MIGRATION REQUIRED")
    print("=" * 60)
    print("\nThe Supabase Python client doesn't support executing raw SQL.")
    print("Please apply the migration manually:\n")
    print("Option 1: Supabase Dashboard")
    print("  1. Go to https://supabase.com/dashboard")
    print("  2. Select your project")
    print("  3. Click 'SQL Editor' in the sidebar")
    print("  4. Click 'New Query'")
    print("  5. Copy the contents of: migration/prp_system.sql")
    print("  6. Paste and click 'Run'\n")
    print("Option 2: Direct Postgres Connection")
    print("  1. Get your direct database URL from Supabase Dashboard")
    print("  2. Go to Project Settings > Database")
    print("  3. Copy the 'Connection string' (postgres://...)")
    print("  4. Run: psql '<connection-string>' -f migration/prp_system.sql\n")
    print("After applying the migration, run this script again to verify.")
    print("=" * 60)


if __name__ == "__main__":
    main()