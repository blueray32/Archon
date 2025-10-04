#!/bin/bash
# Quick PRP Agent Test Script

set -euo pipefail

echo "============================================================"
echo "Testing PRP Agent"
echo "============================================================"
echo ""

# Check if agent is available
echo "Checking agent availability..."
HEALTH=$(curl -s http://localhost:8052/health || echo '{}')
if echo "$HEALTH" | grep -q '"prp"'; then
  echo "✓ PRP agent is available"
else
  echo "❌ PRP agent not found in health check"
  echo "Response: $HEALTH"
  exit 1
fi
echo ""

# Test 1: Basic chat
echo "Test 1: Basic Question"
echo "Question: 'What is Archon?'"
echo ""
RESP1=$(curl -s -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is Archon?",
    "context": {"session_id": "test-basic"}
  }')

if echo "$RESP1" | jq -e '.success == true' >/dev/null 2>&1; then
  echo "✓ Test 1 passed"
  echo "Response:"
  echo "$RESP1" | jq -r '.result.output // .result' | head -5
else
  echo "❌ Test 1 failed"
  echo "$RESP1" | jq .
fi
echo ""
echo "---"
echo ""

# Test 2: Conversation continuity
echo "Test 2: Conversation Continuity"
echo "Message 1: 'Tell me about the agents service'"
echo ""
RESP2=$(curl -s -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "Tell me about the agents service",
    "context": {"session_id": "test-continuity"}
  }')

if echo "$RESP2" | jq -e '.success == true' >/dev/null 2>&1; then
  echo "✓ Message 1 successful"
  echo "Response:"
  echo "$RESP2" | jq -r '.result.output // .result' | head -5
else
  echo "❌ Message 1 failed"
fi
echo ""

sleep 1

echo "Message 2: 'How do I add a new agent to it?'"
echo "(Should remember context from message 1)"
echo ""
RESP3=$(curl -s -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "How do I add a new agent to it?",
    "context": {"session_id": "test-continuity"}
  }')

if echo "$RESP3" | jq -e '.success == true' >/dev/null 2>&1; then
  echo "✓ Message 2 successful"
  echo "Response:"
  echo "$RESP3" | jq -r '.result.output // .result' | head -5
else
  echo "❌ Message 2 failed"
fi
echo ""
echo "---"
echo ""

# Test 3: PRP-specific question
echo "Test 3: PRP System Question"
echo "Question: 'What is the PRP system and how does it work?'"
echo ""
RESP4=$(curl -s -X POST http://localhost:8052/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "prp",
    "prompt": "What is the PRP system and how does it work?",
    "context": {"session_id": "test-prp"}
  }')

if echo "$RESP4" | jq -e '.success == true' >/dev/null 2>&1; then
  echo "✓ Test 3 passed"
  echo "Response:"
  echo "$RESP4" | jq -r '.result.output // .result' | head -10

  # Check if it retrieved PRP context
  if echo "$RESP4" | jq -e '.result.sources[]? | select(.type == "prp")' >/dev/null 2>&1; then
    echo ""
    echo "✓ Successfully retrieved PRP context"
  fi
else
  echo "❌ Test 3 failed"
fi
echo ""

echo "============================================================"
echo "Test Summary"
echo "============================================================"
echo ""
echo "✓ All tests completed"
echo ""
echo "View full responses with: jq . (pipe curl output)"
echo "Check logs with: docker compose logs archon-agents --tail=50"
echo "============================================================"