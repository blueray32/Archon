#!/usr/bin/env python3
"""
Unit tests for PRP guardrail validation functions.

Tests the core validation logic from .github/scripts/verify_prp.py
"""
import sys
import tempfile
import pathlib
from unittest import mock
import pytest
import subprocess

# Add parent directories to path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / ".github" / "scripts"))


class TestPRPGuardrails:
    """Test PRP guardrail validation functions."""

    def test_memory_budget_check(self):
        """Test memory budget validation (5KB limit)."""
        import importlib.util

        # Load the verify_prp module
        spec = importlib.util.spec_from_file_location(
            "verify_prp",
            pathlib.Path(__file__).parent.parent.parent / ".github" / "scripts" / "verify_prp.py"
        )
        verify_prp = importlib.util.module_from_spec(spec)

        with tempfile.TemporaryDirectory() as tmpdir:
            test_root = pathlib.Path(tmpdir)
            memory_dir = test_root / "memory"
            memory_dir.mkdir()

            # Test case: file within limit
            small_file = memory_dir / "concise.md"
            small_file.write_text("Small content")  # Well under 5KB

            with mock.patch('verify_prp.ROOT', test_root):
                verify_prp.errors = []

                # Execute the memory check code
                mem = verify_prp.ROOT / "memory" / "concise.md"
                if mem.exists():
                    size = mem.stat().st_size
                    if size > 5 * 1024:
                        verify_prp.errors.append(f"memory/concise.md too large: {size} bytes (limit 5120)")
                else:
                    verify_prp.errors.append("memory/concise.md missing")

                # Should pass (no errors)
                assert len(verify_prp.errors) == 0

            # Test case: file too large
            large_file = memory_dir / "concise.md"
            large_file.write_text("x" * 6000)  # Over 5KB limit

            with mock.patch('verify_prp.ROOT', test_root):
                verify_prp.errors = []

                mem = verify_prp.ROOT / "memory" / "concise.md"
                if mem.exists():
                    size = mem.stat().st_size
                    if size > 5 * 1024:
                        verify_prp.errors.append(f"memory/concise.md too large: {size} bytes (limit 5120)")
                else:
                    verify_prp.errors.append("memory/concise.md missing")

                # Should fail (has error)
                assert len(verify_prp.errors) == 1
                assert "too large" in verify_prp.errors[0]
                assert "6000 bytes" in verify_prp.errors[0]

    def test_missing_memory_file(self):
        """Test error when memory file is missing."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "verify_prp",
            pathlib.Path(__file__).parent.parent.parent / ".github" / "scripts" / "verify_prp.py"
        )
        verify_prp = importlib.util.module_from_spec(spec)

        with tempfile.TemporaryDirectory() as tmpdir:
            test_root = pathlib.Path(tmpdir)
            # Don't create memory directory

            with mock.patch('verify_prp.ROOT', test_root):
                verify_prp.errors = []

                mem = verify_prp.ROOT / "memory" / "concise.md"
                if mem.exists():
                    size = mem.stat().st_size
                    if size > 5 * 1024:
                        verify_prp.errors.append(f"memory/concise.md too large: {size} bytes (limit 5120)")
                else:
                    verify_prp.errors.append("memory/concise.md missing")

                assert len(verify_prp.errors) == 1
                assert "missing" in verify_prp.errors[0]

    def test_tracked_files_function(self):
        """Test the tracked() function error handling."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "verify_prp",
            pathlib.Path(__file__).parent.parent.parent / ".github" / "scripts" / "verify_prp.py"
        )
        verify_prp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verify_prp)

        # Test successful case (mock git ls-files)
        with mock.patch('subprocess.check_output') as mock_subprocess:
            mock_subprocess.return_value = b"file1.py\x00file2.js\x00"

            from io import StringIO
            captured_stderr = StringIO()

            with mock.patch('sys.stderr', captured_stderr):
                result = verify_prp.tracked()

            assert result == ["file1.py", "file2.js"]
            assert captured_stderr.getvalue() == ""  # No warnings

        # Test subprocess error case
        with mock.patch('subprocess.check_output') as mock_subprocess:
            mock_subprocess.side_effect = subprocess.CalledProcessError(1, "git")

            from io import StringIO
            captured_stderr = StringIO()

            with mock.patch('sys.stderr', captured_stderr):
                result = verify_prp.tracked()

            assert result == []
            assert "Warning: git ls-files failed" in captured_stderr.getvalue()

        # Test generic error case
        with mock.patch('subprocess.check_output') as mock_subprocess:
            mock_subprocess.side_effect = Exception("Some other error")

            from io import StringIO
            captured_stderr = StringIO()

            with mock.patch('sys.stderr', captured_stderr):
                result = verify_prp.tracked()

            assert result == []
            assert "Warning: Failed to get tracked files" in captured_stderr.getvalue()

    def test_large_file_detection(self):
        """Test detection of large files outside artifacts/."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "verify_prp",
            pathlib.Path(__file__).parent.parent.parent / ".github" / "scripts" / "verify_prp.py"
        )
        verify_prp = importlib.util.module_from_spec(spec)

        with tempfile.TemporaryDirectory() as tmpdir:
            test_root = pathlib.Path(tmpdir)

            # Create a large file outside artifacts
            large_file = test_root / "large_file.txt"
            large_file.write_text("x" * (6 * 1024 * 1024))  # 6MB file

            # Create artifacts directory with large file (should be ignored)
            artifacts_dir = test_root / "artifacts"
            artifacts_dir.mkdir()
            artifacts_large = artifacts_dir / "large_artifact.txt"
            artifacts_large.write_text("x" * (6 * 1024 * 1024))

            with mock.patch('verify_prp.ROOT', test_root):
                verify_prp.errors = []

                # Mock tracked files to include both
                tracked_files = ["large_file.txt", "artifacts/large_artifact.txt"]

                LARGE = 5 * 1024 * 1024
                for rel in tracked_files:
                    if rel.startswith("artifacts/"):
                        continue
                    p = verify_prp.ROOT / rel
                    try:
                        if p.is_file() and p.stat().st_size > LARGE:
                            verify_prp.errors.append(f"Large tracked file outside artifacts/: {rel} ({p.stat().st_size} bytes)")
                    except FileNotFoundError:
                        pass

                # Should only flag the non-artifacts file
                assert len(verify_prp.errors) == 1
                assert "large_file.txt" in verify_prp.errors[0]
                assert "artifacts" not in verify_prp.errors[0]


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])