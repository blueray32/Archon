#!/usr/bin/env python3
"""Quick migration applier - attempts to apply PRP migration"""
import os
import sys
sys.path.insert(0, 'python/src')

from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

# Check if exists
try:
    client.table('prp_messages').select('id').limit(1).execute()
    print("✓ PRP tables already exist!")
    sys.exit(0)
except:
    print("Creating PRP tables...")

# Try creating tables one by one via Supabase REST API
# Note: This won't work for complex SQL, user needs to use SQL Editor
print("\n⚠️  The Supabase REST API doesn't support CREATE TABLE operations.")
print("\nPlease apply the migration manually:")
print("\n1. Go to https://supabase.com/dashboard")
print("2. Select your project")
print("3. Click 'SQL Editor'")
print("4. Copy contents of: migration/prp_system.sql")
print("5. Paste and click 'Run'")
print("\nOr copy this command to see the migration:")
print(f"  cat {os.getcwd()}/migration/prp_system.sql")
