#!/usr/bin/env bash
# Daily development workflow automation for Archon
# Usage: scripts/daily_workflow.sh <command> [story]

set -euo pipefail

COMMAND="${1:?Usage: scripts/daily_workflow.sh <start|check|end> [story]}"
STORY="${2:-}"

case "$COMMAND" in
    "start")
        echo "🌅 Starting daily development workflow"
        echo "Current time: $(date)"
        echo "Git status:"
        git status --short
        echo

        # Create daily note in Obsidian if vault exists
        if [[ -n "${OBSIDIAN_VAULT:-}" ]]; then
            DAILY_NOTE="${OBSIDIAN_VAULT}/Daily/$(date +%Y-%m-%d).md"
            if [[ ! -f "$DAILY_NOTE" ]]; then
                mkdir -p "$(dirname "$DAILY_NOTE")"
                cat > "$DAILY_NOTE" <<EOF
# Development Log - $(date +%Y-%m-%d)

## 🎯 Today's Focus
[What are you working on today?]

## 📋 Current Stories
- [ ] [Story Name] - Current status and next steps

## 🔧 Technical Notes
- Code snippets
- Configuration changes
- Problem-solving notes

## 💡 Insights & Decisions
- Architectural decisions made
- Patterns discovered
- Lessons learned

## 🐛 Issues Encountered
- Problems faced
- Solutions attempted
- Resolutions found

## 🔗 Resources Used
- Documentation consulted
- Tools discovered
- Helpful links

## ➡️ Next Steps
- [ ] Priority task 1
- [ ] Priority task 2
- [ ] Priority task 3

---
**Tags**: #daily #development #archon
**Created**: $(date +%Y-%m-%d)
EOF
                echo "📚 Created daily note: $DAILY_NOTE"
            else
                echo "📚 Daily note already exists: $DAILY_NOTE"
            fi
        fi

        echo "✅ Daily workflow started!"
        ;;

    "check")
        if [[ -z "$STORY" ]]; then
            echo "Usage: scripts/daily_workflow.sh check <story>"
            exit 1
        fi

        echo "🔍 Running development checks for $STORY"
        echo

        # Check git status
        echo "📊 Git Status:"
        git status --short
        echo

        # Run QA
        echo "🧪 Running QA checks..."
        make qa STORY="$STORY" || echo "⚠️ QA checks failed"
        echo

        # Check guardrails
        echo "🛡️ Checking guardrails..."
        make verify-prp || echo "⚠️ PRP guardrails failed"
        echo

        # Run implementation audit
        echo "📋 Running implementation audit..."
        scripts/archon_impl_audit.sh "$STORY" || echo "⚠️ Implementation audit failed"
        echo

        echo "✅ Development checks completed!"
        ;;

    "end")
        if [[ -z "$STORY" ]]; then
            echo "Usage: scripts/daily_workflow.sh end <story>"
            exit 1
        fi

        echo "🌆 Ending daily development workflow for $STORY"
        echo

        # Show what was accomplished
        echo "📊 Today's Progress:"
        git log --oneline --since="1 day ago"
        echo

        # Update daily note with progress
        if [[ -n "${OBSIDIAN_VAULT:-}" ]]; then
            DAILY_NOTE="${OBSIDIAN_VAULT}/Daily/$(date +%Y-%m-%d).md"
            if [[ -f "$DAILY_NOTE" ]]; then
                echo "## End of Day Summary - $(date +%H:%M)" >> "$DAILY_NOTE"
                echo "### Commits Today:" >> "$DAILY_NOTE"
                git log --oneline --since="1 day ago" | sed 's/^/- /' >> "$DAILY_NOTE"
                echo "### Story Status: $STORY" >> "$DAILY_NOTE"
                if [[ -f "artifacts/$STORY/notes.md" ]]; then
                    echo "- Progress documented in artifacts/$STORY/notes.md" >> "$DAILY_NOTE"
                fi
                echo "" >> "$DAILY_NOTE"
                echo "📚 Updated daily note: $DAILY_NOTE"
            fi
        fi

        # Run final checks
        echo "🔍 Running final checks..."
        make verify-prp || echo "⚠️ PRP guardrails failed"

        echo "✅ Daily workflow completed!"
        ;;

    *)
        echo "Usage: scripts/daily_workflow.sh <start|check|end> [story]"
        echo
        echo "Commands:"
        echo "  start       - Start daily development (creates daily note)"
        echo "  check STORY - Run development checks for a story"
        echo "  end STORY   - End daily development (update notes, final checks)"
        exit 1
        ;;
esac