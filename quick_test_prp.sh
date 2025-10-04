#!/bin/bash
# Quick PRP agent smoke tests (requires agents service running on :8052)

set -euo pipefail

echo "Test 1: Basic chat…"
curl -s -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is Archon?",
    "context": {"session_id": "test-1"}
  }' | jq -r '.result.output // .error // "No response"'
echo ""

echo "Test 2: Conversation continuity…"
echo "Message 1:"
curl -s -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "Tell me about the agents service",
    "context": {"session_id": "test-2"}
  }' | jq -r '.result.output // "No response"'
echo ""

echo "Message 2 (should reference prior context):"
curl -s -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "How do I add a new one?",
    "context": {"session_id": "test-2"}
  }' | jq -r '.result.output // "No response"'
echo ""