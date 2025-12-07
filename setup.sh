#!/bin/bash
# Claude Code + Grok MCP Server Setup Script
# Usage: ./setup.sh YOUR_XAI_API_KEY
# Installs with 'user' scope (available in all your projects)

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

echo -e "${BLUE}Claude Code + Grok MCP Server Setup${NC}"
echo ""

# Check if API key was provided
API_KEY="$1"
if [ -z "$API_KEY" ]; then
    echo -e "${RED}Please provide your xAI API key${NC}"
    echo "Usage: ./setup.sh YOUR_XAI_API_KEY"
    echo ""
    echo "Get an API key at: https://console.x.ai/"
    exit 1
fi

# Check Python version
echo "Checking requirements..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is required but not installed.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
    echo -e "${RED}Python 3.10+ is required. Found: Python $PYTHON_VERSION${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Check Claude Code
if ! command -v claude &> /dev/null; then
    echo -e "${RED}Claude Code CLI not found. Please install it first:${NC}"
    echo "npm install -g @anthropic-ai/claude-code"
    exit 1
fi
echo -e "${GREEN}✓ Claude Code CLI found${NC}"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install xai-sdk --quiet

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Remove any existing MCP configuration
echo ""
echo "Configuring Claude Code..."
claude mcp remove Grok 2>/dev/null || true

# Add MCP server with user scope and API key as environment variable
claude mcp add -s user -t stdio Grok python3 "$SCRIPT_DIR/server.py" -e "XAI_API_KEY=$API_KEY"

echo ""
echo -e "${GREEN}✓ Setup complete!${NC}"
echo ""
echo -e "You can now use Grok in Claude Code from any directory!"
echo ""
echo -e "${YELLOW}IMPORTANT: Restart Claude Code for changes to take effect.${NC}"
echo ""
echo "Available tools:"
echo -e "${GRAY}  • Grok - ask${NC}"
echo -e "${GRAY}  • Grok - code_review${NC}"
echo -e "${GRAY}  • Grok - brainstorm${NC}"
echo ""
echo -e "${GRAY}To change the default model, run:${NC}"
echo -e "${GRAY}  python3 $SCRIPT_DIR/server.py config --list-models${NC}"
echo -e "${GRAY}  python3 $SCRIPT_DIR/server.py config --model grok-4${NC}"
