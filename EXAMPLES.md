# Grok MCP Usage Examples

## Trigger Phrases

Use these phrases to invoke Grok:

| Trigger | Tool | Example |
|---------|------|---------|
| `use grok`, `ask grok`, `grok:` | Ask | "use grok: what is quantum computing?" |
| `grok review`, `have grok review` | Code Review | "grok review this function for security" |
| `grok brainstorm`, `grok ideas` | Brainstorm | "grok brainstorm ideas for authentication" |
| `grok generate image`, `grok image` | Generate Image | "grok image of a cyberpunk cityscape" |
| `grok analyze image`, `grok vision` | Analyze Image | "grok analyze image at ./screenshot.png" |

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

## Image Generation

```
# Generate a single image
> grok generate image of a sunset over the Swiss Alps

# Generate with specific aspect ratio
> grok image of a futuristic dashboard, 16:9 aspect ratio

# Generate multiple variations
> grok generate 4 images of a logo concept for a tech startup

# Images are saved automatically to ./generated-images/
# and returned inline to Claude
```

## Image Analysis (Vision)

```
# Analyze a screenshot
> grok analyze image at /path/to/screenshot.png

# Ask a specific question about an image
> grok vision: what UI issues do you see in ./mockup.png?

# Describe a generated image
> grok describe image at ./generated-images/grok_20260210_143022.jpg
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

## Advanced: Image Workflow

```
# Generate an image with Grok
> grok generate image of a clean landing page hero section

# Then have Grok analyze it for feedback
> grok analyze image at ./generated-images/grok_20260210_143022.jpg
> What could be improved about this design?

# Iterate with a new prompt based on feedback
> grok generate image of a landing page hero with more contrast and bolder typography
```

## Real-World Workflow

1. **Claude writes initial code**
2. **Grok reviews for security/performance**
3. **Claude implements improvements**
4. **Both AIs brainstorm edge cases**
5. **Grok generates visual assets if needed**
6. **Final optimized solution!**

This creates a powerful AI pair programming experience where both models complement each other's strengths.

## Why Grok?

Grok models offer massive context windows (up to 2M tokens with `grok-4-1-fast-reasoning`), making them ideal for:

- Reviewing large codebases
- Understanding complex system architectures
- Processing extensive documentation
- Analyzing lengthy log files
- Generating images with Aurora
- Analyzing images and screenshots with vision

## Model Selection

List available models and change the default:

```bash
# See all available models
python server.py config --list-models

# Set your preferred model
python server.py config --model grok-4-0709

# Check current configuration
python server.py config --show
```

Restart Claude Code after changing the model.

### Available Models

| Model ID | Context | Description |
|----------|---------|-------------|
| `grok-4-1-fast-reasoning` | 2M | Grok 4.1 Fast with reasoning (Default) |
| `grok-4-1-fast-non-reasoning` | 2M | Grok 4.1 Fast without reasoning |
| `grok-4-fast-reasoning` | — | Grok 4 Fast with reasoning |
| `grok-4-fast-non-reasoning` | — | Grok 4 Fast without reasoning |
| `grok-4-0709` | — | Grok 4 (July 2025 release) |
| `grok-3` | 128K | Grok 3 - Previous flagship |
| `grok-3-mini` | 128K | Grok 3 Mini - Lighter/cheaper |
| `grok-2-1212` | 128K | Grok 2 |
| `grok-2-vision-1212` | 32K | Grok 2 Vision (used by `analyze_image`) |
| `grok-code-fast-1` | — | Grok Code Fast - Optimized for coding |
| `grok-imagine-image` | — | Aurora image generation (used by `generate_image`) |
