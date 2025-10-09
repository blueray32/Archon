#!/usr/bin/env python3
"""
Simple test runner for Archon validation tests.
Usage: python scripts/tests/run_tests.py
"""
import subprocess
import sys
from pathlib import Path


def main():
    """Run all validation tests."""
    project_root = Path(__file__).parent.parent.parent
    test_dir = project_root / "scripts" / "tests"

    print("🧪 Running Archon Validation Tests")
    print("=" * 40)

    # Run pytest with verbose output
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            str(test_dir),
            "-v",
            "--tb=short"
        ], cwd=project_root, check=False)

        if result.returncode == 0:
            print("\n✅ All tests passed!")
        else:
            print(f"\n❌ Tests failed with exit code {result.returncode}")

        return result.returncode

    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())