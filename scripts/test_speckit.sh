#!/usr/bin/env bash
set -euo pipefail

# Tests for scripts/speckit.sh
# - Ensures README.md and spec.md are created with sensible fallbacks
# - Verifies behavior when templates are present and when they are absent

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TPL_DIR="$ROOT_DIR/tools/spec-kit/templates"
BACKUP_DIR="$ROOT_DIR/tools/spec-kit/templates.bak.test"

ts="$(date +%s)"
name_with_tpl="__speckit_test_with_tpl_${ts}"
name_without_tpl="__speckit_test_without_tpl_${ts}"

cleanup() {
  # Remove created spec dirs
  rm -rf "$ROOT_DIR/ai_docs/specs/$name_with_tpl" || true
  rm -rf "$ROOT_DIR/ai_docs/specs/$name_without_tpl" || true
  # Restore templates if we backed them up
  if [ -d "$BACKUP_DIR" ]; then
    rm -rf "$TPL_DIR" || true
    mv "$BACKUP_DIR" "$TPL_DIR"
  fi
}
trap cleanup EXIT

assert() {
  local msg="$1"; shift
  if ! "$@"; then
    echo "[FAIL] $msg" >&2
    exit 1
  fi
}

assert_file_contains() {
  local file="$1"; shift
  local pattern="$1"; shift
  if ! grep -qE "$pattern" "$file"; then
    echo "[FAIL] Expected pattern not found in $file: $pattern" >&2
    exit 1
  fi
}

echo "[TEST] Case 1: templates present (spec-template.md available)"
bash "$ROOT_DIR/scripts/speckit.sh" "$name_with_tpl"

spec1="$ROOT_DIR/ai_docs/specs/$name_with_tpl/spec.md"
readme1="$ROOT_DIR/ai_docs/specs/$name_with_tpl/README.md"

assert "spec.md should exist (case 1)" test -f "$spec1"
assert "README.md should exist (case 1)" test -f "$readme1"

# spec.md should be copied from spec-template.md when spec.md missing in templates
assert_file_contains "$spec1" "Feature Specification|Section Requirements|Execution Flow"

# README likely from placeholder as templates typically do not provide one
first_readme_line="$(head -n1 "$readme1" || true)"
expected_readme_line="# $name_with_tpl"
assert "README placeholder should be used (case 1)" bash -c "[ \"$first_readme_line\" = \"$expected_readme_line\" ]"

echo "[TEST] Case 2: templates directory absent (force placeholders)"
if [ -d "$TPL_DIR" ]; then
  mv "$TPL_DIR" "$BACKUP_DIR"
fi

bash "$ROOT_DIR/scripts/speckit.sh" "$name_without_tpl"

spec2="$ROOT_DIR/ai_docs/specs/$name_without_tpl/spec.md"
readme2="$ROOT_DIR/ai_docs/specs/$name_without_tpl/README.md"

assert "spec.md should exist (case 2)" test -f "$spec2"
assert "README.md should exist (case 2)" test -f "$readme2"

# Placeholders expected when templates are absent
first_spec_line="$(head -n1 "$spec2" || true)"
expected_spec_line="# Spec: $name_without_tpl"
assert "spec placeholder should be used (case 2)" bash -c "[ \"$first_spec_line\" = \"$expected_spec_line\" ]"

first_readme_line2="$(head -n1 "$readme2" || true)"
expected_readme_line2="# $name_without_tpl"
assert "README placeholder should be used (case 2)" bash -c "[ \"$first_readme_line2\" = \"$expected_readme_line2\" ]"

echo "[OK] All speckit.sh tests passed"

