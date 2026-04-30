# Grok MCP Usage Examples

## Trigger Phrases

Use these phrases to invoke Grok:

| Trigger | Tool | Example |
|---------|------|---------|
| `use grok`, `ask grok`, `grok:` | Ask | "use grok: what is quantum computing?" |
| `grok review`, `have grok review` | Code Review | "grok review this function for security" |
| `grok brainstorm`, `grok ideas` | Brainstorm | "grok brainstorm ideas for authentication" |
| `grok search`, `grok web search` | Web Search | "grok search for latest React 19 features" |
| `grok search x`, `grok twitter search` | X Search | "grok search x for posts about Claude Code" |
| `grok run code`, `grok calculate` | Run Code | "grok calculate the first 50 prime numbers" |
| `grok upload file` | Upload File | "grok upload file at ./report.pdf" |
| `grok generate image`, `grok image` | Generate Image | "grok image of a cyberpunk cityscape" |
| `grok analyze image`, `grok vision` | Analyze Image | "grok analyze image at ./screenshot.png" |
| `grok speak`, `grok tts`, `grok say` | Text-to-Speech | "grok speak: welcome to the demo" |
| `grok transcribe`, `grok stt` | Speech-to-Text | "grok transcribe ./meeting.mp3" |

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

## Web Search

```
# Search for current information
> grok search for the latest developments in quantum computing

# Search within specific domains
> grok web search for Python 3.13 features on docs.python.org

# Research a topic with real-time data
> grok search what happened in tech news today

# Results include source citations with URLs
```

## X / Twitter Search

```
# Search for posts about a topic
> grok search x for discussions about Claude Code

# Search specific users' posts
> grok search x for posts from @elikitten about AI safety

# Search within a date range
> grok search x for posts about GPT-5 from 2026-01-01 to 2026-02-01

# Combine filters
> grok search x for AI announcements from @OpenAI and @AnthropicAI
```

## Code Execution

```
# Run calculations
> grok calculate the standard deviation of [23, 45, 67, 89, 12, 34]

# Data analysis
> grok run code to analyze this CSV data and find trends

# Mathematical proofs
> grok execute: verify that the sum of first n odd numbers equals n²

# Generate visualizations
> grok run code to create a bar chart comparing Python vs JavaScript popularity
```

## File Upload & Analysis

```
# Upload and immediately ask about a file
> grok upload file at ./quarterly-report.pdf and summarize the key findings

# Upload a file for later questions
> grok upload file at ./codebase-architecture.md
# Returns a file ID, then use it:
> ask grok about the authentication flow (with the uploaded file)

# Analyze code files
> grok upload file at ./server.py and review it for security issues

# Process data files
> grok upload file at ./sales-data.csv and identify the top-performing regions
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

## Advanced: Research Workflow

```
# Step 1: Search the web for current information
> grok search for the latest best practices in microservices architecture 2026

# Step 2: Search X for community opinions
> grok search x for discussions about microservices vs monolith

# Step 3: Upload your existing architecture doc
> grok upload file at ./architecture.md and suggest improvements based on current best practices

# Step 4: Have Grok run calculations
> grok run code to estimate the cost savings of migrating to microservices
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
2. **Grok searches the web** for current best practices
3. **Grok reviews** the code for security/performance
4. **Claude implements improvements**
5. **Grok runs code** to verify calculations or benchmark
6. **Both AIs brainstorm edge cases**
7. **Grok searches X** for community feedback on the approach
8. **Grok generates visual assets** if needed
9. **Final optimized solution!**

This creates a powerful AI pair programming experience where both models complement each other's strengths.

## Why Grok?

Grok models offer massive context windows (up to 2M tokens with `grok-4-1-fast-reasoning`), making them ideal for:

- Reviewing large codebases
- Understanding complex system architectures
- Processing extensive documentation
- Analyzing lengthy log files
- **Searching the web** for real-time information with citations
- **Searching X/Twitter** for community discussions and trends
- **Executing Python code** for calculations and data analysis
- **Analyzing uploaded files** (PDFs, code, CSVs, etc.)
- Generating images with Aurora
- Analyzing images and screenshots with vision

## Text-to-Speech

```
# Use the configured default voice (eve)
> grok speak: Welcome to the morning standup. Let's get started.

# Override the voice for a single call
> grok speak with voice rex: System nominal. All checks passed.

# Save to a specific path
> grok tts "this is a test" and save it to ./demo.mp3
```

The MP3 is saved to `./generated-audio/` by default (override with `GROK_AUDIO_OUTPUT_DIR`). To change the default voice permanently:

```bash
python server.py config --list-voices
python server.py config --voice rex
```

## Speech-to-Text

```
# Basic transcription
> grok transcribe ./meeting.mp3

# Force a language
> grok transcribe ./call.wav (language=es)

# Word-level timestamps and speaker diarization
> grok stt ./interview.flac with response_format=verbose_json

# Generate subtitles
> grok transcribe ./talk.mp4 with response_format=srt
```

Supports mp3, wav, flac, m4a, ogg, opus, aac, webm, mp4, mpga, mpeg, wma (max 100MB).

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
| `grok-4` | 256K | Grok 4 flagship model |
| `grok-4-1-fast-non-reasoning` | 2M | Grok 4.1 Fast without reasoning |
| `grok-4-fast-reasoning` | — | Grok 4 Fast with reasoning |
| `grok-4-fast-non-reasoning` | — | Grok 4 Fast without reasoning |
| `grok-4-0709` | — | Grok 4 (July 2025 release) |
| `grok-3` | 128K | Grok 3 - Previous flagship |
| `grok-3-mini` | 128K | Grok 3 Mini - Lighter/cheaper |
| `grok-2-1212` | 128K | Grok 2 |
| `grok-2-vision-1212` | 32K | Grok 2 Vision (used by `analyze_image`) |
| `grok-code-fast-1` | — | Grok Code Fast - Optimized for coding |
| `grok-2-image` | — | Aurora image generation (used by `generate_image`) |
