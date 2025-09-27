#!/usr/bin/env python3
import sys, yaml, pathlib

def main():
    base = pathlib.Path("data/bim/standards")
    naming = base/"naming.yml"
    sheets = base/"sheets.yml"

    # Check for missing files with specific reporting
    missing = []
    if not naming.exists(): missing.append(str(naming))
    if not sheets.exists(): missing.append(str(sheets))
    if missing:
        print(f"Missing BIM standards files: {', '.join(missing)}", file=sys.stderr)
        sys.exit(2)

    # Load YAML files with error handling
    try:
        with open(naming) as f:
            n = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Error parsing {naming}: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error reading {naming}: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        with open(sheets) as f:
            s = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Error parsing {sheets}: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error reading {sheets}: {e}", file=sys.stderr)
        sys.exit(2)
    print("BIM Standards Summary")
    print("- Families:", ", ".join(n.get("family_prefixes", [])))
    print("- Doors pattern:", next((tp["pattern"] for tp in n.get("type_patterns", []) if tp.get("category")=="Doors"), "n/a"))
    print("- Sheet number pattern:", s.get("number_pattern"))
    print("OK")
    return 0

if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: scripts/revit/validate_naming.py  # reads YAML standards and prints a summary")
        sys.exit(0)
    sys.exit(main())
