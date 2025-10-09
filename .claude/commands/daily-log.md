Create or update today's agent log in Obsidian vault:

1. Run the daily log script: `/Users/ciarancox/Archon/scripts/daily_agent_log.sh`
2. Show the user the file path and contents
3. Offer to open the file in their editor

The script will:
- Create `Logs/Agents/YYYY-MM-DD.md` if it doesn't exist (using Agent Log template)
- Add a timestamped "Connected via Claude Code MCP ✅" heartbeat
- Preserve existing content if the file already exists
