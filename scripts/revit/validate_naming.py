#!/usr/bin/env python3
import sys, yaml, pathlib

def main():
    base = pathlib.Path("data/bim/standards")
    naming = base/"naming.yml"
    sheets = base/"sheets.yml"
    if not naming.exists() or not sheets.exists():
        print("Standards files missing. Expected naming.yml and sheets.yml under data/bim/standards/", file=sys.stderr)
        sys.exit(2)
    with open(naming) as f: n = yaml.safe_load(f)
    with open(sheets) as f: s = yaml.safe_load(f)
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
