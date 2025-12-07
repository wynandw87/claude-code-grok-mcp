# Claude Code + Grok MCP Server Setup Script for Windows
# Usage: .\setup.ps1 -ApiKey "YOUR_XAI_API_KEY"

param(
    [Parameter(Mandatory=$true)]
    [string]$ApiKey
)

$ErrorActionPreference = "Stop"

Write-Host "Claude Code + Grok MCP Server Setup" -ForegroundColor Blue
Write-Host ""

# Check Python version
Write-Host "Checking requirements..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
            Write-Host "Python 3.10+ is required. Found: $pythonVersion" -ForegroundColor Red
            exit 1
        }
        Write-Host "Python $major.$minor found" -ForegroundColor Green
    }
} catch {
    Write-Host "Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Check Claude Code CLI
try {
    $claudeVersion = claude --version 2>&1
    Write-Host "Claude Code CLI found" -ForegroundColor Green
} catch {
    Write-Host "Claude Code CLI not found. Please install it first:" -ForegroundColor Red
    Write-Host "npm install -g @anthropic-ai/claude-code" -ForegroundColor Yellow
    exit 1
}

# Install Python dependencies
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
pip install xai-sdk --quiet

# Get the directory where this script is located
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverPath = Join-Path $scriptDir "server.py"

# Remove any existing MCP configuration
Write-Host ""
Write-Host "Configuring Claude Code..." -ForegroundColor Yellow
try {
    claude mcp remove Grok 2>$null
} catch {
    # Ignore if not exists
}

# Add MCP server with user scope and API key as environment variable
claude mcp add -s user -t stdio Grok python $serverPath -e "XAI_API_KEY=$ApiKey"

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "You can now use Grok in Claude Code from any directory!" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Restart Claude Code for changes to take effect." -ForegroundColor Yellow
Write-Host ""
Write-Host "Available tools:" -ForegroundColor White
Write-Host "  - Grok - ask" -ForegroundColor Gray
Write-Host "  - Grok - code_review" -ForegroundColor Gray
Write-Host "  - Grok - brainstorm" -ForegroundColor Gray
Write-Host ""
Write-Host "To change the default model, run:" -ForegroundColor Gray
Write-Host "  python $serverPath config --list-models" -ForegroundColor Gray
Write-Host "  python $serverPath config --model grok-4" -ForegroundColor Gray
