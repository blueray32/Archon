#!/usr/bin/env bash
#
# Production Obsidian Sync - Safe Full Run
#
# This script runs the full orchestration with safe defaults
# and proper error handling.

set -euo pipefail

# Configuration
VAULT_PATH="${OBSIDIAN_VAULT:-/Users/ciarancox/Documents/ArchonVault}"
CONCURRENCY="${SYNC_CONCURRENCY:-5}"
SHARD_SIZE="${SYNC_SHARD_SIZE:-2000}"
STATE_FILE="${SYNC_STATE_FILE:-sync_state.json}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Pre-flight checks
preflight_checks() {
    log_info "Running pre-flight checks..."

    # Check vault exists
    if [[ ! -d "$VAULT_PATH" ]]; then
        log_error "Vault not found: $VAULT_PATH"
        log_error "Set OBSIDIAN_VAULT environment variable"
        exit 1
    fi

    # Check Ollama
    if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_error "Ollama not running at http://localhost:11434"
        log_error "Start with: ollama serve"
        exit 1
    fi

    # Check model available
    if ! ollama list | grep -q "qwen2.5:3b"; then
        log_warn "Model qwen2.5:3b not found"
        log_info "Pulling model..."
        ollama pull qwen2.5:3b
    fi

    log_info "✓ All checks passed"
}

# Main execution
main() {
    local mode="${1:-safe}"

    log_info "Starting Obsidian Orchestration"
    log_info "Vault: $VAULT_PATH"
    log_info "Mode: $mode"
    log_info "Concurrency: $CONCURRENCY"
    log_info "Shard size: $SHARD_SIZE"
    echo ""

    # Run pre-flight checks
    preflight_checks
    echo ""

    # Change to python directory
    cd "$(dirname "$0")/.."

    case "$mode" in
        safe)
            log_info "Running SAFE mode (dry-run first, then execute)"
            log_info "Step 1: Dry run..."

            uv run python src/scripts/orchestrate_obsidian_sync_production.py \
                --vault "$VAULT_PATH" \
                --auto-tag \
                --concurrency "$CONCURRENCY" \
                --shard-size "$SHARD_SIZE" \
                --state-file "$STATE_FILE" \
                --dry-run

            echo ""
            log_warn "Dry run complete. Review the plan above."
            read -p "Continue with execution? (yes/no): " -r
            echo

            if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
                log_info "Cancelled by user"
                exit 0
            fi

            log_info "Step 2: Executing..."
            uv run python src/scripts/orchestrate_obsidian_sync_production.py \
                --vault "$VAULT_PATH" \
                --auto-tag \
                --concurrency "$CONCURRENCY" \
                --shard-size "$SHARD_SIZE" \
                --state-file "$STATE_FILE" \
                --git-commit
            ;;

        fast)
            log_info "Running FAST mode (execute immediately, no embeddings)"
            uv run python src/scripts/orchestrate_obsidian_sync_production.py \
                --vault "$VAULT_PATH" \
                --auto-tag \
                --concurrency 8 \
                --shard-size "$SHARD_SIZE" \
                --state-file "$STATE_FILE"
            ;;

        full)
            log_info "Running FULL mode (execute with embeddings)"
            uv run python src/scripts/orchestrate_obsidian_sync_production.py \
                --vault "$VAULT_PATH" \
                --auto-tag \
                --create-embeddings \
                --concurrency "$CONCURRENCY" \
                --shard-size "$SHARD_SIZE" \
                --state-file "$STATE_FILE" \
                --git-commit
            ;;

        resume)
            log_info "Running RESUME mode (continue from state file)"
            if [[ ! -f "$STATE_FILE" ]]; then
                log_error "State file not found: $STATE_FILE"
                exit 1
            fi

            uv run python src/scripts/orchestrate_obsidian_sync_production.py \
                --vault "$VAULT_PATH" \
                --auto-tag \
                --concurrency "$CONCURRENCY" \
                --shard-size "$SHARD_SIZE" \
                --state-file "$STATE_FILE"
            ;;

        dry-run)
            log_info "Running DRY-RUN mode (no changes)"
            uv run python src/scripts/orchestrate_obsidian_sync_production.py \
                --vault "$VAULT_PATH" \
                --auto-tag \
                --concurrency "$CONCURRENCY" \
                --shard-size "$SHARD_SIZE" \
                --dry-run
            ;;

        *)
            log_error "Unknown mode: $mode"
            echo ""
            echo "Usage: $0 [mode]"
            echo ""
            echo "Modes:"
            echo "  safe      - Dry run first, then prompt (default)"
            echo "  fast      - Execute immediately, higher concurrency"
            echo "  full      - Execute with embeddings + git commit"
            echo "  resume    - Resume from state file"
            echo "  dry-run   - Plan only, no changes"
            echo ""
            echo "Environment variables:"
            echo "  OBSIDIAN_VAULT     - Path to vault (default: /Users/ciarancox/Documents/ArchonVault)"
            echo "  SYNC_CONCURRENCY   - Max concurrent calls (default: 5)"
            echo "  SYNC_SHARD_SIZE    - Shard size (default: 2000)"
            echo "  SYNC_STATE_FILE    - State file path (default: sync_state.json)"
            exit 1
            ;;
    esac

    echo ""
    log_info "✓ Orchestration complete!"
    log_info "Check artifacts/ directory for results"
}

# Trap Ctrl+C
trap 'log_warn "Interrupted! State saved to $STATE_FILE"; exit 130' INT

# Run
main "$@"
