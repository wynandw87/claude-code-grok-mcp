# Claude Code + Grok MCP Server

Connect Claude Code with xAI's Grok AI for powerful AI collaboration. Ask Grok questions, get code reviews, and brainstorm ideas - all within Claude Code!

## Quick Start

### Step 1: Get Your API Key

1. Go to [console.x.ai](https://console.x.ai/)
2. Create an account or sign in
3. Generate an API key
4. Copy the key (you'll need it in Step 3)

### Step 2: Install Prerequisites

- **Python 3.10+** - [Download here](https://www.python.org/downloads/)
- **Claude Code CLI** - [Installation guide](https://docs.anthropic.com/claude-code)
- **xai-sdk** - Install with: `pip install xai-sdk`

### Step 3: Install the MCP Server

#### Linux/macOS

```bash
# Clone the repository
git clone https://github.com/wynandw87/claude-code-grok-mcp.git
cd claude-code-grok-mcp

# Install the MCP server (replace YOUR_API_KEY with your actual key)
claude mcp add -s user -t stdio Grok python server.py -e "XAI_API_KEY=YOUR_API_KEY"
```

#### Windows (PowerShell)

```powershell
# Clone the repository
git clone https://github.com/wynandw87/claude-code-grok-mcp.git
cd claude-code-grok-mcp

# Install the MCP server (replace YOUR_API_KEY with your actual key)
claude mcp add -s user -t stdio Grok python server.py -e "XAI_API_KEY=YOUR_API_KEY"
```

### Step 4: Restart Claude Code

Close and reopen Claude Code. The Grok tools are now available!

### Step 5: Verify Installation

```bash
claude mcp list
```

You should see `Grok` listed with a ✓ Connected status.

---

## Usage

Once installed, just use trigger phrases to invoke Grok:

| Trigger | Tool | Example |
|---------|------|---------|
| `use grok`, `ask grok`, `grok:` | Ask | "use grok: what is quantum computing?" |
| `grok review`, `have grok review` | Code Review | "grok review this function for security" |
| `grok brainstorm`, `grok ideas` | Brainstorm | "grok brainstorm ideas for authentication" |

Or ask naturally:

- *"Ask Grok what it thinks about this approach"*
- *"Have Grok review this code for security issues"*
- *"Brainstorm with Grok about scaling strategies"*

---

## Changing the Default Model

The default model is `grok-4-1-fast-reasoning`. To change it:

### 1. See available models

Run this from the `claude-code-grok-mcp` folder you cloned:

```bash
python server.py config --list-models
```

Output:
```
Available Grok models:
--------------------------------------------------
  grok-4
    Flagship model (256K context)
  grok-4-1-fast-reasoning *
    Fast reasoning model (2M context) - Default
  grok-4-fast
    Fast with reasoning (2M context)
  grok-3
    Previous flagship (128K context)
  grok-3-mini
    Lighter/cheaper option (128K context)
  grok-2
    Grok 2 (128K context)
  grok-2-vision
    Vision capable (32K context)

* = currently selected
```

### 2. Set your preferred model

```bash
python server.py config --model grok-4
```

### 3. Restart Claude Code

Close and reopen Claude Code for the change to take effect.

---

## Troubleshooting

### Fix API Key (typo or needs updating)

If you entered the wrong API key, reinstall with the correct one:

```bash
# Remove the old installation
claude mcp remove Grok

# Reinstall with the correct API key
claude mcp add -s user -t stdio Grok python server.py -e "XAI_API_KEY=YOUR_CORRECT_API_KEY"
```

Then restart Claude Code.

### MCP Server Not Showing Up

```bash
# Check if installed
claude mcp list

# If not listed, install it (see Step 3 above)
```

### Connection Errors

1. **Verify your API key** is valid at [console.x.ai](https://console.x.ai/)
2. **Check Python version**: `python --version` (needs 3.10+)
3. **Ensure xai-sdk is installed**: `pip install xai-sdk`

### View Current Configuration

Run this from the `claude-code-grok-mcp` folder:

```bash
python server.py config --show
```

---

## Contributing

Pull requests welcome! Please keep it simple and beginner-friendly.

## License

MIT - Use freely!

---

Made for the Claude Code community
