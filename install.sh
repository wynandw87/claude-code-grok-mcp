#!/bin/bash
# One-line installer for Claude Code + Grok MCP Server
# Usage: curl -sSL https://raw.githubusercontent.com/wynandw87/claude-code-grok-mcp/main/install.sh | bash

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Claude Code + Grok MCP Server Installer${NC}"
echo ""

# Check requirements
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is required. Please install it first.${NC}"
    exit 1
fi

if ! command -v claude &> /dev/null; then
    echo -e "${RED}Claude Code CLI not found. Please install it first:${NC}"
    echo "npm install -g @anthropic-ai/claude-code"
    exit 1
fi

# Clone the repository
echo "Downloading Grok MCP Server..."
INSTALL_DIR="$HOME/.claude-mcp-servers/grok-repo"
rm -rf "$INSTALL_DIR"
git clone --quiet https://github.com/wynandw87/claude-code-grok-mcp.git "$INSTALL_DIR"

# Get API key
echo ""
echo -e "${YELLOW}Please enter your xAI API key:${NC}"
echo "   (Get one at https://console.x.ai/)"
read -p "API Key: " API_KEY

if [ -z "$API_KEY" ]; then
    echo -e "${RED}API key is required${NC}"
    exit 1
fi

# Run setup
cd "$INSTALL_DIR"
chmod +x setup.sh
./setup.sh "$API_KEY"

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo -e "${YELLOW}To change the default model later, run:${NC}"
echo -e "  python3 $INSTALL_DIR/server.py config --list-models"
echo -e "  python3 $INSTALL_DIR/server.py config --model grok-4"
