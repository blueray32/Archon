#!/usr/bin/env python3
import sys, pathlib, subprocess
ROOT = pathlib.Path(".")
errors = []

# 1) memory budget: 5 KB
mem = ROOT / "memory" / "concise.md"
if mem.exists():
  size = mem.stat().st_size
  if size > 5 * 1024:
    errors.append(f"memory/concise.md too large: {size} bytes (limit 5120)")
else:
  errors.append("memory/concise.md missing")

# 2) scan only tracked files for large-size rule (>5MB) outside artifacts/
def tracked():
  try:
    out = subprocess.check_output(["git", "ls-files", "-z"], text=False)
    return [p.decode("utf-8") for p in out.split(b"\x00") if p]
  except subprocess.CalledProcessError as e:
    print(f"Warning: git ls-files failed (exit code {e.returncode}): {e}", file=sys.stderr)
    return []
  except Exception as e:
    print(f"Warning: Failed to get tracked files: {e}", file=sys.stderr)
    return []
LARGE = 5 * 1024 * 1024
for rel in tracked():
  if rel.startswith("artifacts/"): continue
  p = ROOT / rel
  try:
    if p.is_file() and p.stat().st_size > LARGE:
      errors.append(f"Large tracked file outside artifacts/: {rel} ({p.stat().st_size} bytes)")
  except FileNotFoundError:
    pass

# 3) PRP/ADR reference (or PRP files changed) on last commit
try:
  msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"], text=True).strip()
  changed = subprocess.check_output(["git", "diff", "--name-only", "HEAD~1..HEAD"], text=True).splitlines()
except subprocess.CalledProcessError as e:
  print(f"Warning: git command failed (exit code {e.returncode}): {e}", file=sys.stderr)
  msg, changed = "", []
except Exception as e:
  print(f"Warning: Failed to check git history: {e}", file=sys.stderr)
  msg, changed = "", []
has_prp_ref = any("ai_docs/PRPs" in f for f in changed) or ("PRP" in msg or "ADR" in msg)
if not has_prp_ref:
  errors.append("No PRP/ADR reference found in last commit message and no PRP files changed.")

# 4) artifacts directory required
if not (ROOT / "artifacts").exists():
  errors.append("artifacts/ directory missing")

if errors:
  print("PRP Guardrails FAILED:\n- " + "\n- ".join(errors)); sys.exit(1)
print("PRP guardrails passed.")
