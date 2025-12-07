# Grok MCP Usage Examples

## Trigger Phrases

Use these phrases to invoke Grok:

| Trigger | Tool | Example |
|---------|------|---------|
| `use grok`, `ask grok`, `grok:` | Ask | "use grok: what is quantum computing?" |
| `grok review`, `have grok review` | Code Review | "grok review this function for security" |
| `grok brainstorm`, `grok ideas` | Brainstorm | "grok brainstorm ideas for authentication" |

## Basic Conversation

```
# Start Claude Code
claude

# Ask Grok a simple question using trigger phrases
> use grok: what is the capital of France?
> ask grok about quantum computing
> grok: explain machine learning
```

## Code Review Example

```
# Have Grok review your authentication code
> grok review this code for security:
def authenticate(username, password):
    if username == "admin" and password == "password123":
        return True
    return False

# Grok will point out security issues like:
# - Hardcoded credentials
# - Plain text password
# - No hashing
# - etc.
```

## Brainstorming Session

```
# Brainstorm startup ideas
> grok brainstorm AI-powered tools for developers
> grok ideas for B2B SaaS that solves developer pain points

# Grok provides creative suggestions
```

## Advanced: Collaborative Problem Solving

```
# Claude writes code
> Write a Python function to calculate fibonacci numbers

# Claude creates the function...

# Then get Grok's optimization suggestions
> grok review that code for performance

# Claude can then incorporate Grok's feedback!
```

## Real-World Workflow

1. **Claude writes initial code**
2. **Grok reviews for security/performance**
3. **Claude implements improvements**
4. **Both AIs brainstorm edge cases**
5. **Final optimized solution!**

This creates a powerful AI pair programming experience where both models complement each other's strengths.

## Why Grok?

Grok models offer massive context windows (up to 2M tokens with `grok-4-1-fast-reasoning`), making them ideal for:

- Reviewing large codebases
- Understanding complex system architectures
- Processing extensive documentation
- Analyzing lengthy log files

## Model Selection

List available models and change the default:

```bash
# See all available models
python server.py config --list-models

# Set your preferred model
python server.py config --model grok-4

# Check current configuration
python server.py config --show
```

Restart Claude Code after changing the model.

### Available Models

| Model | Context | Description |
|-------|---------|-------------|
| `grok-4` | 256K | Flagship model |
| `grok-4-1-fast-reasoning` | 2M | Fast reasoning (Default) |
| `grok-4-fast` | 2M | Fast with reasoning |
| `grok-3` | 128K | Previous flagship |
| `grok-3-mini` | 128K | Lighter/cheaper |
| `grok-2` | 128K | Grok 2 |
| `grok-2-vision` | 32K | Vision capable |
