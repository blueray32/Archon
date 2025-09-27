"""
Pytest configuration for Archon validation tests.
"""
import sys
import pathlib

# Add script directories to Python path for imports
scripts_dir = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))
sys.path.insert(0, str(scripts_dir.parent / ".github" / "scripts"))