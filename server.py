#!/usr/bin/env python3
"""
Claude Code + Grok MCP Server
Enables Claude Code to collaborate with xAI's Grok AI

Usage:
  As MCP server (default):  python server.py
  Configure model:          python server.py config --model grok-4.5
  Configure voice:          python server.py config --voice eve
  Show current config:      python server.py config --show
  List available models:    python server.py config --list-models
  List available voices:    python server.py config --list-voices
"""

import argparse
import base64
import json
import sys
import os
import signal
import logging
import time
import uuid
import requests
import select
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Server version
__version__ = "3.9.2"

# xAI API endpoints
XAI_CHAT_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_RESPONSES_API_URL = "https://api.x.ai/v1/responses"
XAI_IMAGE_API_URL = "https://api.x.ai/v1/images/generations"
XAI_IMAGE_EDIT_API_URL = "https://api.x.ai/v1/images/edits"
XAI_VIDEO_API_URL = "https://api.x.ai/v1/videos/generations"
XAI_VIDEO_EDIT_API_URL = "https://api.x.ai/v1/videos/edits"
XAI_FILES_API_URL = "https://api.x.ai/v1/files"
XAI_TTS_API_URL = "https://api.x.ai/v1/tts"
XAI_STT_API_URL = "https://api.x.ai/v1/stt"

# Timeouts (seconds)
TIMEOUT_DEFAULT = int(os.environ.get("GROK_TIMEOUT", "180"))
TIMEOUT_TOOLS = 300   # web_search, x_search, code_interpreter
TIMEOUT_UPLOAD = 120
TIMEOUT_IMAGE = 120
TIMEOUT_VIDEO = 300       # video generation submission
TIMEOUT_AUDIO = 180       # TTS / STT
VIDEO_POLL_INTERVAL = 5   # seconds between status checks
VIDEO_POLL_TIMEOUT = 600  # max 10 minutes waiting for video

# Default output directories for generated media
OUTPUT_DIR = os.environ.get("GROK_OUTPUT_DIR", "./generated-images")
VIDEO_OUTPUT_DIR = os.environ.get("GROK_VIDEO_OUTPUT_DIR", "./generated-videos")
AUDIO_OUTPUT_DIR = os.environ.get("GROK_AUDIO_OUTPUT_DIR", "./generated-audio")

# Audio input limits (for speech-to-text)
MAX_AUDIO_SIZE_MB = 500
SUPPORTED_AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".m4a", ".ogg", ".opus",
    ".aac", ".webm", ".mp4", ".mpga", ".mpeg", ".wma",
}

# Available built-in TTS voices (xAI Voice API)
# Custom cloned voices (8-char lowercase alphanumeric IDs) are also accepted.
AVAILABLE_VOICES = {
    "ara": "Warm female voice",
    "eve": "Energetic female voice (default)",
    "leo": "Authoritative male voice",
    "rex": "Confident male voice",
    "sal": "Neutral voice",
}
DEFAULT_VOICE_FALLBACK = "eve"

# Custom voice IDs from xAI's voice cloning are 8-char lowercase alphanumeric.
import re as _re
_CUSTOM_VOICE_ID_RE = _re.compile(r"^[a-z0-9]{8}$")

def is_valid_voice_id(voice: str) -> bool:
    """Accept built-in voices or custom cloned voice IDs."""
    if not voice:
        return False
    if voice in AVAILABLE_VOICES:
        return True
    return bool(_CUSTOM_VOICE_ID_RE.match(voice))

# Supported TTS audio output formats and sample rates (xAI TTS API)
TTS_AUDIO_FORMATS = ["mp3", "wav", "pcm", "mulaw", "alaw"]
TTS_SAMPLE_RATES = [8000, 16000, 22050, 24000, 44100, 48000]
TTS_MP3_BITRATES = [32, 64, 96, 128, 192]
TTS_FORMAT_EXTENSIONS = {
    "mp3": "mp3", "wav": "wav", "pcm": "pcm", "mulaw": "ulaw", "alaw": "alaw",
}

# File upload limits
MAX_FILE_SIZE_MB = 48
SUPPORTED_FILE_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp",
    ".h", ".go", ".rs", ".rb", ".php", ".css", ".html", ".xml", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".sh", ".bat", ".ps1", ".csv", ".json", ".jsonl",
    ".pdf", ".log", ".sql", ".r", ".swift", ".kt", ".scala", ".lua",
}

# Image input limits (vision, image editing, image-to-video)
MAX_IMAGE_SIZE_MB = 20
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# Video input limits (video editing)
MAX_VIDEO_SIZE_MB = 100
SUPPORTED_VIDEO_EXTENSIONS = {".mp4"}

# TTS input limit (xAI bills per character; keep requests sane)
MAX_TTS_TEXT_LENGTH = 10000

# Session limits
MAX_SESSIONS = 50            # LRU-evict beyond this many live sessions
MAX_SESSION_MESSAGES = 40    # sliding window of messages sent per turn

# Available Grok models (from xAI API, current as of 2026-07-21)
AVAILABLE_MODELS = {
    "grok-4.5": "Grok 4.5 flagship (500k context, $2/$6 per 1M tokens) - Default",
    "grok-4.3": "Grok 4.3 (1M context, $1.25/$2.50 per 1M tokens)",
    "grok-4.20-0309-reasoning": "Grok 4.20 with reasoning (1M context, $1.25/$2.50)",
    "grok-4.20-0309-non-reasoning": "Grok 4.20 without reasoning (1M context, $1.25/$2.50)",
    "grok-4.20-multi-agent-0309": "Grok 4.20 multi-agent (2M context, $1.25/$2.50)",
    "grok-build-0.1": "Grok Build 0.1 coding model (256k context, $1/$2)",
    # Image generation models
    "grok-imagine-image": "Imagine image gen + editing (text,image→image, $0.02/img)",
    "grok-imagine-image-quality": "Imagine higher-quality image gen + editing ($0.05/img)",
    # Video generation models
    "grok-imagine-video": "Imagine video generation (text,image,video→video, $0.05/sec)",
    "grok-imagine-video-1.5": "Imagine video 1.5 (image→video ONLY - no text-to-video, no editing; $0.08/sec)",
}

# Models that can be used for chat/vision (excludes image + video models)
TEXT_MODELS = [
    "grok-4.5",
    "grok-4.3",
    "grok-4.20-0309-reasoning",
    "grok-4.20-0309-non-reasoning",
    "grok-4.20-multi-agent-0309",
    "grok-build-0.1",
]

# Video generation models
VIDEO_MODELS = ["grok-imagine-video", "grok-imagine-video-1.5"]
DEFAULT_VIDEO_MODEL = "grok-imagine-video"
# grok-imagine-video-1.5 accepts image-to-video only: the API rejects both
# text-to-video and video editing for it (verified against /v1/videos/*).
IMAGE_TO_VIDEO_ONLY_MODELS = {"grok-imagine-video-1.5"}
# Models usable with /v1/videos/edits
VIDEO_EDIT_MODELS = [m for m in VIDEO_MODELS if m not in IMAGE_TO_VIDEO_ONLY_MODELS]

# Config file location
def get_config_path() -> Path:
    """Get the config file path (cross-platform)"""
    if sys.platform == "win32":
        base = Path(os.environ.get("USERPROFILE", "~"))
    else:
        base = Path(os.environ.get("HOME", "~"))
    return base.expanduser() / ".claude-mcp-servers" / "grok" / "config.json"

def load_config() -> Dict[str, Any]:
    """Load configuration from file"""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}

def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to file"""
    config_path = get_config_path()
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except IOError as e:
        print(f"Error saving config: {e}", file=sys.stderr)
        return False

DEFAULT_MODEL_FALLBACK = "grok-4.5"

def get_default_model() -> str:
    """Get the default model from config file or use fallback.

    A config file holding a retired or non-text model would otherwise poison
    every chat/vision call with an opaque API error, so validate it here the
    same way get_default_voice() validates voices.
    """
    config = load_config()
    configured = config.get("model")
    if configured in TEXT_MODELS:
        return configured
    if configured is not None:
        # Runs at import time, before the logger global exists - stderr is the
        # only safe channel here (stdout carries JSON-RPC).
        print(
            f"Warning: configured model '{configured}' is not a valid text model; "
            f"falling back to {DEFAULT_MODEL_FALLBACK}. "
            f"Run 'python server.py config --model <model>' to update it.",
            file=sys.stderr,
        )
    return DEFAULT_MODEL_FALLBACK

def get_default_voice() -> str:
    """Get the default TTS voice from config file or use fallback"""
    config = load_config()
    if "voice" in config and config["voice"] in AVAILABLE_VOICES:
        return config["voice"]
    return DEFAULT_VOICE_FALLBACK

def handle_config_command(args) -> int:
    """Handle the config subcommand"""
    if args.list_models:
        print("Available Grok models:")
        print("-" * 50)
        current = get_default_model()
        for model, description in AVAILABLE_MODELS.items():
            marker = " *" if model == current else ""
            print(f"  {model}{marker}")
            print(f"    {description}")
        print()
        print("* = currently selected")
        return 0

    if args.list_voices:
        print("Available TTS voices:")
        print("-" * 50)
        current = get_default_voice()
        for voice, description in AVAILABLE_VOICES.items():
            marker = " *" if voice == current else ""
            print(f"  {voice}{marker}")
            print(f"    {description}")
        print()
        print("* = currently selected")
        return 0

    if args.show:
        config = load_config()
        current_model = get_default_model()
        current_voice = get_default_voice()
        print(f"Current model: {current_model}")
        print(f"Current voice: {current_voice}")
        print(f"Config file: {get_config_path()}")
        if config:
            print(f"Config contents: {json.dumps(config, indent=2)}")
        return 0

    if args.model:
        if args.model not in TEXT_MODELS:
            if args.model in AVAILABLE_MODELS:
                print(
                    f"Error: '{args.model}' is an image/video model and cannot be the "
                    f"default chat model. Choose one of: {', '.join(TEXT_MODELS)}",
                    file=sys.stderr,
                )
            else:
                print(f"Error: Unknown model '{args.model}'", file=sys.stderr)
                print(f"Run 'python server.py config --list-models' to see available models", file=sys.stderr)
            return 1

        config = load_config()
        config["model"] = args.model
        if save_config(config):
            print(f"Default model set to: {args.model}")
            print("Restart Claude Code for changes to take effect.")
            return 0
        return 1

    if args.voice:
        if args.voice not in AVAILABLE_VOICES:
            print(f"Error: Unknown voice '{args.voice}'", file=sys.stderr)
            print(f"Run 'python server.py config --list-voices' to see available voices", file=sys.stderr)
            return 1

        config = load_config()
        config["voice"] = args.voice
        if save_config(config):
            print(f"Default voice set to: {args.voice}")
            print("Restart Claude Code for changes to take effect.")
            return 0
        return 1

    # No args - show help
    print("Usage:")
    print("  python server.py config --model <model>  Set default model")
    print("  python server.py config --voice <voice>  Set default TTS voice")
    print("  python server.py config --show           Show current config")
    print("  python server.py config --list-models    List available models")
    print("  python server.py config --list-voices    List available TTS voices")
    return 0

# Only configure logging when running as MCP server (not CLI)
def setup_logging():
    """Configure logging to stderr (stdout is for JSON-RPC)"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stderr
    )
    return logging.getLogger(__name__)

# Input limits for security
MAX_PROMPT_LENGTH = 100000  # 100K characters
MAX_CODE_LENGTH = 500000    # 500K characters for code review

# Default model - loaded from config
DEFAULT_MODEL = get_default_model()

# Default TTS voice - loaded from config
DEFAULT_VOICE = get_default_voice()

# Session management
SESSION_EXPIRY_SECONDS = 30 * 60  # 30 minutes
sessions: Dict[str, Dict[str, Any]] = {}

def generate_session_id() -> str:
    return uuid.uuid4().hex[:8]

def prune_expired_sessions():
    now = time.time()
    expired = [
        sid for sid, s in sessions.items()
        if now - s["last_active"] > SESSION_EXPIRY_SECONDS
    ]
    for sid in expired:
        if logger:
            logger.info(f"Session {sid} expired (model={sessions[sid]['model']})")
        del sessions[sid]

def evict_sessions_over_limit():
    """Drop least-recently-active sessions once MAX_SESSIONS is exceeded."""
    while len(sessions) > MAX_SESSIONS:
        oldest = min(sessions, key=lambda sid: sessions[sid]["last_active"])
        if logger:
            logger.info(f"Session {oldest} evicted (session limit {MAX_SESSIONS} reached)")
        del sessions[oldest]

def window_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return the messages to send: any system prompt plus the most recent turns.

    Session history is otherwise re-sent in full every turn, so cost grows
    quadratically and a long session eventually exceeds the context window.
    """
    if len(messages) <= MAX_SESSION_MESSAGES:
        return messages
    system = [m for m in messages[:1] if m["role"] == "system"]
    recent = messages[-(MAX_SESSION_MESSAGES - len(system)):]
    return system + recent

# Graceful shutdown flag
shutdown_requested = False
logger = None

# API key storage
API_KEY = None

class ShutdownRequested(Exception):
    """Raised from the signal handler to interrupt a blocked stdin read."""

class RequestCancelled(Exception):
    """Raised when the client cancels a long-running request mid-flight."""

# Messages read off stdin while waiting on a long job, replayed by the main loop.
pending_stdin_lines: List[str] = []

def _stdin_has_data() -> bool:
    """True if stdin has a line waiting. POSIX only; returns False elsewhere."""
    if os.name != "posix":
        return False
    try:
        readable, _, _ = select.select([sys.stdin], [], [], 0)
        return bool(readable)
    except Exception:
        return False

def check_for_cancellation(target_request_id: Any) -> bool:
    """Drain stdin without blocking, looking for a cancel of target_request_id.

    Unrelated messages are buffered for the main loop rather than dropped. On
    Windows this is a no-op (select() can't watch a pipe), so cancellation
    there still waits for the poll timeout.
    """
    cancelled = False
    while _stdin_has_data():
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            pending_stdin_lines.append(line)
            continue
        if (
            isinstance(message, dict)
            and message.get("method") == "notifications/cancelled"
            and (message.get("params") or {}).get("requestId") == target_request_id
        ):
            cancelled = True
            continue
        pending_stdin_lines.append(line)
    return cancelled

def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully.

    Raises rather than only setting a flag: per PEP 475 a blocking
    sys.stdin.readline() is transparently retried after a signal, so a flag
    alone would leave the process stuck until EOF.
    """
    global shutdown_requested
    if logger:
        logger.info(f"Received signal {signum}, shutting down gracefully...")
    shutdown_requested = True
    raise ShutdownRequested()

# Initialize Grok
GROK_AVAILABLE = False
GROK_ERROR = ""

def init_grok() -> bool:
    """Initialize Grok API with proper error handling"""
    global GROK_AVAILABLE, GROK_ERROR, API_KEY

    # Get API key from environment
    API_KEY = os.environ.get("XAI_API_KEY")
    if not API_KEY:
        GROK_ERROR = "XAI_API_KEY environment variable is not set"
        if logger:
            logger.error(GROK_ERROR)
        return False

    GROK_AVAILABLE = True
    if logger:
        logger.info(f"Grok API initialized successfully with model: {DEFAULT_MODEL}")
    return True

def send_response(response: Dict[str, Any]):
    """Send a JSON-RPC response"""
    try:
        print(json.dumps(response), flush=True)
    except Exception as e:
        logger.error(f"Failed to send response: {e}")

def truncate_input(text: str, max_length: int, field_name: str) -> str:
    """Truncate input and log warning if needed"""
    if len(text) > max_length:
        logger.warning(f"{field_name} truncated from {len(text)} to {max_length} characters")
        return text[:max_length]
    return text

# ---------------------------------------------------------------------------
# Responses API helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# HTTP with retry
# ---------------------------------------------------------------------------

# 429 and 503 mean the request was NOT processed, so retrying is safe and
# cannot double-charge. Ambiguous 5xx responses are only retried on read-only
# GETs, where a duplicate request has no billing side effect.
RETRY_STATUSES_WRITE = {429, 503}
RETRY_STATUSES_READ = {429, 500, 502, 503, 504}
MAX_API_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds; doubled per attempt

def _retry_delay(response: Optional[Any], attempt: int) -> float:
    """Honour Retry-After when present, else exponential backoff."""
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except ValueError:
                pass
    return RETRY_BASE_DELAY * (2 ** attempt)

def request_with_retry(
    method: str,
    url: str,
    *,
    retry_statuses: Optional[set] = None,
    max_retries: int = MAX_API_RETRIES,
    rewind: Optional[Any] = None,
    **kwargs,
) -> Any:
    """requests.request with bounded retry on transient failures.

    `rewind` is called before each retry so multipart uploads can seek their
    file handles back to the start (a consumed handle would otherwise resend
    an empty body).
    """
    if retry_statuses is None:
        retry_statuses = RETRY_STATUSES_READ if method.upper() == "GET" else RETRY_STATUSES_WRITE

    last_error = ""
    for attempt in range(max_retries + 1):
        if attempt > 0 and rewind is not None:
            rewind()
        try:
            response = requests.request(method, url, **kwargs)
        except requests.RequestException as e:
            last_error = f"{type(e).__name__}: {e}"
            if attempt >= max_retries:
                raise RuntimeError(
                    f"Request to {url} failed after {attempt + 1} attempts - {last_error}"
                )
            delay = _retry_delay(None, attempt)
        else:
            if response.status_code not in retry_statuses or attempt >= max_retries:
                return response
            last_error = f"HTTP {response.status_code}"
            delay = _retry_delay(response, attempt)

        if logger:
            logger.warning(
                f"{last_error} from {url}, retrying in {delay:.0f}s "
                f"(attempt {attempt + 2}/{max_retries + 1})"
            )
        time.sleep(delay)

    # Unreachable: the loop either returns or raises.
    raise RuntimeError(f"Request to {url} failed - {last_error}")

def build_tool_spec(tool_type: str, **kwargs) -> Dict[str, Any]:
    """Build a server-side tool specification for the Responses API."""
    spec: Dict[str, Any] = {"type": tool_type}
    for key, value in kwargs.items():
        if value is not None:
            spec[key] = value
    return spec

def parse_responses_output(response_json: Dict[str, Any]) -> Dict[str, Any]:
    """Parse the Responses API output array into a structured result."""
    text_parts: List[str] = []
    citations: List[Dict[str, str]] = []

    for item in response_json.get("output", []):
        # Handle message items
        if item.get("type") == "message":
            for block in item.get("content", []):
                if block.get("type") == "output_text":
                    text_parts.append(block.get("text", ""))
                    # Collect inline annotations/citations
                    for ann in block.get("annotations", []):
                        if ann.get("type") == "url_citation":
                            citations.append({
                                "url": ann.get("url", ""),
                                "title": ann.get("title", ""),
                            })

    usage = response_json.get("usage", {})
    return {
        "text": "\n".join(text_parts),
        "citations": citations,
        "usage": usage,
    }

def format_citations(citations: List[Dict[str, str]]) -> str:
    """Format citation objects into a markdown Sources section."""
    if not citations:
        return ""
    seen = set()
    lines = ["", "**Sources:**"]
    for c in citations:
        url = c.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        title = c.get("title", url)
        lines.append(f"- [{title}]({url})")
    return "\n".join(lines) if len(lines) > 2 else ""

def call_grok_responses(
    prompt: str,
    system_prompt: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    file_ids: Optional[List[str]] = None,
    timeout: int = TIMEOUT_DEFAULT,
) -> Dict[str, Any]:
    """Call xAI Responses API and return structured result."""
    # Build input array
    input_items: List[Dict[str, Any]] = []
    if system_prompt:
        input_items.append({"role": "developer", "content": system_prompt})

    # Build user content
    if file_ids:
        content_parts: List[Dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        for fid in file_ids:
            content_parts.append({"type": "input_file", "file_id": fid})
        input_items.append({"role": "user", "content": content_parts})
    else:
        input_items.append({"role": "user", "content": prompt})

    payload: Dict[str, Any] = {
        "model": DEFAULT_MODEL,
        "input": input_items,
        "store": False,
    }

    if tools:
        payload["tools"] = tools
        # Enable inline citations when search tools are present
        search_types = {"web_search", "x_search"}
        if any(t.get("type") in search_types for t in tools):
            payload["inline_citations"] = True

    response = request_with_retry(
        "POST",
        XAI_RESPONSES_API_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        timeout=timeout,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Grok API error (HTTP {response.status_code}): {response.text}")

    return parse_responses_output(response.json())

def call_grok_chat(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    timeout: int = TIMEOUT_DEFAULT,
) -> str:
    """Multi-turn chat via xAI Chat Completions API. Returns assistant text."""
    payload: Dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.7,
    }

    response = request_with_retry(
        "POST",
        XAI_CHAT_API_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        timeout=timeout,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Grok API error (HTTP {response.status_code}): {response.text}")

    result = response.json()
    if "choices" in result and len(result["choices"]) > 0:
        return result["choices"][0]["message"]["content"]
    return ""

# ---------------------------------------------------------------------------
# File upload helpers
# ---------------------------------------------------------------------------

def validate_file_path(file_path: str, max_size_mb: int = MAX_FILE_SIZE_MB) -> str:
    """Validate file exists, size, extension. Returns absolute path."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        raise ValueError(f"File not found: {abs_path}")
    size_mb = os.path.getsize(abs_path) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"File too large: {size_mb:.1f}MB (max {max_size_mb}MB)")
    ext = Path(abs_path).suffix.lower()
    if ext not in SUPPORTED_FILE_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Supported: {', '.join(sorted(SUPPORTED_FILE_EXTENSIONS))}")
    return abs_path

def upload_file_to_xai(file_path: str) -> Dict[str, Any]:
    """Upload a file to xAI Files API. Returns {file_id, filename}."""
    abs_path = validate_file_path(file_path)
    filename = os.path.basename(abs_path)

    with open(abs_path, "rb") as f:
        response = request_with_retry(
            "POST",
            XAI_FILES_API_URL,
            files={"file": (filename, f)},
            data={"purpose": "assistants"},
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=TIMEOUT_UPLOAD,
            rewind=lambda: f.seek(0),
        )

    if response.status_code != 200:
        raise RuntimeError(f"File upload failed (HTTP {response.status_code}): {response.text}")

    result = response.json()
    return {
        "file_id": result.get("id", ""),
        "filename": result.get("filename", filename),
    }

# ---------------------------------------------------------------------------
# Image and vision helpers (unchanged endpoints)
# ---------------------------------------------------------------------------

IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".webp": "image/webp", ".bmp": "image/bmp",
}

def get_mime_type(file_path: str) -> str:
    """Detect MIME type from file extension.

    Raises on unknown extensions rather than mislabelling arbitrary bytes as
    image/jpeg, which would let any local file be uploaded as an "image".
    """
    ext = Path(file_path).suffix.lower()
    if ext not in IMAGE_MIME_TYPES:
        raise ValueError(
            f"Unsupported image type: {ext or '(no extension)'}. "
            f"Supported: {', '.join(sorted(SUPPORTED_IMAGE_EXTENSIONS))}"
        )
    return IMAGE_MIME_TYPES[ext]

def _validate_input_path(
    file_path: str, extensions: set, max_size_mb: int, kind: str
) -> str:
    """Shared validation for local files read and sent to xAI."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        raise ValueError(f"File not found: {abs_path}")
    ext = Path(abs_path).suffix.lower()
    if ext not in extensions:
        raise ValueError(
            f"Unsupported {kind} type: {ext or '(no extension)'}. "
            f"Supported: {', '.join(sorted(extensions))}"
        )
    size_mb = os.path.getsize(abs_path) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"{kind.capitalize()} file too large: {size_mb:.1f}MB (max {max_size_mb}MB)")
    return abs_path

def validate_image_path(file_path: str) -> str:
    """Validate an image that will be read and sent to xAI. Returns absolute path."""
    return _validate_input_path(file_path, SUPPORTED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE_MB, "image")

def validate_video_path(file_path: str) -> str:
    """Validate a video that will be read and sent to xAI. Returns absolute path."""
    return _validate_input_path(file_path, SUPPORTED_VIDEO_EXTENSIONS, MAX_VIDEO_SIZE_MB, "video")

def resolve_save_path(save_path: str, overwrite: bool = False) -> str:
    """Resolve an output path, refusing to clobber an existing file by default."""
    abs_path = os.path.abspath(save_path)
    if os.path.exists(abs_path) and not overwrite:
        raise ValueError(
            f"Refusing to overwrite existing file: {abs_path}. "
            f"Pass overwrite=true to replace it, or choose a different save_path."
        )
    return abs_path

def write_file_atomic(abs_path: str, data: bytes) -> str:
    """Write bytes via a temp file + rename so a failure never leaves a partial file."""
    parent = os.path.dirname(abs_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = f"{abs_path}.{os.getpid()}.partial"
    try:
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.replace(tmp_path, abs_path)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    return abs_path

def get_auto_save_path(index: int = 0) -> str:
    """Generate an auto-save path with timestamp"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{index}" if index > 0 else ""
    return os.path.join(OUTPUT_DIR, f"grok_{timestamp}{suffix}.jpg")

def save_image(b64_data: str, save_path: str, overwrite: bool = False) -> str:
    """Decode base64 image data and save to disk. Returns the absolute path."""
    abs_path = resolve_save_path(save_path, overwrite)
    return write_file_atomic(abs_path, base64.b64decode(b64_data))

def call_grok_image_gen(
    prompt: str,
    n: int = 1,
    aspect_ratio: Optional[str] = None,
    model: str = "grok-imagine-image",
    resolution: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Call xAI image generation API. Returns list of {b64_json, revised_prompt}."""
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "response_format": "b64_json",
    }
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    if resolution:
        payload["resolution"] = resolution

    response = request_with_retry(
        "POST",
        XAI_IMAGE_API_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        timeout=TIMEOUT_IMAGE,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Image generation failed (HTTP {response.status_code}): {response.text}")

    result = response.json()
    images = []
    for item in result.get("data", []):
        b64 = item.get("b64_json", "")
        if not b64:
            raise RuntimeError("Image generation returned empty image data — the response may contain a URL instead of base64.")
        images.append({
            "b64_json": b64,
            "revised_prompt": item.get("revised_prompt", prompt),
        })
    if not images:
        raise RuntimeError("Image generation returned no images.")
    return images

def call_grok_image_edit(
    prompt: str,
    image_base64: str,
    mime_type: str,
    model: str = "grok-imagine-image",
) -> Dict[str, str]:
    """Call xAI image edit API. Returns {b64_json, revised_prompt}."""
    data_url = f"data:{mime_type};base64,{image_base64}"
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "image": {"url": data_url},
        "n": 1,
        "response_format": "b64_json",
    }

    response = request_with_retry(
        "POST",
        XAI_IMAGE_EDIT_API_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        timeout=TIMEOUT_IMAGE,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Image edit failed (HTTP {response.status_code}): {response.text}")

    result = response.json()
    data = result.get("data", [])
    if not data:
        raise RuntimeError("Image edit returned no images.")
    b64 = data[0].get("b64_json", "")
    if not b64:
        raise RuntimeError("Image edit returned empty image data.")
    return {
        "b64_json": b64,
        "revised_prompt": data[0].get("revised_prompt", prompt),
    }

def call_grok_vision(image_base64: str, mime_type: str, prompt: str, model: Optional[str] = None) -> str:
    """Call Grok vision model to analyze an image. Returns text response."""
    vision_model = model or DEFAULT_MODEL
    data_url = f"data:{mime_type};base64,{image_base64}"
    payload = {
        "model": vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "stream": False,
        "temperature": 0.7,
    }

    response = request_with_retry(
        "POST",
        XAI_CHAT_API_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        timeout=TIMEOUT_DEFAULT,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Vision analysis failed (HTTP {response.status_code}): {response.text}")

    result = response.json()
    if "choices" in result and len(result["choices"]) > 0:
        return result["choices"][0]["message"]["content"]
    return f"Unexpected response format: {result}"

# ---------------------------------------------------------------------------
# Video generation helpers
# ---------------------------------------------------------------------------

def get_video_save_path() -> str:
    """Generate an auto-save path for video with timestamp."""
    os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(VIDEO_OUTPUT_DIR, f"grok_{timestamp}.mp4")

def call_grok_video_gen(
    prompt: str,
    duration: Optional[int] = None,
    aspect_ratio: Optional[str] = None,
    resolution: Optional[str] = None,
    image_path: Optional[str] = None,
    model: str = DEFAULT_VIDEO_MODEL,
) -> str:
    """Submit a video generation request to /v1/videos/generations.

    Returns request_id for polling. Supports text-to-video and image-to-video.
    For video editing, use call_grok_video_edit instead.
    """
    if model in IMAGE_TO_VIDEO_ONLY_MODELS and not image_path:
        raise ValueError(
            f"{model} supports image-to-video only. Provide image_path, "
            f"or use {DEFAULT_VIDEO_MODEL} for text-to-video."
        )

    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
    }
    if duration is not None:
        payload["duration"] = duration
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    if resolution:
        payload["resolution"] = resolution

    # Image-to-video: read image and send as base64 data URI inside `image` object
    if image_path:
        abs_image = validate_image_path(image_path)
        mime = get_mime_type(abs_image)
        with open(abs_image, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        payload["image"] = {"url": f"data:{mime};base64,{img_b64}"}

    response = request_with_retry(
        "POST",
        XAI_VIDEO_API_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        timeout=TIMEOUT_VIDEO,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Video generation failed (HTTP {response.status_code}): {response.text}")

    result = response.json()
    request_id = result.get("request_id")
    if not request_id:
        raise RuntimeError(f"Video generation returned no request_id: {result}")
    return request_id

def call_grok_video_edit(
    prompt: str,
    video_url: Optional[str] = None,
    video_path: Optional[str] = None,
    file_id: Optional[str] = None,
    model: str = DEFAULT_VIDEO_MODEL,
) -> str:
    """Submit a video edit request to /v1/videos/edits.

    Exactly one of video_url, video_path, or file_id must be provided.
    Source must be .mp4 (H.264 / H.265 / AV1). Returns request_id for polling.
    """
    if model in IMAGE_TO_VIDEO_ONLY_MODELS:
        raise ValueError(
            f"{model} supports image-to-video only and cannot edit video. "
            f"Use {DEFAULT_VIDEO_MODEL} for editing."
        )

    sources = sum(1 for v in (video_url, video_path, file_id) if v)
    if sources != 1:
        raise ValueError("Provide exactly one of: video_url, video_path, file_id")

    if video_path:
        abs_video = validate_video_path(video_path)
        with open(abs_video, "rb") as f:
            vid_b64 = base64.b64encode(f.read()).decode("utf-8")
        video_ref: Dict[str, str] = {"url": f"data:video/mp4;base64,{vid_b64}"}
    elif video_url:
        video_ref = {"url": video_url}
    else:
        video_ref = {"file_id": file_id}  # type: ignore[dict-item]

    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "video": video_ref,
    }

    response = request_with_retry(
        "POST",
        XAI_VIDEO_EDIT_API_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        timeout=TIMEOUT_VIDEO,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Video edit failed (HTTP {response.status_code}): {response.text}")

    result = response.json()
    request_id = result.get("request_id")
    if not request_id:
        raise RuntimeError(f"Video edit returned no request_id: {result}")
    return request_id

def poll_video_status(request_id: str, cancel_check: Optional[Any] = None) -> Dict[str, Any]:
    """Poll for video completion. Returns video result when done.

    The job is already running (and already billed) on xAI's side, so transient
    poll failures retry instead of abandoning it. Every error carries the
    request_id so an abandoned job can still be retrieved manually.
    """
    poll_url = f"https://api.x.ai/v1/videos/{request_id}"
    start = time.time()
    consecutive_errors = 0
    max_consecutive_errors = 5

    def _sleep(seconds: float):
        """Sleep in slices so a cancellation is noticed promptly."""
        deadline = time.time() + seconds
        while time.time() < deadline:
            if cancel_check is not None and cancel_check():
                raise RequestCancelled(
                    f"Video job cancelled by client (request_id: {request_id})"
                )
            time.sleep(min(1.0, max(0.0, deadline - time.time())))

    while time.time() - start < VIDEO_POLL_TIMEOUT:
        if cancel_check is not None and cancel_check():
            raise RequestCancelled(
                f"Video job cancelled by client (request_id: {request_id})"
            )
        try:
            response = requests.get(
                poll_url,
                headers={"Authorization": f"Bearer {API_KEY}"},
                timeout=60,
            )
        except requests.RequestException as e:
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                raise RuntimeError(
                    f"Video poll failed {consecutive_errors}x in a row ({e}). "
                    f"The job may still complete - request_id: {request_id}"
                )
            _sleep(VIDEO_POLL_INTERVAL * consecutive_errors)
            continue

        # Rate limits and server-side blips are transient: back off and retry
        # rather than abandoning a job the user has already paid for.
        if response.status_code == 429 or response.status_code >= 500:
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                raise RuntimeError(
                    f"Video poll failed {consecutive_errors}x in a row "
                    f"(HTTP {response.status_code}). The job may still complete - "
                    f"request_id: {request_id}"
                )
            retry_after = response.headers.get("Retry-After")
            try:
                delay = int(retry_after) if retry_after else VIDEO_POLL_INTERVAL * consecutive_errors
            except ValueError:
                delay = VIDEO_POLL_INTERVAL * consecutive_errors
            if logger:
                logger.warning(
                    f"Video poll got HTTP {response.status_code}, retrying in {delay}s "
                    f"(request_id: {request_id})"
                )
            _sleep(delay)
            continue

        # The xAI API returns HTTP 202 (with {"status":"pending"}) while the job
        # is in flight, and HTTP 200 once it's done. Treat both as pollable.
        if response.status_code not in (200, 202):
            raise RuntimeError(
                f"Video poll failed (HTTP {response.status_code}): {response.text} "
                f"(request_id: {request_id})"
            )

        consecutive_errors = 0
        result = response.json()
        status = result.get("status", "")

        if status == "done":
            return result
        elif status in ("expired", "failed"):
            raise RuntimeError(
                f"Video generation {status}: {result.get('error', result)} "
                f"(request_id: {request_id})"
            )
        elif status == "pending":
            if logger:
                elapsed = int(time.time() - start)
                progress = result.get("progress")
                progress_str = f", progress={progress}%" if progress is not None else ""
                logger.info(f"Video generation pending... ({elapsed}s elapsed{progress_str})")
            _sleep(VIDEO_POLL_INTERVAL)
        else:
            raise RuntimeError(
                f"Unexpected video status: {status} (request_id: {request_id})"
            )

    raise RuntimeError(
        f"Video generation timed out after {VIDEO_POLL_TIMEOUT}s. "
        f"The job may still complete - request_id: {request_id}"
    )

def download_video(url: str, save_path: str, overwrite: bool = False) -> str:
    """Download a video from a temporary URL and save to disk. Returns absolute path."""
    abs_path = resolve_save_path(save_path, overwrite)

    response = request_with_retry("GET", url, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(f"Video download failed (HTTP {response.status_code})")

    return write_file_atomic(abs_path, response.content)

# ---------------------------------------------------------------------------
# Audio (TTS / STT) helpers
# ---------------------------------------------------------------------------

def get_audio_save_path(extension: str = "mp3") -> str:
    """Generate an auto-save path for audio with timestamp."""
    os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(AUDIO_OUTPUT_DIR, f"grok_{timestamp}.{extension}")

def validate_audio_path(file_path: str) -> str:
    """Validate audio file exists, size, and extension. Returns absolute path."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        raise ValueError(f"File not found: {abs_path}")
    size_mb = os.path.getsize(abs_path) / (1024 * 1024)
    if size_mb > MAX_AUDIO_SIZE_MB:
        raise ValueError(f"Audio file too large: {size_mb:.1f}MB (max {MAX_AUDIO_SIZE_MB}MB)")
    ext = Path(abs_path).suffix.lower()
    if ext not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(
            f"Unsupported audio type: {ext}. Supported: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
        )
    return abs_path

def call_grok_tts(
    text: str,
    voice_id: str,
    language: str = "en",
    audio_format: Optional[str] = None,
    sample_rate: Optional[int] = None,
    bitrate: Optional[int] = None,
) -> bytes:
    """Call xAI text-to-speech API. Returns audio bytes.

    audio_format / sample_rate / bitrate are mapped into the API's nested
    output_format object. bitrate is given in kbps and converted to bps.
    """
    payload: Dict[str, Any] = {
        "text": text,
        "voice_id": voice_id,
        "language": language,
    }
    output_format: Dict[str, Any] = {}
    if audio_format:
        output_format["codec"] = audio_format
    if sample_rate:
        output_format["sample_rate"] = sample_rate
    if bitrate:
        output_format["bit_rate"] = bitrate * 1000  # kbps → bps
    if output_format:
        payload["output_format"] = output_format

    response = request_with_retry(
        "POST",
        XAI_TTS_API_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        timeout=TIMEOUT_AUDIO,
    )

    if response.status_code != 200:
        raise RuntimeError(f"TTS request failed (HTTP {response.status_code}): {response.text}")

    return response.content

def call_grok_stt(
    audio_path: Optional[str] = None,
    audio_url: Optional[str] = None,
    language: Optional[str] = None,
    format: Optional[bool] = None,
    diarize: Optional[bool] = None,
    multichannel: Optional[bool] = None,
    channels: Optional[int] = None,
    keyterm: Optional[List[str]] = None,
    filler_words: Optional[bool] = None,
) -> Dict[str, Any]:
    """Call xAI speech-to-text API (/v1/stt). Returns parsed JSON response.

    Provide exactly one of audio_path (local file, uploaded multipart) or
    audio_url (remote URL passed via the `url` form field).
    """
    if bool(audio_path) == bool(audio_url):
        raise ValueError("Provide exactly one of audio_path or audio_url")

    data: Dict[str, Any] = {}
    if audio_url:
        data["url"] = audio_url
    if language:
        data["language"] = language
    if format is not None:
        data["format"] = "true" if format else "false"
    if diarize is not None:
        data["diarize"] = "true" if diarize else "false"
    if multichannel is not None:
        data["multichannel"] = "true" if multichannel else "false"
    if channels is not None:
        data["channels"] = str(channels)
    if filler_words is not None:
        data["filler_words"] = "true" if filler_words else "false"
    # multipart form: repeat the field for arrays
    files_list: List[Any] = []
    if keyterm:
        for term in keyterm:
            files_list.append(("keyterm", (None, term)))

    headers = {"Authorization": f"Bearer {API_KEY}"}

    if audio_path:
        abs_path = validate_audio_path(audio_path)
        filename = os.path.basename(abs_path)
        with open(abs_path, "rb") as f:
            files_list.append(("file", (filename, f)))
            response = request_with_retry(
                "POST",
                XAI_STT_API_URL,
                files=files_list,
                data=data or None,
                headers=headers,
                timeout=TIMEOUT_AUDIO,
                rewind=lambda: f.seek(0),
            )
    else:
        response = request_with_retry(
            "POST",
            XAI_STT_API_URL,
            files=files_list or None,
            data=data,
            headers=headers,
            timeout=TIMEOUT_AUDIO,
        )

    if response.status_code != 200:
        raise RuntimeError(f"STT request failed (HTTP {response.status_code}): {response.text}")

    return response.json()

# ---------------------------------------------------------------------------
# Session tool handlers
# ---------------------------------------------------------------------------

def handle_chat(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle multi-turn chat with session management."""
    prune_expired_sessions()

    message = arguments.get("message", "").strip()
    if not message:
        return {"error": "message is required"}
    message = truncate_input(message, MAX_PROMPT_LENGTH, "message")

    session_id = arguments.get("session_id")

    ignored_overrides = []
    if session_id:
        if session_id not in sessions:
            return {
                "error": f"Session '{session_id}' not found or expired. Start a new session by omitting session_id."
            }
        session = sessions[session_id]
        # These only apply when the session is created; say so rather than
        # silently dropping them.
        for key in ("model", "system_prompt"):
            if arguments.get(key):
                ignored_overrides.append(key)
    else:
        session_id = generate_session_id()
        model = arguments.get("model", DEFAULT_MODEL)
        session = {
            "model": model,
            "messages": [],
            "created_at": time.time(),
            "last_active": time.time(),
        }
        system_prompt = arguments.get("system_prompt")
        if system_prompt:
            session["messages"].append({"role": "system", "content": system_prompt})
        sessions[session_id] = session
        evict_sessions_over_limit()

    session["messages"].append({"role": "user", "content": message})
    session["last_active"] = time.time()

    try:
        response_text = call_grok_chat(
            window_messages(session["messages"]), model=session["model"]
        )
    except Exception:
        # Don't leave an orphaned user message with no reply in the history -
        # it would be re-sent as context on every later turn.
        session["messages"].pop()
        raise

    session["messages"].append({"role": "assistant", "content": response_text})

    turns = sum(1 for m in session["messages"] if m["role"] == "user")

    result = {
        "response": response_text,
        "session_id": session_id,
        "model": session["model"],
        "turn": turns,
        "message_count": len(session["messages"]),
    }
    if ignored_overrides:
        result["warning"] = (
            f"Ignored {', '.join(ignored_overrides)}: these apply only when a session "
            f"is created. Omit session_id to start a new session with them."
        )
    if len(session["messages"]) > MAX_SESSION_MESSAGES:
        result["context_window"] = (
            f"Sending only the most recent {MAX_SESSION_MESSAGES} messages"
        )
    return result

def handle_list_sessions() -> Dict[str, Any]:
    prune_expired_sessions()
    result = []
    for sid, s in sessions.items():
        turns = sum(1 for m in s["messages"] if m["role"] == "user")
        result.append({
            "session_id": sid,
            "model": s["model"],
            "turns": turns,
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(s["created_at"])),
            "last_active": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(s["last_active"])),
        })
    return {"sessions": result}

def handle_end_session(arguments: Dict[str, Any]) -> Dict[str, Any]:
    session_id = arguments.get("session_id", "").strip()
    if not session_id:
        return {"error": "session_id is required"}
    if session_id not in sessions:
        return {"error": f"Session '{session_id}' not found"}
    del sessions[session_id]
    return {"ended": True, "session_id": session_id}

# ---------------------------------------------------------------------------
# MCP protocol handlers
# ---------------------------------------------------------------------------

def handle_initialize(request_id: Any) -> Dict[str, Any]:
    """Handle initialization"""
    logger.info("Handling initialize request")
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {}
            },
            "serverInfo": {
                "name": "grok-mcp",
                "version": __version__
            }
        }
    }

def handle_tools_list(request_id: Any) -> Dict[str, Any]:
    """List available tools"""
    tools = []

    if GROK_AVAILABLE:
        tools = [
            {
                "name": "ask",
                "description": "Ask Grok a question and get the response directly in Claude's context. Trigger: 'use grok', 'ask grok', or 'grok:' followed by a question.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The question or prompt for Grok",
                            "maxLength": MAX_PROMPT_LENGTH
                        },
                        "search": {
                            "type": "boolean",
                            "description": "Enable web search for real-time information (default: false)",
                            "default": False
                        },
                        "file_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File IDs from previous upload_file calls to include as context"
                        }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "code_review",
                "description": "Have Grok review code and return feedback directly to Claude. Trigger: 'grok review', 'grok code review', or 'have grok review'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The code to review",
                            "maxLength": MAX_CODE_LENGTH
                        },
                        "focus": {
                            "type": "string",
                            "description": "Specific focus area (security, performance, etc.)",
                            "default": "general"
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "brainstorm",
                "description": "Brainstorm solutions with Grok, response visible to Claude. Trigger: 'grok brainstorm', 'brainstorm with grok', or 'grok ideas'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "The topic to brainstorm about",
                            "maxLength": MAX_PROMPT_LENGTH
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context",
                            "default": "",
                            "maxLength": MAX_PROMPT_LENGTH
                        }
                    },
                    "required": ["topic"]
                }
            },
            {
                "name": "search_web",
                "description": "Search the web using Grok with real-time results and citations. Grok autonomously searches, browses pages, and synthesizes answers. Trigger: 'grok search', 'grok web search', or 'search with grok'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query or question to research on the web",
                            "maxLength": MAX_PROMPT_LENGTH
                        },
                        "allowed_domains": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Only search within these domains (max 5). Cannot be combined with excluded_domains.",
                            "maxItems": 5
                        },
                        "excluded_domains": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Exclude these domains from search (max 5). Cannot be combined with allowed_domains.",
                            "maxItems": 5
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "search_x",
                "description": "Search X (Twitter) posts using Grok. Find tweets, threads, and discussions from specific users or timeframes. Trigger: 'grok search x', 'grok twitter search', or 'search x with grok'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query or question about X/Twitter content",
                            "maxLength": MAX_PROMPT_LENGTH
                        },
                        "allowed_x_handles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Only search posts from these X handles (max 10, without @ prefix)",
                            "maxItems": 10
                        },
                        "excluded_x_handles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Exclude posts from these X handles (max 10)",
                            "maxItems": 10
                        },
                        "from_date": {
                            "type": "string",
                            "description": "Start date for search range (YYYY-MM-DD format)"
                        },
                        "to_date": {
                            "type": "string",
                            "description": "End date for search range (YYYY-MM-DD format)"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "run_code",
                "description": "Execute Python code in Grok's sandboxed environment with NumPy, Pandas, Matplotlib, SciPy. Useful for calculations, data analysis, and generating visualizations. Trigger: 'grok run code', 'grok execute', or 'grok calculate'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Description of what to compute or analyze. Grok will write and execute Python code automatically.",
                            "maxLength": MAX_PROMPT_LENGTH
                        }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "upload_file",
                "description": "Upload a document for Grok to analyze. Supports: txt, md, py, js, csv, json, pdf, and more (max 48MB). Optionally ask a question about it immediately. Trigger: 'grok upload file', 'upload to grok'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute path to the file to upload"
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional question to ask about the file immediately after upload",
                            "maxLength": MAX_PROMPT_LENGTH
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "generate_image",
                "description": "Generate images using Grok's image models. Returns the image inline and saves to disk. Trigger: 'grok generate image', 'grok image', or 'grok create image'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Image generation prompt describing what to create",
                            "maxLength": MAX_PROMPT_LENGTH
                        },
                        "model": {
                            "type": "string",
                            "description": "Image model to use (default: grok-imagine-image at $0.02/img)",
                            "enum": ["grok-imagine-image", "grok-imagine-image-quality"],
                            "default": "grok-imagine-image"
                        },
                        "n": {
                            "type": "integer",
                            "description": "Number of images to generate (1-10)",
                            "default": 1,
                            "minimum": 1,
                            "maximum": 10
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "description": "Aspect ratio for the generated image",
                            "enum": ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2", "19.5:9", "9:19.5", "20:9", "9:20", "auto"]
                        },
                        "resolution": {
                            "type": "string",
                            "description": "Image resolution: '1k' (~1024px) or '2k' (~2048px)",
                            "enum": ["1k", "2k"]
                        },
                        "save_path": {
                            "type": "string",
                            "description": "File path to save the image. If not provided, auto-saves to output directory."
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Allow replacing an existing file at save_path (default: false - existing files are never overwritten).",
                            "default": False
                        }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "edit_image",
                "description": "Edit an existing image using Grok's Imagine models. Supports style transfer, iterative refinement, and natural language editing. Trigger: 'grok edit image', 'grok modify image', or 'grok image edit'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Natural language description of the desired edits (e.g., 'make it look like an oil painting', 'add a sunset background')",
                            "maxLength": MAX_PROMPT_LENGTH
                        },
                        "image_path": {
                            "type": "string",
                            "description": "Absolute path to the source image to edit"
                        },
                        "model": {
                            "type": "string",
                            "description": "Image model to use (default: grok-imagine-image at $0.02/img)",
                            "enum": ["grok-imagine-image", "grok-imagine-image-quality"],
                            "default": "grok-imagine-image"
                        },
                        "save_path": {
                            "type": "string",
                            "description": "File path to save the edited image. If not provided, auto-saves to output directory."
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Allow replacing an existing file at save_path (default: false - existing files are never overwritten).",
                            "default": False
                        }
                    },
                    "required": ["prompt", "image_path"]
                }
            },
            {
                "name": "generate_video",
                "description": "Generate videos using Grok's Imagine video model. Supports text-to-video and image-to-video. Video generation is async and may take 1-5 minutes. For editing an existing video, use the 'edit_video' tool. Trigger: 'grok generate video', 'grok video', or 'grok create video'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Description of the video to generate",
                            "maxLength": MAX_PROMPT_LENGTH
                        },
                        "duration": {
                            "type": "integer",
                            "description": "Video duration in seconds (1-15, default: 8).",
                            "default": 8,
                            "minimum": 1,
                            "maximum": 15
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "description": "Aspect ratio (default: 16:9).",
                            "enum": ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"],
                            "default": "16:9"
                        },
                        "resolution": {
                            "type": "string",
                            "description": "Video resolution (default: 480p).",
                            "enum": ["480p", "720p", "1080p"],
                            "default": "480p"
                        },
                        "image_path": {
                            "type": "string",
                            "description": "Absolute path to a source image for image-to-video mode. The image will be animated based on the prompt."
                        },
                        "model": {
                            "type": "string",
                            "description": "Video model to use (default: grok-imagine-video at $0.05/sec, supports text-to-video and image-to-video; grok-imagine-video-1.5 is higher quality at $0.08/sec but is image-to-video only, so image_path is required with it)",
                            "enum": VIDEO_MODELS,
                            "default": DEFAULT_VIDEO_MODEL
                        },
                        "save_path": {
                            "type": "string",
                            "description": "File path to save the video. If not provided, auto-saves to output directory."
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Allow replacing an existing file at save_path (default: false - existing files are never overwritten).",
                            "default": False
                        }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "edit_video",
                "description": "Edit an existing video using Grok's Imagine video model via /v1/videos/edits. Apply natural-language edits to a source MP4 (H.264 / H.265 / AV1). Provide exactly one of video_path, video_url, or file_id. Trigger: 'grok edit video' or 'grok modify video'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Natural-language edit instructions (e.g. 'give the woman a silver necklace', 'change the background to a snowy mountain').",
                            "maxLength": MAX_PROMPT_LENGTH
                        },
                        "video_path": {
                            "type": "string",
                            "description": "Absolute path to a local source MP4 to edit. Uploaded inline as a base64 data URI."
                        },
                        "video_url": {
                            "type": "string",
                            "description": "Public URL of a source MP4 to edit (alternative to video_path)."
                        },
                        "file_id": {
                            "type": "string",
                            "description": "xAI file_id of a previously uploaded video (alternative to video_path / video_url)."
                        },
                        "model": {
                            "type": "string",
                            "description": "Video model to use. Only grok-imagine-video supports editing ($0.05/sec); grok-imagine-video-1.5 is image-to-video only and is rejected here.",
                            "enum": VIDEO_EDIT_MODELS,
                            "default": DEFAULT_VIDEO_MODEL
                        },
                        "save_path": {
                            "type": "string",
                            "description": "File path to save the edited video. If not provided, auto-saves to output directory."
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Allow replacing an existing file at save_path (default: false - existing files are never overwritten).",
                            "default": False
                        }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "analyze_image",
                "description": "Analyze an image using Grok's vision capabilities. Uses your configured default model (Grok 4.5, 4.3 and 4.20 support vision natively). Trigger: 'grok analyze image', 'grok describe image', or 'grok vision'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Absolute path to the image file to analyze"
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Question or instruction about the image",
                            "default": "Describe this image in detail",
                            "maxLength": MAX_PROMPT_LENGTH
                        },
                        "model": {
                            "type": "string",
                            "description": "Vision model to use. Defaults to your configured model. Grok 4.5, 4.3 and the 4.20 variants all support vision natively.",
                            "enum": ["grok-4.5", "grok-4.3", "grok-4.20-0309-reasoning", "grok-4.20-0309-non-reasoning", "grok-4.20-multi-agent-0309"]
                        }
                    },
                    "required": ["image_path"]
                }
            },
            {
                "name": "text_to_speech",
                "description": (
                    "Convert text to natural-sounding speech using Grok's TTS API. "
                    "Saves audio (MP3) to disk and returns the path. "
                    "Trigger: 'grok speak', 'grok text to speech', 'grok tts', or 'grok say'."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to synthesize into speech. Supports inline speech tags for emotion (e.g. laughter, whispers, pauses).",
                            "maxLength": MAX_PROMPT_LENGTH,
                        },
                        "voice": {
                            "type": "string",
                            "description": f"Built-in voice (default: configured voice '{DEFAULT_VOICE}') — ara (warm female), eve (energetic female), leo (authoritative male), rex (confident male), sal (neutral) — OR a custom cloned voice ID (8 lowercase alphanumeric characters).",
                        },
                        "language": {
                            "type": "string",
                            "description": "Language code (default: 'en'). Grok TTS supports 20+ languages.",
                            "default": "en",
                        },
                        "audio_format": {
                            "type": "string",
                            "description": "Output codec (default: mp3).",
                            "enum": TTS_AUDIO_FORMATS,
                        },
                        "sample_rate": {
                            "type": "integer",
                            "description": "Sample rate in Hz (default: 24000).",
                            "enum": TTS_SAMPLE_RATES,
                        },
                        "bitrate": {
                            "type": "integer",
                            "description": "MP3 bitrate in kbps (default: 128). MP3 only.",
                            "enum": TTS_MP3_BITRATES,
                        },
                        "save_path": {
                            "type": "string",
                            "description": "File path to save the audio. If not provided, auto-saves to GROK_AUDIO_OUTPUT_DIR with a timestamp.",
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Allow replacing an existing file at save_path (default: false - existing files are never overwritten).",
                            "default": False,
                        },
                    },
                    "required": ["text"],
                },
            },
            {
                "name": "speech_to_text",
                "description": (
                    "Transcribe an audio file to text using Grok's STT API (/v1/stt). "
                    "Supports MP3, WAV, FLAC, M4A, OGG, and other common formats (max 500MB). "
                    "24 languages with optional speaker diarization, multi-channel, and keyterm boosting. "
                    "Provide exactly one of audio_path or audio_url. "
                    "Trigger: 'grok transcribe', 'grok speech to text', 'grok stt', or 'grok listen'."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "audio_path": {
                            "type": "string",
                            "description": "Absolute path to a local audio file to transcribe.",
                        },
                        "audio_url": {
                            "type": "string",
                            "description": "Public URL of the audio to transcribe (alternative to audio_path).",
                        },
                        "language": {
                            "type": "string",
                            "description": "ISO language code (e.g. 'en', 'es'). Auto-detected if omitted.",
                        },
                        "format": {
                            "type": "boolean",
                            "description": "Enable text formatting (punctuation, casing). Default: false.",
                        },
                        "diarize": {
                            "type": "boolean",
                            "description": "Enable speaker diarization (per-speaker labels). Default: false.",
                        },
                        "multichannel": {
                            "type": "boolean",
                            "description": "Enable per-channel transcription. Default: false.",
                        },
                        "channels": {
                            "type": "integer",
                            "description": "Number of channels in the source audio (for raw/headerless audio).",
                        },
                        "keyterm": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Up to 100 keyterms to boost recognition for (proper nouns, jargon, etc.).",
                            "maxItems": 100,
                        },
                        "filler_words": {
                            "type": "boolean",
                            "description": "Include filler words ('um', 'uh') in the transcript. Default: false.",
                        },
                    },
                },
            },
            {
                "name": "chat",
                "description": (
                    "Multi-turn conversation with Grok. "
                    "Omit session_id to start a new conversation; "
                    "provide session_id to continue an existing one. "
                    "Grok remembers the full conversation history within a session. "
                    "Trigger: 'grok chat', 'chat with grok', or 'start a conversation with grok'."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The message to send",
                            "maxLength": MAX_PROMPT_LENGTH,
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Session ID to continue (omit to start new session)",
                        },
                        "model": {
                            "type": "string",
                            "description": "Override model (first message only)",
                            "enum": TEXT_MODELS,
                        },
                        "system_prompt": {
                            "type": "string",
                            "description": "System prompt (first message only)",
                        },
                    },
                    "required": ["message"],
                },
            },
            {
                "name": "list_sessions",
                "description": (
                    "List active Grok chat sessions. "
                    "Trigger: 'grok sessions', 'list grok sessions'."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "end_session",
                "description": (
                    "End and clean up a Grok chat session. "
                    "Trigger: 'end grok session', 'grok end session'."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "The session ID to end",
                        },
                    },
                    "required": ["session_id"],
                },
            },
        ]
    else:
        tools = [
            {
                "name": "server_info",
                "description": "Get server status and error information",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "tools": tools
        }
    }

def handle_tool_call(request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle tool execution"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    logger.info(f"Handling tool call: {tool_name}")

    try:
        result = ""

        if tool_name == "server_info":
            if GROK_AVAILABLE:
                result = f"Server v{__version__} - Grok connected and ready! Model: {DEFAULT_MODEL}"
            else:
                result = f"Server v{__version__} - Grok error: {GROK_ERROR}"

        elif tool_name == "ask":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                prompt = arguments.get("prompt", "")
                prompt = truncate_input(prompt, MAX_PROMPT_LENGTH, "prompt")
                if not prompt.strip():
                    raise ValueError("prompt cannot be empty")

                tools = []
                if arguments.get("search"):
                    tools.append(build_tool_spec("web_search"))
                file_ids = arguments.get("file_ids")

                resp = call_grok_responses(
                    prompt,
                    tools=tools or None,
                    file_ids=file_ids,
                    timeout=TIMEOUT_TOOLS if tools else TIMEOUT_DEFAULT,
                )
                result = resp["text"]
                cites = format_citations(resp.get("citations", []))
                if cites:
                    result += cites

        elif tool_name == "code_review":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                code = arguments.get("code", "")
                code = truncate_input(code, MAX_CODE_LENGTH, "code")
                if not code.strip():
                    raise ValueError("code cannot be empty")
                focus = arguments.get("focus", "general")
                # Sanitize focus to prevent prompt injection
                focus = focus[:50].replace("\n", " ").strip() or "general"

                prompt = f"""Please review this code with a focus on {focus}:

```
{code}
```

Provide specific, actionable feedback on:
1. Potential issues or bugs
2. Security concerns
3. Performance optimizations
4. Best practices
5. Code clarity and maintainability"""
                resp = call_grok_responses(prompt, system_prompt="You are an expert code reviewer.")
                result = resp["text"]

        elif tool_name == "brainstorm":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                topic = arguments.get("topic", "")
                topic = truncate_input(topic, MAX_PROMPT_LENGTH, "topic")
                if not topic.strip():
                    raise ValueError("topic cannot be empty")
                context = arguments.get("context", "")
                context = truncate_input(context, MAX_PROMPT_LENGTH, "context")

                prompt = f"Let's brainstorm about: {topic}"
                if context:
                    prompt += f"\n\nContext: {context}"
                prompt += "\n\nProvide creative ideas, alternatives, and considerations."
                resp = call_grok_responses(prompt, system_prompt="You are a creative problem solver and brainstorming partner.")
                result = resp["text"]

        elif tool_name == "search_web":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                query = arguments.get("query", "")
                query = truncate_input(query, MAX_PROMPT_LENGTH, "query")
                if not query.strip():
                    raise ValueError("query cannot be empty")

                allowed = arguments.get("allowed_domains")
                excluded = arguments.get("excluded_domains")
                if allowed and excluded:
                    raise ValueError("Cannot use both allowed_domains and excluded_domains")

                # web_search takes domain filters nested under `filters`
                # (unlike x_search, whose handle/date fields are top-level).
                filters = {}
                if allowed:
                    filters["allowed_domains"] = allowed[:5]
                if excluded:
                    filters["excluded_domains"] = excluded[:5]

                tools = [build_tool_spec("web_search", filters=filters or None)]
                resp = call_grok_responses(query, tools=tools, timeout=TIMEOUT_TOOLS)
                result = resp["text"]
                cites = format_citations(resp.get("citations", []))
                if cites:
                    result += cites

        elif tool_name == "search_x":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                query = arguments.get("query", "")
                query = truncate_input(query, MAX_PROMPT_LENGTH, "query")
                if not query.strip():
                    raise ValueError("query cannot be empty")

                allowed_handles = arguments.get("allowed_x_handles")
                excluded_handles = arguments.get("excluded_x_handles")
                if allowed_handles and excluded_handles:
                    raise ValueError("Cannot use both allowed_x_handles and excluded_x_handles")

                tool_kwargs = {}
                if allowed_handles:
                    tool_kwargs["allowed_x_handles"] = allowed_handles[:10]
                if excluded_handles:
                    tool_kwargs["excluded_x_handles"] = excluded_handles[:10]
                if arguments.get("from_date"):
                    tool_kwargs["from_date"] = arguments["from_date"]
                if arguments.get("to_date"):
                    tool_kwargs["to_date"] = arguments["to_date"]

                tools = [build_tool_spec("x_search", **tool_kwargs)]
                resp = call_grok_responses(query, tools=tools, timeout=TIMEOUT_TOOLS)
                result = resp["text"]
                cites = format_citations(resp.get("citations", []))
                if cites:
                    result += cites

        elif tool_name == "run_code":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                prompt = arguments.get("prompt", "")
                prompt = truncate_input(prompt, MAX_PROMPT_LENGTH, "prompt")
                if not prompt.strip():
                    raise ValueError("prompt cannot be empty")

                tools = [build_tool_spec("code_interpreter")]
                resp = call_grok_responses(prompt, tools=tools, timeout=TIMEOUT_TOOLS)
                result = resp["text"]

        elif tool_name == "upload_file":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                file_path = arguments.get("file_path", "")
                if not file_path.strip():
                    raise ValueError("file_path cannot be empty")

                upload_result = upload_file_to_xai(file_path)
                file_id = upload_result["file_id"]
                filename = upload_result["filename"]

                query = arguments.get("query", "")
                if query.strip():
                    query = truncate_input(query, MAX_PROMPT_LENGTH, "query")
                    resp = call_grok_responses(query, file_ids=[file_id])
                    result = f"File '{filename}' uploaded (ID: {file_id}).\n\n{resp['text']}"
                else:
                    result = f"File '{filename}' uploaded successfully.\nFile ID: {file_id}\n\nUse this file_id with the 'ask' tool's file_ids parameter to ask questions about it."

        elif tool_name == "generate_image":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                prompt = arguments.get("prompt", "")
                prompt = truncate_input(prompt, MAX_PROMPT_LENGTH, "prompt")
                if not prompt.strip():
                    raise ValueError("prompt cannot be empty")
                n = min(max(int(arguments.get("n", 1)), 1), 10)
                aspect_ratio = arguments.get("aspect_ratio")
                resolution = arguments.get("resolution")
                model = arguments.get("model", "grok-imagine-image")
                save_path = arguments.get("save_path")
                overwrite = bool(arguments.get("overwrite", False))

                # Fail before spending on generation if the target exists.
                if save_path:
                    for i in range(n):
                        if n == 1:
                            candidate = save_path
                        else:
                            base, ext = os.path.splitext(save_path)
                            candidate = f"{base}_{i}{ext}"
                        resolve_save_path(candidate, overwrite)

                images = call_grok_image_gen(prompt, n, aspect_ratio, model, resolution)

                content_blocks = []
                for i, img in enumerate(images):
                    # Determine save path
                    if save_path and n == 1:
                        path = save_path
                    elif save_path and n > 1:
                        base, ext = os.path.splitext(save_path)
                        path = f"{base}_{i}{ext}"
                    else:
                        path = get_auto_save_path(i)

                    abs_path = save_image(img["b64_json"], path, overwrite)

                    content_blocks.append({
                        "type": "text",
                        "text": f"Image {i + 1} saved to: {abs_path}\nRevised prompt: {img['revised_prompt']}",
                    })

                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": content_blocks},
                }

        elif tool_name == "edit_image":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                prompt = arguments.get("prompt", "")
                prompt = truncate_input(prompt, MAX_PROMPT_LENGTH, "prompt")
                if not prompt.strip():
                    raise ValueError("prompt cannot be empty")

                image_path = arguments.get("image_path", "")
                if not image_path.strip():
                    raise ValueError("image_path cannot be empty")
                abs_image = validate_image_path(image_path)

                model = arguments.get("model", "grok-imagine-image")
                save_path = arguments.get("save_path")
                overwrite = bool(arguments.get("overwrite", False))
                if save_path:
                    resolve_save_path(save_path, overwrite)

                mime_type = get_mime_type(abs_image)
                with open(abs_image, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("utf-8")

                edited = call_grok_image_edit(prompt, image_base64, mime_type, model)

                if not save_path:
                    save_path = get_auto_save_path()
                abs_path = save_image(edited["b64_json"], save_path, overwrite)

                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Edited image saved to: {abs_path}\nRevised prompt: {edited['revised_prompt']}",
                            }
                        ]
                    },
                }

        elif tool_name == "generate_video":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                prompt = arguments.get("prompt", "")
                prompt = truncate_input(prompt, MAX_PROMPT_LENGTH, "prompt")
                if not prompt.strip():
                    raise ValueError("prompt cannot be empty")

                duration = arguments.get("duration")
                if duration is not None:
                    duration = min(max(int(duration), 1), 15)
                aspect_ratio = arguments.get("aspect_ratio")
                resolution = arguments.get("resolution")
                save_path = arguments.get("save_path")
                overwrite = bool(arguments.get("overwrite", False))
                if save_path:
                    resolve_save_path(save_path, overwrite)
                video_model = arguments.get("model", DEFAULT_VIDEO_MODEL)

                # Image-to-video mode (validated inside call_grok_video_gen)
                image_path = arguments.get("image_path")

                # Submit generation request
                vid_request_id = call_grok_video_gen(
                    prompt, duration, aspect_ratio, resolution, image_path, video_model
                )
                logger.info(f"Video generation submitted: {vid_request_id}")

                # Poll for completion
                video_result = poll_video_status(
                    vid_request_id,
                    cancel_check=lambda: check_for_cancellation(request_id),
                )

                # Download and save
                video_data = video_result.get("video", {})
                video_url_result = video_data.get("url")
                if not video_url_result:
                    raise RuntimeError(f"Video result missing URL: {video_result}")

                if not save_path:
                    save_path = get_video_save_path()
                abs_path = download_video(video_url_result, save_path, overwrite)

                video_duration = video_data.get("duration", "unknown")
                mode = "image-to-video" if image_path else "text-to-video"

                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Video saved to: {abs_path}\nMode: {mode}\nDuration: {video_duration}s\nRequest ID: {vid_request_id}",
                            }
                        ]
                    },
                }

        elif tool_name == "edit_video":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                prompt = arguments.get("prompt", "")
                prompt = truncate_input(prompt, MAX_PROMPT_LENGTH, "prompt")
                if not prompt.strip():
                    raise ValueError("prompt cannot be empty")

                video_path = arguments.get("video_path")
                video_url = arguments.get("video_url")
                file_id = arguments.get("file_id")
                save_path = arguments.get("save_path")
                overwrite = bool(arguments.get("overwrite", False))
                if save_path:
                    resolve_save_path(save_path, overwrite)
                video_model = arguments.get("model", DEFAULT_VIDEO_MODEL)

                # video_path is validated inside call_grok_video_edit
                vid_request_id = call_grok_video_edit(
                    prompt,
                    video_url=video_url,
                    video_path=video_path,
                    file_id=file_id,
                    model=video_model,
                )
                logger.info(f"Video edit submitted: {vid_request_id}")

                video_result = poll_video_status(
                    vid_request_id,
                    cancel_check=lambda: check_for_cancellation(request_id),
                )
                video_data = video_result.get("video", {})
                video_url_result = video_data.get("url")
                if not video_url_result:
                    raise RuntimeError(f"Video edit result missing URL: {video_result}")

                if not save_path:
                    save_path = get_video_save_path()
                abs_path = download_video(video_url_result, save_path, overwrite)

                source = "video_path" if video_path else ("video_url" if video_url else "file_id")
                video_duration = video_data.get("duration", "unknown")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Edited video saved to: {abs_path}\nSource: {source}\nDuration: {video_duration}s\nRequest ID: {vid_request_id}",
                            }
                        ]
                    },
                }

        elif tool_name == "analyze_image":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                image_path = arguments.get("image_path", "")
                if not image_path.strip():
                    raise ValueError("image_path cannot be empty")
                abs_image = validate_image_path(image_path)

                prompt = arguments.get("prompt", "Describe this image in detail")
                prompt = truncate_input(prompt, MAX_PROMPT_LENGTH, "prompt")
                model = arguments.get("model")

                mime_type = get_mime_type(abs_image)
                with open(abs_image, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("utf-8")

                result = call_grok_vision(image_base64, mime_type, prompt, model)

        elif tool_name == "text_to_speech":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                text = arguments.get("text", "")
                text = truncate_input(text, MAX_TTS_TEXT_LENGTH, "text")
                if not text.strip():
                    raise ValueError("text cannot be empty")

                voice = arguments.get("voice") or DEFAULT_VOICE
                if not is_valid_voice_id(voice):
                    raise ValueError(
                        f"Invalid voice '{voice}'. Use a built-in ({', '.join(AVAILABLE_VOICES.keys())}) "
                        f"or a custom cloned voice ID (8 lowercase alphanumeric characters)."
                    )
                language = arguments.get("language", "en")
                audio_format = arguments.get("audio_format")
                sample_rate = arguments.get("sample_rate")
                bitrate = arguments.get("bitrate")

                extension = TTS_FORMAT_EXTENSIONS.get(audio_format or "mp3", "mp3")
                save_path = arguments.get("save_path") or get_audio_save_path(extension)
                overwrite = bool(arguments.get("overwrite", False))
                abs_path = resolve_save_path(save_path, overwrite)

                audio_bytes = call_grok_tts(
                    text, voice, language,
                    audio_format=audio_format,
                    sample_rate=sample_rate,
                    bitrate=bitrate,
                )

                write_file_atomic(abs_path, audio_bytes)

                voice_label = AVAILABLE_VOICES.get(voice, "custom cloned voice")
                size_kb = len(audio_bytes) / 1024
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Audio saved to: {abs_path}\n"
                                    f"Voice: {voice} ({voice_label})\n"
                                    f"Language: {language}\n"
                                    f"Size: {size_kb:.1f} KB"
                                ),
                            }
                        ]
                    },
                }

        elif tool_name == "speech_to_text":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                audio_path = (arguments.get("audio_path") or "").strip() or None
                audio_url = (arguments.get("audio_url") or "").strip() or None
                if not audio_path and not audio_url:
                    raise ValueError("Provide audio_path or audio_url")

                stt_result = call_grok_stt(
                    audio_path=audio_path,
                    audio_url=audio_url,
                    language=arguments.get("language"),
                    format=arguments.get("format"),
                    diarize=arguments.get("diarize"),
                    multichannel=arguments.get("multichannel"),
                    channels=arguments.get("channels"),
                    keyterm=arguments.get("keyterm"),
                    filler_words=arguments.get("filler_words"),
                )

                # Surface a clean transcription up top, then the full payload
                transcript = stt_result.get("text", "") if isinstance(stt_result, dict) else ""
                payload_json = json.dumps(stt_result, indent=2)

                if transcript:
                    text_out = f"Transcription:\n\n{transcript}\n\n---\nFull response:\n{payload_json}"
                else:
                    text_out = f"STT response:\n{payload_json}"

                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": text_out}],
                    },
                }

        elif tool_name == "chat":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                chat_result = handle_chat(arguments)
                if "error" in chat_result:
                    raise ValueError(chat_result["error"])
                text = json.dumps(chat_result, indent=2)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": f"GROK RESPONSE:\n\n{text}"}],
                    },
                }

        elif tool_name == "list_sessions":
            text = json.dumps(handle_list_sessions(), indent=2)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": text}],
                },
            }

        elif tool_name == "end_session":
            end_result = handle_end_session(arguments)
            if "error" in end_result:
                raise ValueError(end_result["error"])
            text = json.dumps(end_result, indent=2)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": text}],
                },
            }

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": f"GROK RESPONSE:\n\n{result}"
                    }
                ]
            }
        }
    except RequestCancelled as e:
        # Per MCP, a cancelled request gets no response at all.
        logger.info(f"Tool call cancelled for {tool_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Tool call error for {tool_name}: {e}")
        # MCP convention: tool *execution* failures are reported in-band with
        # isError so the model can see the message and adjust. Top-level
        # JSON-RPC errors are reserved for protocol-level problems.
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": f"ERROR: {e}"}],
                "isError": True
            }
        }

# ---------------------------------------------------------------------------
# Main server loop
# ---------------------------------------------------------------------------

def main():
    """Main server loop"""
    global shutdown_requested

    logger.info(f"Starting Grok MCP server v{__version__}")
    logger.info(f"Using Responses API + direct HTTP (no SDK)")
    logger.info(f"Model: {DEFAULT_MODEL}")
    logger.info(f"Default TTS voice: {DEFAULT_VOICE}")
    logger.info(f"Grok available: {GROK_AVAILABLE}")
    if not GROK_AVAILABLE:
        logger.warning(f"Grok initialization failed: {GROK_ERROR}")

    while not shutdown_requested:
        request_id = None
        try:
            # Messages buffered while a long job was running come first.
            if pending_stdin_lines:
                line = pending_stdin_lines.pop(0)
            else:
                line = sys.stdin.readline()
                if not line:
                    logger.info("EOF received, shutting down")
                    break

            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON received: {e}")
                continue

            if not isinstance(request, dict):
                logger.warning("Received a non-object JSON-RPC message, ignoring")
                send_response({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "Invalid Request: expected a JSON object"}
                })
                continue

            method = request.get("method")
            request_id = request.get("id")
            params = request.get("params", {})

            # Handle notifications (no response needed)
            if method == "notifications/initialized":
                logger.info("Client initialized notification received")
                continue
            elif method == "notifications/cancelled":
                logger.info(f"Request cancelled: {params.get('requestId')}")
                continue

            # Handle requests (response required)
            if method == "initialize":
                response = handle_initialize(request_id)
            elif method == "tools/list":
                response = handle_tools_list(request_id)
            elif method == "tools/call":
                response = handle_tool_call(request_id, params)
            elif method == "resources/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"resources": []}
                }
            elif method == "ping":
                # MCP base protocol: respond with an empty result object.
                response = {"jsonrpc": "2.0", "id": request_id, "result": {}}
            elif method == "prompts/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"prompts": []}
                }
            else:
                logger.warning(f"Unknown method: {method}")
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

            # handle_tool_call returns None for a cancelled request: no reply.
            if response is not None:
                send_response(response)

        except ShutdownRequested:
            logger.info("Shutdown signal received, stopping")
            break
        except EOFError:
            logger.info("EOF received, shutting down")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            if request_id is not None:
                send_response({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                })

    logger.info("Server shutdown complete")

def run_server():
    """Initialize and run the MCP server"""
    global logger

    # Setup logging for server mode
    logger = setup_logging()

    # Ensure unbuffered output for MCP protocol
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 1)
    sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 1)

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Initialize Grok API
    init_grok()

    # Run main loop
    main()

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Grok MCP Server for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python server.py                                       Run as MCP server
  python server.py config --model grok-4.3                 Set default model
  python server.py config --voice eve                    Set default TTS voice
  python server.py config --show                         Show current config
  python server.py config --list-models                  List available models
  python server.py config --list-voices                  List available TTS voices
        """
    )
    subparsers = parser.add_subparsers(dest="command")

    # Config subcommand
    config_parser = subparsers.add_parser("config", help="Configure the Grok MCP server")
    config_parser.add_argument("--model", "-m", help="Set the default Grok model")
    config_parser.add_argument("--voice", "-v", help="Set the default TTS voice (ara, eve, leo, rex, sal)")
    config_parser.add_argument("--show", "-s", action="store_true", help="Show current configuration")
    config_parser.add_argument("--list-models", "-l", action="store_true", help="List available models")
    config_parser.add_argument("--list-voices", action="store_true", help="List available TTS voices")

    args = parser.parse_args()

    if args.command == "config":
        sys.exit(handle_config_command(args))
    else:
        # No subcommand = run as MCP server
        run_server()
