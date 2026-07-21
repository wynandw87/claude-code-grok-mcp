# Claude Code + Grok MCP Server

MCP server that brings xAI's Grok to Claude Code — text generation, brainstorming, code review, web search, X/Twitter search, code execution, file analysis, image generation, image editing, video generation, video editing, vision analysis, **text-to-speech**, **speech-to-text**, and **multi-turn conversations**. Supports Grok 4.5 (default), Grok 4.3, Grok 4.20, Grok Build, Imagine (image/video), and Voice models.

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
| `grok generate video`, `grok video` | Generate Video | "grok generate an 8 second video of ocean waves" |
| `grok edit video`, `grok modify video` | Edit Video | "grok edit ./clip.mp4 to change the sky to sunset" |
| `grok analyze image`, `grok vision` | Analyze Image | "grok analyze image at ./screenshot.png" |
| `grok speak`, `grok tts`, `grok say` | Text-to-Speech | "grok speak: welcome to the demo" |
| `grok transcribe`, `grok stt` | Speech-to-Text | "grok transcribe ./meeting.mp3" |
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
- *"Grok edit this video to swap the red car for a blue one"*
- *"Grok describe what's in this screenshot"*
- *"Have Grok read this paragraph aloud and save it as an MP3"*
- *"Grok transcribe this meeting recording with speaker labels"*
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
- `model` (optional) — `"grok-imagine-image"` (default, $0.02/img) or `"grok-imagine-image-quality"` ($0.05/img, higher quality)
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
- `model` (optional) — `"grok-imagine-image"` (default, $0.02/img) or `"grok-imagine-image-quality"` ($0.05/img)
- `save_path` (optional) — where to save the edited image; auto-saves if omitted

## Video Generation

Generate videos using Grok's Imagine video model (`/v1/videos/generations`). Supports text-to-video and image-to-video. Video generation is async and may take 1-5 minutes.

**Parameters:**
- `prompt` (required) — description of the video to generate
- `duration` (optional, 1-15) — video duration in seconds (default: 8)
- `aspect_ratio` (optional) — `"1:1"`, `"16:9"` (default), `"9:16"`, `"4:3"`, `"3:4"`, `"3:2"`, `"2:3"`
- `resolution` (optional) — `"480p"` (default), `"720p"`, or `"1080p"`
- `image_path` (optional) — source image for image-to-video mode
- `save_path` (optional) — where to save the video; auto-saves if omitted

For editing an existing video, use the separate `edit_video` tool.

Videos are saved to disk. The default save directory is `./generated-videos/`, configurable via the `GROK_VIDEO_OUTPUT_DIR` environment variable. Pricing is $0.05 per second of generated video.

## Video Editing

Apply natural-language edits to an existing MP4 (H.264 / H.265 / AV1) using `/v1/videos/edits`.

**Parameters** (provide exactly one of `video_path`, `video_url`, or `file_id`):
- `prompt` (required) — natural-language edit instructions (e.g. *"give the woman a silver necklace"*, *"change the background to a snowy mountain"*)
- `video_path` — absolute path to a local MP4 (uploaded inline as base64)
- `video_url` — public URL of the source MP4
- `file_id` — xAI `file_id` of a previously uploaded video
- `save_path` (optional) — where to save the edited video; auto-saves if omitted

## Image Analysis (Vision)

Analyze images using Grok's vision capabilities. Uses your configured default model (Grok 4.5, 4.3 and the 4.20 variants all support vision natively).

**Parameters:**
- `image_path` (required) — absolute path to the image file
- `prompt` (optional) — question about the image (default: "Describe this image in detail")
- `model` (optional) — vision model override: `"grok-4.5"`, `"grok-4.3"`, `"grok-4.20-0309-reasoning"`, etc.

## Text-to-Speech

Convert text to natural-sounding speech using Grok's TTS API. Supports inline speech tags for emotion (laughter, whispers, pauses) and 20+ languages. Pricing: $15.00 per 1M characters.

**Parameters:**
- `text` (required) — the text to synthesize
- `voice` (optional) — built-in voice ID (default: `eve`; see list below) or a custom cloned voice ID (8 lowercase alphanumeric chars)
- `language` (optional) — language code (default: `"en"`)
- `audio_format` (optional) — `mp3` (default), `wav`, `pcm`, `mulaw`, `alaw`
- `sample_rate` (optional) — 8000, 16000, 22050, 24000 (default), 44100, or 48000 Hz
- `bitrate` (optional, MP3 only) — 32, 64, 96, 128 (default), or 192 kbps
- `save_path` (optional) — where to save the audio; auto-saves to `./generated-audio/` with a timestamp if omitted

**Built-in voices:**

| Voice | Description |
|-------|-------------|
| `ara` | Warm female |
| `eve` | Energetic female (default) |
| `leo` | Authoritative male |
| `rex` | Confident male |
| `sal` | Neutral |

To switch the default voice permanently, see [Changing the Default Voice](#changing-the-default-voice). To override for a single call, pass `voice` (e.g. *"grok speak with voice rex: ..."*).

**Custom cloned voices:** xAI supports voice cloning from a short reference clip. Create one via the [xAI Console](https://console.x.ai/) (free tier: up to 30 voices) or the `POST /v1/custom-voices` API (Enterprise plan). Custom voice IDs are 8-char lowercase alphanumeric (e.g. `nlbqfwie`) and can be passed to `text_to_speech` directly in place of a built-in voice. Currently US-only (excluding Illinois).

## Speech-to-Text

Transcribe audio files using Grok's STT API (`/v1/stt`). Supports 24 languages, per-channel transcription, speaker diarization, and keyterm boosting. Pricing: $0.10/hr (REST), $0.20/hr (streaming).

**Parameters** (provide exactly one of `audio_path` or `audio_url`):
- `audio_path` — absolute path to a local audio file
- `audio_url` — public URL of the audio
- `language` (optional) — ISO language code (e.g. `"en"`, `"es"`); auto-detected if omitted
- `format` (optional, bool) — apply text formatting (punctuation, casing)
- `diarize` (optional, bool) — speaker diarization (per-speaker labels)
- `multichannel` (optional, bool) — per-channel transcription
- `channels` (optional, int) — channel count for raw/headerless audio
- `keyterm` (optional, array of strings, max 100) — boost recognition for jargon / proper nouns
- `filler_words` (optional, bool) — include "um", "uh", etc. in the transcript

**Supported audio formats:** mp3, wav, flac, m4a, ogg, opus, aac, webm, mp4, mpga, mpeg, wma. Max 500MB per file.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `XAI_API_KEY` | Your xAI API key (required) | — |
| `GROK_OUTPUT_DIR` | Directory for auto-saved generated images | `./generated-images` |
| `GROK_VIDEO_OUTPUT_DIR` | Directory for auto-saved generated videos | `./generated-videos` |
| `GROK_AUDIO_OUTPUT_DIR` | Directory for auto-saved TTS audio output | `./generated-audio` |
| `GROK_TIMEOUT` | Default timeout in seconds for API calls | `180` |

---

## Reliability Behavior

**File safety.** Tools that write output (`generate_image`, `edit_image`, `generate_video`, `edit_video`, `text_to_speech`) never overwrite an existing file. Pass `overwrite: true` to replace one. Writes are atomic — an interrupted write leaves the original file untouched rather than a truncated one.

**Input validation.** Files you pass in (`image_path`, `video_path`, `audio_path`, `file_path`) are checked for extension and size before being read and sent to xAI. Images are capped at 20MB (`.jpg/.jpeg/.png/.gif/.webp/.bmp`), source videos at 100MB (`.mp4`), audio at 500MB, uploads at 48MB.

**Retries.** HTTP 429 and 503 are retried up to 3 times with exponential backoff, honoring `Retry-After`. Ambiguous 5xx responses are retried only on read-only requests (status polls, downloads) — never on generation calls, where a duplicate request could bill you twice.

**Cancellation.** Video generation and editing poll for up to 10 minutes. Cancelling the request in Claude Code stops the poll within about a second, and the server sends no response for a cancelled request. The job itself continues on xAI's side and is still billed — the `request_id` is logged to stderr so you can retrieve it. On Windows, cancellation is not detected mid-poll and the call runs to completion or timeout.

**Recoverability.** Every video error message includes the `request_id`, so a job that outlives the poll timeout can still be fetched manually from the xAI API.

---

## Changing the Default Model

The default model is `grok-4.5` (xAI's flagship, 500k context window).

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
  grok-4.5 *
    Grok 4.5 flagship (500k context, $2/$6 per 1M tokens) - Default
  grok-4.3
    Grok 4.3 (1M context, $1.25/$2.50 per 1M tokens)
  grok-4.20-0309-reasoning
    Grok 4.20 with reasoning (1M context, $1.25/$2.50)
  grok-4.20-0309-non-reasoning
    Grok 4.20 without reasoning (1M context, $1.25/$2.50)
  grok-4.20-multi-agent-0309
    Grok 4.20 multi-agent (2M context, $1.25/$2.50)
  grok-build-0.1
    Grok Build 0.1 coding model (256k context, $1/$2)
  grok-imagine-image
    Imagine image gen + editing (text,image→image, $0.02/img)
  grok-imagine-image-quality
    Imagine higher-quality image gen + editing ($0.05/img)
  grok-imagine-video
    Imagine video generation (text,image,video→video, $0.05/sec)
  grok-imagine-video-1.5
    Imagine video 1.5 (image→video ONLY - no text-to-video, no editing; $0.08/sec)

* = currently selected
```

### 2. Set your preferred model

**macOS / Linux:**
```text
python3 server.py config --model grok-4.20-0309-reasoning
```

**Windows:**
```text
python server.py config --model grok-4.20-0309-reasoning
```

### 3. Restart Claude Code

Close and reopen Claude Code for the change to take effect.

---

## Changing the Default Voice

The default text-to-speech voice is `eve` (energetic female). You can switch it permanently with the same config CLI used for models. You can also override the default per-call by passing `voice` to the `text_to_speech` tool — e.g. *"grok speak with voice rex: ..."*.

### 1. See available voices

Run from the `claude-code-grok-mcp` folder:

**macOS / Linux:**
```text
python3 server.py config --list-voices
```

**Windows:**
```text
python server.py config --list-voices
```

**Output:**
```
Available TTS voices:
--------------------------------------------------
  ara
    Warm female voice
  eve *
    Energetic female voice (default)
  leo
    Authoritative male voice
  rex
    Confident male voice
  sal
    Neutral voice

* = currently selected
```

### 2. Set your preferred voice

**macOS / Linux:**
```text
python3 server.py config --voice rex
```

**Windows:**
```text
python server.py config --voice rex
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
| `ask` | Responses | Configurable (default: `grok-4.5`) |
| `code_review` | Responses | Configurable (default: `grok-4.5`) |
| `brainstorm` | Responses | Configurable (default: `grok-4.5`) |
| `search_web` | Responses + web_search | Configurable (default: `grok-4.5`) |
| `search_x` | Responses + x_search | Configurable (default: `grok-4.5`) |
| `run_code` | Responses + code_interpreter | Configurable (default: `grok-4.5`) |
| `upload_file` | Files + Responses | Configurable (default: `grok-4.5`) |
| `generate_image` | Image Generations | Configurable (default: `grok-imagine-image`) |
| `edit_image` | Image Edits | Configurable (default: `grok-imagine-image`) |
| `generate_video` | Video Generations (`/v1/videos/generations`) | Configurable (default: `grok-imagine-video`) |
| `edit_video` | Video Edits (`/v1/videos/edits`) | Configurable (default: `grok-imagine-video`) |
| `analyze_image` | Chat Completions | Configurable (default: your configured model) |
| `text_to_speech` | TTS (`/v1/tts`) | Grok Voice (configurable voice, default: `eve`) |
| `speech_to_text` | STT (`/v1/stt`) | Grok Voice |
| `chat` | Chat Completions | Configurable (default: `grok-4.5`) |
| `list_sessions` | — (local) | — |
| `end_session` | — (local) | — |
| `server_info` | — (local) | — |

---

## Contributing

Pull requests welcome! Please keep it simple and beginner-friendly.

## Tests

```bash
python3 test_server.py
```

Covers input validation, overwrite protection, atomic writes, model-config fallback, retry/backoff, session windowing and eviction, and cancellation handling. No network access or API key required — all HTTP is stubbed.

---

## License

MIT - Use freely!

---

Made for the Claude Code community
