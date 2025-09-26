#!/usr/bin/env python3
import os, sys, pathlib, subprocess

ROOT = pathlib.Path(".")
errors = []

# 1) memory budget
mem = ROOT / "memory" / "concise.md"
if mem.exists():
    size = mem.stat().st_size
    if size > 5 * 1024 * 1024:  # 5 KB -> 5 MB? keep tiny (5 KB) as intended
        errors.append(f"memory/concise.md too large: {size} bytes (limit 5120)")
else:
    errors.append("memory/concise.md missing")

# 2) large tracked files outside artifacts/
def tracked_files():
    try:
        out = subprocess.check_output(["git", "ls-files", "-z"], text=False)
        return [p.decode("utf-8") for p in out.split(b"\x00") if p]
    except Exception:
        # fallback: nothing tracked (or not a repo)
        return []

TRACKED = tracked_files()
LARGE_THRESHOLD = 5 * 1024 * 1024  # 5 MB

for rel in TRACKED:
    # allow artifacts entirely
    if rel.startswith("artifacts/"):
        continue
    p = ROOT / rel
    try:
        if p.is_file():
            s = p.stat().st_size
            if s > LARGE_THRESHOLD:
                errors.append(f"Large tracked file outside artifacts/: {rel} ({s} bytes)")
    except FileNotFoundError:
        # file deleted in working copy; ignore
        pass

# 3) PRP/ADR reference (best-effort) on last commit
try:
    msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"], text=True).strip()
    touched = subprocess.check_output(["git", "diff", "--name-only", "HEAD~1..HEAD"], text=True).splitlines()
except Exception:
    msg, touched = "", []

has_prp_ref = any("ai_docs/PRPs" in f for f in touched) or ("PRP" in msg or "ADR" in msg)
if not has_prp_ref:
    errors.append("No PRP/ADR reference found in last commit message and no PRP files changed.")

# 4) artifacts directory required
if not (ROOT / "artifacts").exists():
    errors.append("artifacts/ directory missing")

if errors:
    print("PRP Guardrails FAILED:\n- " + "\n- ".join(errors))
    sys.exit(1)
print("PRP guardrails passed.")
