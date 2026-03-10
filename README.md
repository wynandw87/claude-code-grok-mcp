# Claude Code + Grok MCP Server

MCP server that brings xAI's Grok to Claude Code — text generation, brainstorming, code review, web search, X/Twitter search, code execution, file analysis, image generation, image editing, video generation, vision analysis, and **multi-turn conversations**. Supports Grok 4.1, Aurora, Imagine, and Vision models.

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

> **Tip:** To get the full path, run this from the cloned directory:
> - macOS/Linux: `echo "$(pwd)/server.py"`
> - Windows: `echo %cd%\server.py`

**macOS / Linux:**
```text
claude mcp add -s user -t stdio Grok python3 /full/path/to/server.py -e XAI_API_KEY=YOUR_API_KEY
```

**Windows (CMD):**
```text
claude mcp add -s user -t stdio Grok python "C:\full\path\to\server.py" -e "XAI_API_KEY=YOUR_API_KEY"
```

**Windows (PowerShell):**
```text
claude mcp add -s user -t stdio Grok python "C:\full\path\to\server.py" -e "XAI_API_KEY=YOUR_API_KEY"
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
| `grok search`, `grok web search` | Web Search | "grok search for latest React 19 features" |
| `grok search x`, `grok twitter search` | X Search | "grok search x for posts about Claude Code" |
| `grok run code`, `grok calculate` | Run Code | "grok calculate the first 50 prime numbers" |
| `grok upload file` | Upload File | "grok upload file at ./report.pdf" |
| `grok generate image`, `grok image` | Generate Image | "grok generate image of a sunset over mountains" |
| `grok edit image`, `grok modify image` | Edit Image | "grok edit image at ./photo.jpg to look like an oil painting" |
| `grok generate video`, `grok video` | Generate Video | "grok generate a 5 second video of ocean waves" |
| `grok analyze image`, `grok vision` | Analyze Image | "grok analyze image at ./screenshot.png" |
| `grok chat`, `chat with grok` | Chat (multi-turn) | "grok chat: let's discuss our API design" |
| `grok sessions` | List Sessions | "grok sessions" |
| `end grok session` | End Session | "end grok session abc123" |

Or ask naturally:

- *"Ask Grok what it thinks about this approach"*
- *"Have Grok review this code for security issues"*
- *"Brainstorm with Grok about scaling strategies"*
- *"Grok search the web for the latest news on AI"*
- *"Grok search X for what people are saying about TypeScript 6"*
- *"Grok run code to calculate compound interest over 10 years"*
- *"Upload this CSV to Grok and ask it to summarize the data"*
- *"Grok generate an image of a futuristic city"*
- *"Grok edit this image to add a sunset background"*
- *"Grok generate a 10 second video of a drone flying over a forest"*
- *"Grok describe what's in this screenshot"*
- *"Start a conversation with Grok about database design"*

---

## Multi-Turn Conversations

Have an ongoing conversation with Grok where it remembers the full context. Uses the xAI Chat Completions API with server-side session management.

**Starting a conversation:**
```
grok chat: let's discuss the pros and cons of microservices
```

Grok responds and returns a `session_id`. Use it to continue:

```
grok chat (session abc123): what about event-driven architectures?
```

**Parameters:**
- `message` (required) — the message to send
- `session_id` (optional) — omit to start a new session, provide to continue an existing one
- `model` (optional) — override model (first message only)
- `system_prompt` (optional) — set a system prompt (first message only)

**Managing sessions:**
- Sessions expire automatically after 30 minutes of inactivity
- Use `grok sessions` to list active sessions
- Use `end grok session <id>` to clean up a session

---

## Web Search

Search the web with real-time results and citations. Grok autonomously searches, browses pages, and synthesizes answers.

**Parameters:**
- `query` (required) — the search query or question
- `allowed_domains` (optional) — only search within these domains (max 5)
- `excluded_domains` (optional) — exclude these domains from search (max 5)

Results include inline citations with source URLs.

## X / Twitter Search

Search X (Twitter) posts. Find tweets, threads, and discussions from specific users or timeframes.

**Parameters:**
- `query` (required) — the search query
- `allowed_x_handles` (optional) — only search posts from these handles (max 10, without @ prefix)
- `excluded_x_handles` (optional) — exclude posts from these handles (max 10)
- `from_date` (optional) — start date (YYYY-MM-DD)
- `to_date` (optional) — end date (YYYY-MM-DD)

## Code Execution

Execute Python code in Grok's sandboxed environment. Pre-installed libraries include NumPy, Pandas, Matplotlib, and SciPy.

**Parameters:**
- `prompt` (required) — description of what to compute or analyze

Grok writes and executes Python code automatically. Useful for calculations, data analysis, and generating visualizations.

## File Upload & Analysis

Upload documents for Grok to analyze. Optionally ask a question about the file immediately.

**Parameters:**
- `file_path` (required) — absolute path to the file
- `query` (optional) — question to ask about the file after upload

**Supported file types:** txt, md, py, js, ts, java, c, cpp, go, rs, rb, php, css, html, xml, yaml, json, csv, pdf, sql, and more. Max 48MB per file.

Returns a file ID that can be reused with the `ask` tool's `file_ids` parameter for follow-up questions.

## Image Generation

Generate images using Grok's image models.

**Parameters:**
- `prompt` (required) — description of the image to create
- `model` (optional) — `"grok-imagine-image"` (default, $0.02/img), `"grok-2-image-1212"` ($0.07/img), or `"grok-imagine-image-pro"` ($0.07/img, higher quality)
- `n` (optional, 1-10) — number of images to generate
- `aspect_ratio` (optional) — `"1:1"`, `"16:9"`, `"9:16"`, `"4:3"`, `"3:4"`, `"3:2"`, `"2:3"`, `"2:1"`, `"1:2"`, `"19.5:9"`, `"9:19.5"`, `"20:9"`, `"9:20"`, `"auto"`
- `resolution` (optional) — `"1k"` (~1024px) or `"2k"` (~2048px)
- `save_path` (optional) — where to save the file; auto-saves with timestamp if omitted

Images are saved to disk. The default save directory is `./generated-images/`, configurable via the `GROK_OUTPUT_DIR` environment variable.

## Image Editing

Edit existing images using natural language with Grok's Imagine models. Supports style transfer, iterative refinement, and content modification.

**Parameters:**
- `prompt` (required) — description of the desired edits (e.g., "make it look like an oil painting", "add a sunset background")
- `image_path` (required) — absolute path to the source image
- `model` (optional) — `"grok-imagine-image"` (default, $0.02/img) or `"grok-imagine-image-pro"` ($0.07/img)
- `save_path` (optional) — where to save the edited image; auto-saves if omitted

## Video Generation

Generate videos using Grok's Imagine video model. Supports three modes: text-to-video, image-to-video, and video editing. Video generation is async and may take 1-5 minutes.

**Parameters:**
- `prompt` (required) — description of the video to generate or editing instructions
- `duration` (optional, 1-15) — video duration in seconds (default: 5). Not applicable for video editing.
- `aspect_ratio` (optional) — `"1:1"`, `"16:9"` (default), `"9:16"`, `"4:3"`, `"3:4"`, `"3:2"`, `"2:3"`
- `resolution` (optional) — `"480p"` (default) or `"720p"`
- `image_path` (optional) — source image for image-to-video mode
- `video_url` (optional) — source video URL for video editing mode (max 8.7s input)
- `save_path` (optional) — where to save the video; auto-saves if omitted

Videos are saved to disk. The default save directory is `./generated-videos/`, configurable via the `GROK_VIDEO_OUTPUT_DIR` environment variable. Pricing is $0.05 per second of generated video.

## Image Analysis (Vision)

Analyze images using Grok's vision capabilities. Uses your configured default model (grok-4+ models support vision natively).

**Parameters:**
- `image_path` (required) — absolute path to the image file
- `prompt` (optional) — question about the image (default: "Describe this image in detail")
- `model` (optional) — vision model override: `"grok-2-vision-1212"`, `"grok-4-1-fast-reasoning"`, `"grok-4"`, etc.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `XAI_API_KEY` | Your xAI API key (required) | — |
| `GROK_OUTPUT_DIR` | Directory for auto-saved generated images | `./generated-images` |
| `GROK_VIDEO_OUTPUT_DIR` | Directory for auto-saved generated videos | `./generated-videos` |
| `GROK_TIMEOUT` | Default timeout in seconds for API calls | `180` |

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
  grok-4
    Grok 4 flagship model
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
  grok-2-image-1212
    Aurora image generation (text→image, $0.07/img)
  grok-imagine-image
    Imagine image gen + editing (text,image→image, $0.02/img)
  grok-imagine-image-pro
    Imagine Pro image gen + editing (higher quality, $0.07/img)
  grok-imagine-video
    Imagine video generation (text,image,video→video, $0.05/sec)

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

This MCP server uses the xAI REST API directly to communicate with Grok models. No SDK required — just the `requests` library for HTTP calls. Text-based tools use the Responses API (`/v1/responses`) with server-side tool support, multi-turn conversations use the Chat Completions API (`/v1/chat/completions`) with server-side session management, and image/vision tools use their dedicated endpoints.

**Tools provided:**
| Tool | API | Model |
|------|-----|-------|
| `ask` | Responses | Configurable (default: `grok-4-1-fast-reasoning`) |
| `code_review` | Responses | Configurable (default: `grok-4-1-fast-reasoning`) |
| `brainstorm` | Responses | Configurable (default: `grok-4-1-fast-reasoning`) |
| `search_web` | Responses + web_search | Configurable (default: `grok-4-1-fast-reasoning`) |
| `search_x` | Responses + x_search | Configurable (default: `grok-4-1-fast-reasoning`) |
| `run_code` | Responses + code_interpreter | Configurable (default: `grok-4-1-fast-reasoning`) |
| `upload_file` | Files + Responses | Configurable (default: `grok-4-1-fast-reasoning`) |
| `generate_image` | Image Generations | Configurable (default: `grok-imagine-image`) |
| `edit_image` | Image Edits | Configurable (default: `grok-imagine-image`) |
| `generate_video` | Video Generations | `grok-imagine-video` |
| `analyze_image` | Chat Completions | Configurable (default: your configured model) |
| `chat` | Chat Completions | Configurable (default: `grok-4-1-fast-reasoning`) |
| `list_sessions` | — (local) | — |
| `end_session` | — (local) | — |

---

## Contributing

Pull requests welcome! Please keep it simple and beginner-friendly.

## License

MIT - Use freely!

---

Made for the Claude Code community
