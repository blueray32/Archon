#!/usr/bin/env bash
set -euo pipefail
tar -czf artifacts/summaries.tgz ai_docs/PRDs ai_docs/PRPs || true
echo "Wrote artifacts/summaries.tgz"
