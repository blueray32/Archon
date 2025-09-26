#!/usr/bin/env python3
import os, sys, json, pathlib

ROOT = pathlib.Path(".")
errors = []

# 1) memory budget
mem = ROOT / "memory" / "concise.md"
if mem.exists():
    size = mem.stat().st_size
    if size > 5 * 1024:
        errors.append(f"memory/concise.md too large: {size} bytes (limit 5120)")
else:
    errors.append("memory/concise.md missing")

# 2) forbid large binaries outside artifacts/
for p in ROOT.rglob("*"):
    if not p.is_file(): continue
    rel = p.relative_to(ROOT)
    s = p.stat().st_size
    if str(rel).startswith("artifacts"): 
        continue
    if s > 5 * 1024 * 1024:  # 5 MB
        errors.append(f"Large file outside artifacts/: {rel} ({s} bytes)")

# 3) PRP/ADR reference check (best-effort on last commit)
import subprocess
try:
    msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"], text=True).strip()
    touched = subprocess.check_output(["git", "diff", "--name-only", "HEAD~1..HEAD"], text=True).splitlines()
except Exception:
    msg = ""
    touched = []

has_prp_ref = any("ai_docs/PRPs" in f for f in touched) or ("PRP" in msg or "ADR" in msg)
if not has_prp_ref:
    errors.append("No PRP/ADR reference found in last commit message and no PRP files changed.")

# 4) Require artifacts directory exists
if not (ROOT / "artifacts").exists():
    errors.append("artifacts/ directory missing")

if errors:
    print("PRP Guardrails FAILED:\n- " + "\n- ".join(errors))
    sys.exit(1)
print("PRP guardrails passed.")
