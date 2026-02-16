#!/usr/bin/env python3
"""
Claude Code + Grok MCP Server
Enables Claude Code to collaborate with xAI's Grok AI

Usage:
  As MCP server (default):  python server.py
  Configure model:          python server.py config --model grok-4-1-fast-reasoning
  Show current config:      python server.py config --show
  List available models:    python server.py config --list-models
"""

import argparse
import base64
import json
import sys
import os
import signal
import logging
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Server version
__version__ = "3.1.0"

# xAI API endpoints
XAI_CHAT_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_RESPONSES_API_URL = "https://api.x.ai/v1/responses"
XAI_IMAGE_API_URL = "https://api.x.ai/v1/images/generations"
XAI_IMAGE_EDIT_API_URL = "https://api.x.ai/v1/images/edits"
XAI_VIDEO_API_URL = "https://api.x.ai/v1/videos/generations"
XAI_FILES_API_URL = "https://api.x.ai/v1/files"

# Timeouts (seconds)
TIMEOUT_DEFAULT = int(os.environ.get("GROK_TIMEOUT", "180"))
TIMEOUT_TOOLS = 300   # web_search, x_search, code_interpreter
TIMEOUT_UPLOAD = 120
TIMEOUT_IMAGE = 120
TIMEOUT_VIDEO = 300       # video generation submission
VIDEO_POLL_INTERVAL = 5   # seconds between status checks
VIDEO_POLL_TIMEOUT = 600  # max 10 minutes waiting for video

# Default output directories for generated media
OUTPUT_DIR = os.environ.get("GROK_OUTPUT_DIR", "./generated-images")
VIDEO_OUTPUT_DIR = os.environ.get("GROK_VIDEO_OUTPUT_DIR", "./generated-videos")

# File upload limits
MAX_FILE_SIZE_MB = 48
SUPPORTED_FILE_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp",
    ".h", ".go", ".rs", ".rb", ".php", ".css", ".html", ".xml", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".sh", ".bat", ".ps1", ".csv", ".json", ".jsonl",
    ".pdf", ".log", ".sql", ".r", ".swift", ".kt", ".scala", ".lua",
}

# Available Grok models (from xAI API)
AVAILABLE_MODELS = {
    "grok-4-1-fast-reasoning": "Grok 4.1 Fast with reasoning (2M context) - Default",
    "grok-4": "Grok 4 flagship model",
    "grok-4-1-fast-non-reasoning": "Grok 4.1 Fast without reasoning (2M context)",
    "grok-4-fast-reasoning": "Grok 4 Fast with reasoning",
    "grok-4-fast-non-reasoning": "Grok 4 Fast without reasoning",
    "grok-4-0709": "Grok 4 (July 2025 release)",
    "grok-3": "Grok 3 - Previous flagship (128K context)",
    "grok-3-mini": "Grok 3 Mini - Lighter/cheaper option (128K context)",
    "grok-2-1212": "Grok 2 (128K context)",
    "grok-2-vision-1212": "Grok 2 Vision (32K context)",
    "grok-code-fast-1": "Grok Code Fast - Optimized for coding",
    # Image generation models
    "grok-2-image-1212": "Aurora image generation (text→image, $0.07/img)",
    "grok-imagine-image": "Imagine image gen + editing (text,image→image, $0.02/img)",
    "grok-imagine-image-pro": "Imagine Pro image gen + editing (higher quality, $0.07/img)",
    # Video generation model
    "grok-imagine-video": "Imagine video generation (text,image,video→video, $0.05/sec)",
}

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

def get_default_model() -> str:
    """Get the default model from config file or use fallback"""
    config = load_config()
    if "model" in config:
        return config["model"]
    return "grok-4-1-fast-reasoning"

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

    if args.show:
        config = load_config()
        current_model = get_default_model()
        print(f"Current model: {current_model}")
        print(f"Config file: {get_config_path()}")
        if config:
            print(f"Config contents: {json.dumps(config, indent=2)}")
        return 0

    if args.model:
        if args.model not in AVAILABLE_MODELS:
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

    # No args - show help
    print("Usage:")
    print("  python server.py config --model <model>  Set default model")
    print("  python server.py config --show           Show current config")
    print("  python server.py config --list-models    List available models")
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

# Graceful shutdown flag
shutdown_requested = False
logger = None

# API key storage
API_KEY = None

def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    if logger:
        logger.info(f"Received signal {signum}, shutting down gracefully...")
    shutdown_requested = True

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

    response = requests.post(
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
        response = requests.post(
            XAI_FILES_API_URL,
            files={"file": (filename, f)},
            data={"purpose": "assistants"},
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=TIMEOUT_UPLOAD,
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

def get_mime_type(file_path: str) -> str:
    """Detect MIME type from file extension"""
    ext = Path(file_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif",
        ".webp": "image/webp", ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/jpeg")

def get_auto_save_path(index: int = 0) -> str:
    """Generate an auto-save path with timestamp"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{index}" if index > 0 else ""
    return os.path.join(OUTPUT_DIR, f"grok_{timestamp}{suffix}.jpg")

def save_image(b64_data: str, save_path: str) -> str:
    """Decode base64 image data and save to disk. Returns the absolute path."""
    abs_path = os.path.abspath(save_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return abs_path

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

    response = requests.post(
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

    response = requests.post(
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

    response = requests.post(
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
    video_url: Optional[str] = None,
) -> str:
    """Submit a video generation request. Returns request_id for polling."""
    payload: Dict[str, Any] = {
        "model": "grok-imagine-video",
        "prompt": prompt,
    }
    if duration is not None:
        payload["duration"] = duration
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    if resolution:
        payload["resolution"] = resolution

    # Image-to-video: read image and send as base64 data URI
    if image_path:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        mime = get_mime_type(image_path)
        payload["image_url"] = f"data:{mime};base64,{img_b64}"

    # Video editing: pass video URL directly
    if video_url:
        payload["video_url"] = video_url

    response = requests.post(
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

def poll_video_status(request_id: str) -> Dict[str, Any]:
    """Poll for video completion. Returns video result when done."""
    poll_url = f"https://api.x.ai/v1/videos/{request_id}"
    start = time.time()

    while time.time() - start < VIDEO_POLL_TIMEOUT:
        response = requests.get(
            poll_url,
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=60,
        )

        if response.status_code != 200:
            raise RuntimeError(f"Video poll failed (HTTP {response.status_code}): {response.text}")

        result = response.json()
        status = result.get("status", "")

        if status == "done":
            return result
        elif status == "expired":
            raise RuntimeError("Video generation request expired before completion.")
        elif status == "pending":
            if logger:
                elapsed = int(time.time() - start)
                logger.info(f"Video generation pending... ({elapsed}s elapsed)")
            time.sleep(VIDEO_POLL_INTERVAL)
        else:
            raise RuntimeError(f"Unexpected video status: {status}")

    raise RuntimeError(f"Video generation timed out after {VIDEO_POLL_TIMEOUT}s")

def download_video(url: str, save_path: str) -> str:
    """Download a video from a temporary URL and save to disk. Returns absolute path."""
    abs_path = os.path.abspath(save_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    response = requests.get(url, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(f"Video download failed (HTTP {response.status_code})")

    with open(abs_path, "wb") as f:
        f.write(response.content)
    return abs_path

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
                            "enum": ["grok-2-image-1212", "grok-imagine-image", "grok-imagine-image-pro"],
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
                            "enum": ["grok-imagine-image", "grok-imagine-image-pro"],
                            "default": "grok-imagine-image"
                        },
                        "save_path": {
                            "type": "string",
                            "description": "File path to save the edited image. If not provided, auto-saves to output directory."
                        }
                    },
                    "required": ["prompt", "image_path"]
                }
            },
            {
                "name": "generate_video",
                "description": "Generate videos using Grok's Imagine video model. Supports text-to-video, image-to-video, and video editing. Video generation is async and may take 1-5 minutes. Trigger: 'grok generate video', 'grok video', or 'grok create video'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Description of the video to generate or editing instructions",
                            "maxLength": MAX_PROMPT_LENGTH
                        },
                        "duration": {
                            "type": "integer",
                            "description": "Video duration in seconds (1-15). Not applicable for video editing.",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 15
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "description": "Aspect ratio (default: 16:9). Not applicable for video editing.",
                            "enum": ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"],
                            "default": "16:9"
                        },
                        "resolution": {
                            "type": "string",
                            "description": "Video resolution (default: 480p). Not applicable for video editing.",
                            "enum": ["480p", "720p"],
                            "default": "480p"
                        },
                        "image_path": {
                            "type": "string",
                            "description": "Absolute path to a source image for image-to-video mode. The image will be animated based on the prompt."
                        },
                        "video_url": {
                            "type": "string",
                            "description": "URL of a source video for video editing mode. Max 8.7 seconds input."
                        },
                        "save_path": {
                            "type": "string",
                            "description": "File path to save the video. If not provided, auto-saves to output directory."
                        }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "analyze_image",
                "description": "Analyze an image using Grok's vision capabilities. Uses your configured default model (supports vision in grok-4+ models). Trigger: 'grok analyze image', 'grok describe image', or 'grok vision'.",
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
                            "description": "Vision model to use. Defaults to your configured model. grok-2-vision-1212 for legacy, grok-4+ models support vision natively.",
                            "enum": ["grok-2-vision-1212", "grok-4-1-fast-reasoning", "grok-4-1-fast-non-reasoning", "grok-4", "grok-4-0709"]
                        }
                    },
                    "required": ["image_path"]
                }
            }
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

                tool_kwargs = {}
                if allowed:
                    tool_kwargs["allowed_domains"] = allowed[:5]
                if excluded:
                    tool_kwargs["excluded_domains"] = excluded[:5]

                tools = [build_tool_spec("web_search", **tool_kwargs)]
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

                    abs_path = save_image(img["b64_json"], path)

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
                if not os.path.isfile(image_path):
                    raise ValueError(f"File not found: {image_path}")

                model = arguments.get("model", "grok-imagine-image")
                save_path = arguments.get("save_path")

                with open(image_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("utf-8")
                mime_type = get_mime_type(image_path)

                edited = call_grok_image_edit(prompt, image_base64, mime_type, model)

                if not save_path:
                    save_path = get_auto_save_path()
                abs_path = save_image(edited["b64_json"], save_path)

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

                # Image-to-video mode
                image_path = arguments.get("image_path")
                if image_path:
                    if not os.path.isfile(image_path):
                        raise ValueError(f"Image file not found: {image_path}")

                # Video editing mode
                video_url = arguments.get("video_url")

                # Submit generation request
                vid_request_id = call_grok_video_gen(
                    prompt, duration, aspect_ratio, resolution, image_path, video_url
                )
                logger.info(f"Video generation submitted: {vid_request_id}")

                # Poll for completion
                video_result = poll_video_status(vid_request_id)

                # Download and save
                video_data = video_result.get("video", {})
                video_url_result = video_data.get("url")
                if not video_url_result:
                    raise RuntimeError(f"Video result missing URL: {video_result}")

                if not save_path:
                    save_path = get_video_save_path()
                abs_path = download_video(video_url_result, save_path)

                video_duration = video_data.get("duration", "unknown")
                mode = "text-to-video"
                if image_path:
                    mode = "image-to-video"
                elif arguments.get("video_url"):
                    mode = "video-edit"

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

        elif tool_name == "analyze_image":
            if not GROK_AVAILABLE:
                result = f"Grok not available: {GROK_ERROR}"
            else:
                image_path = arguments.get("image_path", "")
                if not image_path.strip():
                    raise ValueError("image_path cannot be empty")
                if not os.path.isfile(image_path):
                    raise ValueError(f"File not found: {image_path}")

                prompt = arguments.get("prompt", "Describe this image in detail")
                prompt = truncate_input(prompt, MAX_PROMPT_LENGTH, "prompt")
                model = arguments.get("model")

                with open(image_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("utf-8")
                mime_type = get_mime_type(image_path)

                result = call_grok_vision(image_base64, mime_type, prompt, model)

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
    except Exception as e:
        logger.error(f"Tool call error for {tool_name}: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": str(e)
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
    logger.info(f"Grok available: {GROK_AVAILABLE}")
    if not GROK_AVAILABLE:
        logger.warning(f"Grok initialization failed: {GROK_ERROR}")

    while not shutdown_requested:
        try:
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

            send_response(response)

        except EOFError:
            logger.info("EOF received, shutting down")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            if 'request_id' in locals() and request_id is not None:
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
  python server.py config --model grok-4-1-fast-reasoning  Set default model
  python server.py config --show                         Show current config
  python server.py config --list-models                  List available models
        """
    )
    subparsers = parser.add_subparsers(dest="command")

    # Config subcommand
    config_parser = subparsers.add_parser("config", help="Configure the Grok MCP server")
    config_parser.add_argument("--model", "-m", help="Set the default Grok model")
    config_parser.add_argument("--show", "-s", action="store_true", help="Show current configuration")
    config_parser.add_argument("--list-models", "-l", action="store_true", help="List available models")

    args = parser.parse_args()

    if args.command == "config":
        sys.exit(handle_config_command(args))
    else:
        # No subcommand = run as MCP server
        run_server()
