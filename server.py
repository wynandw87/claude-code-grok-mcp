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
import json
import sys
import os
import signal
import logging
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# Server version
__version__ = "1.3.0"

# xAI API endpoint
XAI_API_URL = "https://api.x.ai/v1/chat/completions"

# Available Grok models (from xAI API)
AVAILABLE_MODELS = {
    "grok-4-1-fast-reasoning": "Grok 4.1 Fast with reasoning (2M context) - Default",
    "grok-4-1-fast-non-reasoning": "Grok 4.1 Fast without reasoning (2M context)",
    "grok-4-fast-reasoning": "Grok 4 Fast with reasoning",
    "grok-4-fast-non-reasoning": "Grok 4 Fast without reasoning",
    "grok-4-0709": "Grok 4 (July 2025 release)",
    "grok-3": "Grok 3 - Previous flagship (128K context)",
    "grok-3-mini": "Grok 3 Mini - Lighter/cheaper option (128K context)",
    "grok-2-1212": "Grok 2 (128K context)",
    "grok-2-vision-1212": "Grok 2 Vision (32K context)",
    "grok-code-fast-1": "Grok Code Fast - Optimized for coding",
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

def call_grok(prompt: str, system_prompt: Optional[str] = None) -> str:
    """Call Grok API directly via HTTP and return response"""
    try:
        # Build messages array
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request payload
        payload = {
            "model": DEFAULT_MODEL,
            "messages": messages,
            "stream": False,
            "temperature": 0.7
        }

        # Make request using requests library
        response = requests.post(
            XAI_API_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}"
            },
            timeout=120
        )

        # Check for errors
        if response.status_code != 200:
            logger.error(f"HTTP error calling Grok: {response.status_code} - {response.text}")
            return f"Error calling Grok (HTTP {response.status_code}): {response.text}"

        result = response.json()

        # Extract response content
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        else:
            return f"Unexpected response format: {result}"

    except requests.exceptions.Timeout:
        logger.error("Timeout calling Grok")
        return "Error calling Grok: Request timed out"
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error calling Grok: {e}")
        return f"Error calling Grok: {str(e)}"
    except Exception as e:
        logger.error(f"Error calling Grok: {e}")
        return f"Error calling Grok: {str(e)}"

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
                result = call_grok(prompt)

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
                result = call_grok(prompt, "You are an expert code reviewer.")

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
                result = call_grok(prompt, "You are a creative problem solver and brainstorming partner.")

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

def main():
    """Main server loop"""
    global shutdown_requested

    logger.info(f"Starting Grok MCP server v{__version__}")
    logger.info(f"Using direct HTTP API (no SDK)")
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
                # Return empty resources list
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"resources": []}
                }
            elif method == "prompts/list":
                # Return empty prompts list
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
