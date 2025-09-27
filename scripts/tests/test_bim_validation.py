#!/usr/bin/env python3
"""
Unit tests for BIM validation functions.

Tests the core validation logic from scripts/revit/validate_naming.py
"""
import sys
import tempfile
import pathlib
from unittest import mock
import pytest
import yaml

# Add parent directory to path to import the validation script
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))


class TestBIMValidation:
    """Test BIM naming validation functions."""

    def test_valid_yaml_files(self):
        """Test validation with valid YAML files."""
        # Create temporary YAML files
        with tempfile.TemporaryDirectory() as tmpdir:
            base = pathlib.Path(tmpdir)
            naming_file = base / "naming.yml"
            sheets_file = base / "sheets.yml"

            # Create valid naming.yml
            naming_data = {
                "family_prefixes": ["Doors", "Windows"],
                "type_patterns": [
                    {
                        "category": "Doors",
                        "pattern": "^D_[A-Za-z]+$",
                        "example_types": ["D_Internal", "D_External"]
                    }
                ]
            }
            with open(naming_file, 'w') as f:
                yaml.dump(naming_data, f)

            # Create valid sheets.yml
            sheets_data = {
                "number_pattern": "^A-[0-9]{3}$",
                "title_examples": ["GA Floor Plan - Level 01"]
            }
            with open(sheets_file, 'w') as f:
                yaml.dump(sheets_data, f)

            # Mock the script's main function with our test files
            with mock.patch('revit.validate_naming.pathlib.Path') as mock_path:
                mock_path.return_value = base

                # Import and test the main function
                from revit import validate_naming

                # Capture stdout
                from io import StringIO
                captured_output = StringIO()

                with mock.patch('sys.stdout', captured_output):
                    result = validate_naming.main()

                # Assertions
                assert result == 0
                output = captured_output.getvalue()
                assert "BIM Standards Summary" in output
                assert "Doors" in output

    def test_missing_files_error(self):
        """Test error handling when YAML files are missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = pathlib.Path(tmpdir)

            # Mock to point to empty directory
            with mock.patch('revit.validate_naming.pathlib.Path') as mock_path:
                mock_path.return_value = base

                from revit import validate_naming

                # Capture stderr
                from io import StringIO
                captured_error = StringIO()

                with mock.patch('sys.stderr', captured_error):
                    with pytest.raises(SystemExit) as exc_info:
                        validate_naming.main()

                # Assertions
                assert exc_info.value.code == 2
                error_output = captured_error.getvalue()
                assert "Missing BIM standards files" in error_output
                assert "naming.yml" in error_output
                assert "sheets.yml" in error_output

    def test_invalid_yaml_error(self):
        """Test error handling when YAML files contain invalid syntax."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = pathlib.Path(tmpdir)
            naming_file = base / "naming.yml"
            sheets_file = base / "sheets.yml"

            # Create invalid YAML file
            with open(naming_file, 'w') as f:
                f.write("invalid: yaml: content: [unclosed")

            # Create valid sheets file
            with open(sheets_file, 'w') as f:
                yaml.dump({"number_pattern": "A-###"}, f)

            with mock.patch('revit.validate_naming.pathlib.Path') as mock_path:
                mock_path.return_value = base

                from revit import validate_naming

                from io import StringIO
                captured_error = StringIO()

                with mock.patch('sys.stderr', captured_error):
                    with pytest.raises(SystemExit) as exc_info:
                        validate_naming.main()

                assert exc_info.value.code == 2
                error_output = captured_error.getvalue()
                assert "Error parsing" in error_output
                assert "naming.yml" in error_output

    def test_help_flag(self):
        """Test that --help flag works correctly."""
        from revit import validate_naming

        # Mock sys.argv to include --help
        with mock.patch('sys.argv', ['validate_naming.py', '--help']):
            from io import StringIO
            captured_output = StringIO()

            with mock.patch('sys.stdout', captured_output):
                with pytest.raises(SystemExit) as exc_info:
                    validate_naming.main()

            assert exc_info.value.code == 0
            output = captured_output.getvalue()
            assert "Usage:" in output
            assert "reads YAML standards" in output


class TestBIMPatternValidation:
    """Test BIM naming pattern validation logic."""

    def test_door_patterns(self):
        """Test door naming pattern validation."""
        valid_patterns = [
            "D_Internal_Fire_30",
            "D_External",
            "D_Internal_Fire_60",
            "D_Sliding"
        ]

        invalid_patterns = [
            "door_internal",  # Wrong case
            "D-Internal",     # Wrong separator
            "D_",             # Incomplete
            "Internal_D",     # Wrong order
            "D_Internal_Fire_45",  # Invalid fire rating
            "D_Sliding_Glass"      # Extra underscores not allowed
        ]

        door_pattern = r"^D_[A-Za-z]+(_Fire_(30|60))?$"

        import re
        compiled_pattern = re.compile(door_pattern)

        for pattern in valid_patterns:
            assert compiled_pattern.match(pattern), f"Pattern '{pattern}' should be valid"

        for pattern in invalid_patterns:
            assert not compiled_pattern.match(pattern), f"Pattern '{pattern}' should be invalid"

    def test_sheet_number_patterns(self):
        """Test sheet number pattern validation."""
        valid_sheets = [
            "A-001",
            "A-999",
            "A-123"
        ]

        invalid_sheets = [
            "A-1",      # Too short
            "A-1234",   # Too long
            "A001",     # Missing dash
            "B-001"     # Wrong prefix for this test
        ]

        sheet_pattern = r"^A-[0-9]{3}$"

        import re
        compiled_pattern = re.compile(sheet_pattern)

        for sheet in valid_sheets:
            assert compiled_pattern.match(sheet), f"Sheet '{sheet}' should be valid"

        for sheet in invalid_sheets:
            assert not compiled_pattern.match(sheet), f"Sheet '{sheet}' should be invalid"


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])