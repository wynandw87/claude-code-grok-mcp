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

### Step 3: Install the MCP Server

#### 3.1 Clone the repository

```text
git clone https://github.com/wynandw87/claude-code-grok-mcp.git
cd claude-code-grok-mcp
```

#### 3.2 Install dependencies

**macOS / Linux:**
```text
pip3 install -r requirements.txt
```

**Windows:**
```text
pip install -r requirements.txt
```

#### 3.3 Register with Claude Code

Choose your install scope:

| Scope | Flag | Who can use it |
|-------|------|----------------|
| **User** (recommended) | `-s user` | You, in any project |
| **Project** | `-s project` | Anyone who clones this repo |
| **Local** | `-s local` | Only in current directory |

Replace `YOUR_API_KEY` with your actual xAI API key, and use the full path to `server.py`.

**macOS / Linux:**
```text
claude mcp add -s user -t stdio Grok python3 /full/path/to/server.py -e XAI_API_KEY=YOUR_API_KEY
```

**Windows:**
```text
claude mcp add -s user -t stdio Grok python C:\full\path\to\server.py -e XAI_API_KEY=YOUR_API_KEY
```

> **Note:** Windows uses `python` while macOS/Linux use `python3`. Use the full absolute path to where you cloned the repository.

#### Alternative: Use Setup Scripts

The setup scripts handle dependency installation and registration automatically.

**macOS / Linux:**
```text
chmod +x setup.sh
./setup.sh YOUR_API_KEY
```

**Windows (PowerShell):**
```text
.\setup.ps1 -ApiKey YOUR_API_KEY
```

### Step 4: Restart Claude Code

Close and reopen Claude Code for the changes to take effect.

### Step 5: Verify Installation

```text
claude mcp list
```

You should see `Grok` listed with a ✓ Connected status.

---

## Usage

Once installed, use trigger phrases to invoke Grok:

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

The default model is `grok-4-1-fast-reasoning` (Grok 4.1 Fast with reasoning, 2M context window).

### 1. See available models

Run from the `claude-code-grok-mcp` folder:

**macOS / Linux:**
```text
python3 server.py config --list-models
```

**Windows:**
```text
python server.py config --list-models
```

**Output:**
```
Available Grok models:
--------------------------------------------------
  grok-4-1-fast-reasoning *
    Grok 4.1 Fast with reasoning (2M context) - Default
  grok-4-1-fast-non-reasoning
    Grok 4.1 Fast without reasoning (2M context)
  grok-4-fast-reasoning
    Grok 4 Fast with reasoning
  grok-4-fast-non-reasoning
    Grok 4 Fast without reasoning
  grok-4-0709
    Grok 4 (July 2025 release)
  grok-3
    Grok 3 - Previous flagship (128K context)
  grok-3-mini
    Grok 3 Mini - Lighter/cheaper option (128K context)
  grok-2-1212
    Grok 2 (128K context)
  grok-2-vision-1212
    Grok 2 Vision (32K context)
  grok-code-fast-1
    Grok Code Fast - Optimized for coding

* = currently selected
```

### 2. Set your preferred model

**macOS / Linux:**
```text
python3 server.py config --model grok-4-0709
```

**Windows:**
```text
python server.py config --model grok-4-0709
```

### 3. Restart Claude Code

Close and reopen Claude Code for the change to take effect.

---

## Troubleshooting

### Fix API Key

If you entered the wrong API key, remove and reinstall:

```text
claude mcp remove Grok
```

Then reinstall using the command from Step 3.3 above (use the same scope you originally installed with).

### MCP Server Not Showing Up

Check if the server is installed:

```text
claude mcp list
```

If not listed, follow Step 3 to install it.

### Connection Errors

1. **Verify your API key** is valid at [console.x.ai](https://console.x.ai/)

2. **Check Python version** (needs 3.10+):
   - macOS/Linux: `python3 --version`
   - Windows: `python --version`

3. **Ensure requests is installed**:
   - macOS/Linux: `pip3 install requests`
   - Windows: `pip install requests`

### View Current Configuration

Run from the `claude-code-grok-mcp` folder:

**macOS / Linux:**
```text
python3 server.py config --show
```

**Windows:**
```text
python server.py config --show
```

---

## How It Works

This MCP server uses the xAI REST API directly (OpenAI-compatible format) to communicate with Grok models. No SDK required - just the `requests` library for HTTP calls.

---

## Contributing

Pull requests welcome! Please keep it simple and beginner-friendly.

## License

MIT - Use freely!

---

Made for the Claude Code community
