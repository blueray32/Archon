#!/usr/bin/env python3
"""
Core pattern validation tests for BIM standards.
These are the essential tests that validate our BIM naming patterns work correctly.
"""
import re
import pytest


class TestBIMPatterns:
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
        compiled_pattern = re.compile(door_pattern)

        for pattern in valid_patterns:
            assert compiled_pattern.match(pattern), f"Pattern '{pattern}' should be valid"

        for pattern in invalid_patterns:
            assert not compiled_pattern.match(pattern), f"Pattern '{pattern}' should be invalid"

    def test_window_patterns(self):
        """Test window naming pattern validation."""
        valid_patterns = [
            "W_Alu_Double",
            "W_Timber_Triple",
            "W_Steel",
            "W_Glass_Double"
        ]

        invalid_patterns = [
            "window_alu",     # Wrong case
            "W-Alu",          # Wrong separator
            "W_",             # Incomplete
            "Alu_W"           # Wrong order
        ]

        window_pattern = r"^W_[A-Za-z]+(_Double|_Triple)?$"
        compiled_pattern = re.compile(window_pattern)

        for pattern in valid_patterns:
            assert compiled_pattern.match(pattern), f"Pattern '{pattern}' should be valid"

        for pattern in invalid_patterns:
            assert not compiled_pattern.match(pattern), f"Pattern '{pattern}' should be invalid"

    def test_wall_patterns(self):
        """Test wall naming pattern validation."""
        valid_patterns = [
            "Wall_Partition_92",
            "Wall_External_215",
            "Wall_Internal_100",
            "Wall_Structural_300"
        ]

        invalid_patterns = [
            "wall_partition",  # Wrong case
            "Wall-Partition",  # Wrong separator
            "Wall_",           # Incomplete
            "Partition_Wall"   # Wrong order
        ]

        wall_pattern = r"^Wall_[A-Za-z0-9_]+$"
        compiled_pattern = re.compile(wall_pattern)

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
        compiled_pattern = re.compile(sheet_pattern)

        for sheet in valid_sheets:
            assert compiled_pattern.match(sheet), f"Sheet '{sheet}' should be valid"

        for sheet in invalid_sheets:
            assert not compiled_pattern.match(sheet), f"Sheet '{sheet}' should be invalid"

    def test_yaml_schema_structure(self):
        """Test that our BIM YAML files have the expected structure."""
        import yaml
        from pathlib import Path

        # Test naming.yml structure
        naming_file = Path("data/bim/standards/naming.yml")
        assert naming_file.exists(), "naming.yml should exist"

        with open(naming_file) as f:
            naming_data = yaml.safe_load(f)

        assert "family_prefixes" in naming_data, "naming.yml should have family_prefixes"
        assert "type_patterns" in naming_data, "naming.yml should have type_patterns"
        assert isinstance(naming_data["family_prefixes"], list), "family_prefixes should be a list"
        assert isinstance(naming_data["type_patterns"], list), "type_patterns should be a list"

        # Test each type pattern has required fields
        for pattern in naming_data["type_patterns"]:
            assert "category" in pattern, "type_patterns should have category"
            assert "pattern" in pattern, "type_patterns should have pattern"
            assert "example_types" in pattern, "type_patterns should have example_types"

        # Test sheets.yml structure
        sheets_file = Path("data/bim/standards/sheets.yml")
        assert sheets_file.exists(), "sheets.yml should exist"

        with open(sheets_file) as f:
            sheets_data = yaml.safe_load(f)

        assert "number_pattern" in sheets_data, "sheets.yml should have number_pattern"
        assert "title_examples" in sheets_data, "sheets.yml should have title_examples"


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])