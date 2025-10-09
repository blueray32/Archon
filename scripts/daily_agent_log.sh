#!/usr/bin/env bash
set -euo pipefail

# Create daily agent log with Archon template
# Usage: ./daily_agent_log.sh [YYYY-MM-DD]

VAULT="${OBSIDIAN_VAULT:-/Users/ciarancox/Documents/ArchonVault}"
DATE="${1:-$(date +%Y-%m-%d)}"
LOG_FILE="$VAULT/Logs/Agents/$DATE.md"
TEMPLATE_PATH="$VAULT/.templates/archon/Agent Log.md"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}📝 Creating daily agent log for $DATE${NC}"
echo ""

# Ensure Logs/Agents directory exists
if [[ ! -d "$VAULT/Logs/Agents" ]]; then
    echo -e "${YELLOW}📁 Creating Logs/Agents directory...${NC}"
    mkdir -p "$VAULT/Logs/Agents"
fi

# Check if log already exists
if [[ -f "$LOG_FILE" ]]; then
    echo -e "${GREEN}✅ Log already exists: $LOG_FILE${NC}"
    echo ""
    echo -e "${BLUE}Adding Codex heartbeat...${NC}"

    # Add heartbeat with timestamp
    TIMESTAMP=$(date +"%H:%M")
    echo "" >> "$LOG_FILE"
    echo "### $TIMESTAMP - Codex Session" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    echo "✅ Connected via Claude Code MCP" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"

    echo -e "${GREEN}✅ Heartbeat added to existing log${NC}"
    echo ""
    echo "File: $LOG_FILE"
    exit 0
fi

# Create new log from template
if [[ -f "$TEMPLATE_PATH" ]]; then
    echo -e "${BLUE}Using template: $TEMPLATE_PATH${NC}"

    # Process template: replace Templater syntax with actual values
    sed -e "s/<% tp.date.now(\"YYYY-MM-DD\") %>/$DATE/g" \
        -e "s/<% tp.date.now(\"dddd, MMMM DD, YYYY\") %>/$(date -j -f "%Y-%m-%d" "$DATE" "+%A, %B %d, %Y" 2>/dev/null || date "+%A, %B %d, %Y")/g" \
        -e "s/<% tp.date.now(\"HH:mm\") %>/$(date +%H:%M)/g" \
        "$TEMPLATE_PATH" > "$LOG_FILE"

    # Add Codex heartbeat after Session Overview
    TIMESTAMP=$(date +"%H:%M")
    {
        echo ""
        echo "### $TIMESTAMP - Session Start"
        echo ""
        echo "✅ Connected via Claude Code MCP"
        echo ""
    } >> "$LOG_FILE"

    echo -e "${GREEN}✅ Created new log from template${NC}"
else
    echo -e "${YELLOW}⚠️  Template not found, creating basic log...${NC}"

    # Create basic log without template
    TIMESTAMP=$(date +"%H:%M")
    cat > "$LOG_FILE" <<EOF
---
title: Agent Log - $DATE
date: $DATE
area: archon
service: ops
status: active
tags:
  - archon
  - ops
  - agent-log
  - daily
---

# Agent Log - $(date -j -f "%Y-%m-%d" "$DATE" "+%A, %B %d, %Y" 2>/dev/null || date "+%A, %B %d, %Y")

## 📋 Session Overview

**Start Time:** $TIMESTAMP
**Agent:** Claude Code
**Focus Area:**

### $TIMESTAMP - Session Start

✅ Connected via Claude Code MCP

## 🎯 Objectives

- [ ]

## 🔄 Progress Log



## 🔍 Key Insights



## ✅ Completed

- [ ]

## 📝 Notes



## 🔗 Related

- [[Archon]]

---

**Status:** In Progress
EOF

    echo -e "${GREEN}✅ Created basic log${NC}"
fi

echo ""
echo "File: $LOG_FILE"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  • Open in Obsidian: obsidian://open?vault=ArchonVault&file=Logs/Agents/$DATE.md"
echo "  • Open in editor: code '$LOG_FILE'"
echo ""
