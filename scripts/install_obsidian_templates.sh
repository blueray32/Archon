#!/usr/bin/env bash
set -euo pipefail

# Install Obsidian Templater templates to vault
# Usage: ./install_obsidian_templates.sh [vault_path]

VAULT="${1:-${OBSIDIAN_VAULT:-/Users/ciarancox/Documents/ArchonVault}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$SCRIPT_DIR/../templates/obsidian"
VAULT_TEMPLATES="$VAULT/.templates"

echo "🎨 Installing Obsidian Templater templates..."
echo ""
echo "  Source: $TEMPLATES_DIR"
echo "  Vault:  $VAULT"
echo "  Target: $VAULT_TEMPLATES"
echo ""

# Validate vault exists
if [[ ! -d "$VAULT" ]]; then
    echo "❌ Error: Vault not found at $VAULT"
    echo ""
    echo "Usage:"
    echo "  $0 /path/to/vault"
    echo "  OBSIDIAN_VAULT=/path/to/vault $0"
    exit 1
fi

# Validate templates exist
if [[ ! -d "$TEMPLATES_DIR" ]]; then
    echo "❌ Error: Templates not found at $TEMPLATES_DIR"
    exit 1
fi

# Create .templates directory if it doesn't exist
if [[ ! -d "$VAULT_TEMPLATES" ]]; then
    echo "📁 Creating .templates directory..."
    mkdir -p "$VAULT_TEMPLATES"
fi

# Offer symlink or copy
echo "Choose installation method:"
echo "  1) Symlink (recommended - templates stay updated with repo)"
echo "  2) Copy (standalone - won't receive updates)"
echo ""
read -p "Enter choice (1 or 2): " choice

case "$choice" in
    1)
        echo ""
        echo "📎 Creating symlink..."
        LINK_TARGET="$VAULT_TEMPLATES/archon"
        if [[ -L "$LINK_TARGET" ]]; then
            echo "⚠️  Symlink already exists at $LINK_TARGET"
            read -p "Remove and recreate? (y/n): " confirm
            if [[ "$confirm" == "y" ]]; then
                rm "$LINK_TARGET"
            else
                echo "❌ Cancelled"
                exit 0
            fi
        fi
        ln -s "$TEMPLATES_DIR" "$LINK_TARGET"
        echo "✅ Symlink created: $LINK_TARGET -> $TEMPLATES_DIR"
        echo ""
        echo "📝 Next steps:"
        echo "  1. In Obsidian: Settings → Templater → Template folder location"
        echo "  2. Set to: .templates/archon"
        echo "  3. (Optional) Enable Folder Templates for Logs/Agents/"
        ;;
    2)
        echo ""
        echo "📋 Copying templates..."
        cp -v "$TEMPLATES_DIR"/*.md "$VAULT_TEMPLATES/"
        echo "✅ Templates copied to $VAULT_TEMPLATES/"
        echo ""
        echo "📝 Next steps:"
        echo "  1. In Obsidian: Settings → Templater → Template folder location"
        echo "  2. Set to: .templates"
        echo "  3. (Optional) Enable Folder Templates for Logs/Agents/"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "🎉 Installation complete!"
echo ""
echo "Available templates:"
ls -1 "$TEMPLATES_DIR"/*.md | xargs -n1 basename
echo ""
echo "Documentation: templates/obsidian/README.md"
