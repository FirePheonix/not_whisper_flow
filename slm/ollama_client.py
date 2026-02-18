"""
Ollama-based LLM client with native function/tool calling.

Ollama runs locally — no API key, no internet, free forever.
Recommended models (pick one):
  ollama pull qwen2.5:7b       ← best tool calling, fast
  ollama pull llama3.1:8b      ← solid all-around
  ollama pull llama3.2:3b      ← lighter, still good

Install Ollama: https://ollama.com
"""

import base64
import io
import json
import requests
from typing import List, Optional
from utils.logger import setup_logger
from .agent_runner import ToolCall

logger = setup_logger(__name__)

DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_URL   = "http://localhost:11434"

# ──────────────────────────────────────────────────────────────
# Tool schema (Ollama / OpenAI function-calling format)
# ──────────────────────────────────────────────────────────────

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application on the Windows computer",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "App name e.g. chrome, firefox, spotify, discord, vscode, notepad, calculator, explorer, settings, teams, zoom, slack, steam"
                    }
                },
                "required": ["app"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_app",
            "description": "Close or quit an application",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {"type": "string", "description": "Application name to close"}
                },
                "required": ["app"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web using Google",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query terms"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "media_control",
            "description": "Control media playback",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["play", "pause", "stop", "next", "previous", "volume_up", "volume_down", "mute", "unmute"],
                        "description": "Media action to perform"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text at the current cursor position. Use send_enter=true for terminal/shell commands that need to be executed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                    "send_enter": {"type": "boolean", "description": "Press Enter after typing — set true for terminal commands (pip, git, python, etc.)"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "enhance_prompt",
            "description": "Polish a rough coding idea or programming request into a well-structured AI prompt",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The raw coding idea or request to polish"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Save a spoken note, reminder, or thought",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The note content to save"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot_and_describe",
            "description": "Capture the current screen and analyze it visually. Use ONLY when no selected text is available and the user needs visual analysis of on-screen content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to ask or analyze about the screen content"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "respond",
            "description": "Give a direct text response to the user — use for summarization, explanation, answering questions, or any request where the answer is text (especially when selected text or window context is provided).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Your response to show the user"}
                },
                "required": ["text"]
            }
        }
    },
]

_SYSTEM = """\
You are a voice command assistant for a Windows desktop app. \
The user speaks commands — call the appropriate tool(s) to execute them.

Guidelines:
- For app/system commands: use open_app, close_app, search_web, media_control, type_text
- For coding/programming requests: use enhance_prompt
- For notes, reminders, thoughts: use save_note
- Compound commands call multiple tools (e.g. "open chrome and search youtube" → open_app + search_web)
- Ignore filler words: hey, so, hello, please, can you, could you, etc.
- When typing a terminal/shell command (pip, python, git, cd, ls, etc.), set send_enter=true so it executes
- When the user says "type X and run it" or "execute X" in a terminal, use send_enter=true
- If [Desktop context] is provided and has "Selected text": use respond to answer questions/summaries using that text — do NOT use screenshot_and_describe
- If [Desktop context] is provided without selected text and user asks about visible content: use screenshot_and_describe
- Use respond for any direct answer, summary, or explanation\
"""


# ──────────────────────────────────────────────────────────────
# Client
# ──────────────────────────────────────────────────────────────

class OllamaClient:
    """
    Calls a local Ollama server for native function/tool-call inference.

    Availability is cached — checks once on first use, resets after timeout
    so subsequent requests retry when Ollama comes back online.
    """

    def __init__(self, model: str = DEFAULT_MODEL, base_url: str = DEFAULT_URL):
        self.model   = model
        self.base_url = base_url.rstrip("/")
        self._available: Optional[bool] = None
        logger.info(f"OllamaClient: model={model}  url={base_url}")

    # ── Availability ──────────────────────────────────────────

    def is_available(self) -> bool:
        """Check (and cache) whether the Ollama server is reachable."""
        if self._available is not None:
            return self._available
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=2)
            self._available = (r.status_code == 200)
        except Exception:
            self._available = False

        if not self._available:
            logger.warning(
                "Ollama not reachable. "
                "Install from https://ollama.com then run: ollama pull qwen2.5:7b"
            )
        else:
            models = self._list_models()
            if models:
                logger.info(f"Ollama available. Local models: {models}")
            else:
                logger.info("Ollama available (no models yet — run: ollama pull qwen2.5:7b)")
        return self._available

    def _list_models(self) -> List[str]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    # ── Tool parsing ──────────────────────────────────────────

    def parse_tools(self, text: str, context=None) -> Optional[List[ToolCall]]:
        """
        Ask Ollama to parse voice input into tool calls using native function calling.

        Args:
            text:    Raw Whisper transcription
            context: Optional AppContext — injected as a prefix so Ollama knows
                     which app is open, the window title, and any selected text.

        Returns a list of ToolCall objects, or None if Ollama is unavailable / fails.
        """
        if not self.is_available():
            return None

        # Build user message: prepend desktop context when available
        user_message = text
        if context is not None:
            prefix = context.to_prompt_prefix()
            if prefix:
                user_message = f"{prefix}\n\nUser command: {text}"

        try:
            payload = {
                "model":   self.model,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user",   "content": user_message},
                ],
                "tools":   _TOOLS,
                "stream":  False,
                "options": {"temperature": 0.0, "num_predict": 256},
            }
            r = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            msg  = data.get("message", {})
            raw_calls = msg.get("tool_calls", [])

            if not raw_calls:
                logger.debug(f"Ollama returned no tool_calls. content={msg.get('content','')!r}")
                return None

            calls = []
            for tc in raw_calls:
                fn   = tc.get("function", {})
                name = fn.get("name", "").strip()
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                if name:
                    calls.append(ToolCall(tool=name, args=args))

            logger.info(f"Ollama→ {len(calls)} call(s): {[c.tool for c in calls]}")
            return calls if calls else None

        except requests.Timeout:
            logger.warning("Ollama request timed out")
            self._available = None  # retry next time
            return None
        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "?"
            if status == 404:
                logger.warning(
                    f"Ollama model '{self.model}' not found — run: ollama pull {self.model}"
                )
            else:
                logger.warning(f"Ollama HTTP error {status}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Ollama call failed: {e}")
            return None

    # ── Vision ────────────────────────────────────────────────

    def vision_query(self, prompt: str, image, model: str = None) -> Optional[str]:
        """
        Send a screenshot + text prompt to an Ollama vision model.

        Args:
            prompt:  What to ask about the image (e.g. "Summarize this page")
            image:   PIL.Image.Image object (grabbed screenshot)
            model:   Vision model name; defaults to "llava:7b"

        Returns:
            Model response string, or None on failure.
        """
        if not self.is_available():
            return None

        vision_model = model or "llava:7b"

        try:
            # Encode PIL image → base64 PNG
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            payload = {
                "model": vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [img_b64],
                    }
                ],
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 512},
            }
            r = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60,
            )
            r.raise_for_status()
            content = r.json().get("message", {}).get("content", "").strip()
            logger.info(f"Vision response ({len(content)} chars)")
            return content or None

        except requests.Timeout:
            logger.warning("Vision query timed out")
            return None
        except requests.HTTPError as e:
            status = e.response.status_code if e.response else "?"
            if status == 404:
                logger.warning(
                    f"Vision model '{vision_model}' not found — run: ollama pull {vision_model}"
                )
            else:
                logger.warning(f"Vision HTTP error {status}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Vision query failed: {e}")
            return None

    # ── Text query (no vision, no tools) ──────────────────────

    def text_query(self, prompt: str, context_text: str) -> Optional[str]:
        """
        Ask the main Ollama model a plain text question about provided text.
        No tool calling — just returns the model's answer.

        Used when selected text is available so vision is not needed.
        """
        if not self.is_available():
            return None
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Answer concisely and clearly.",
                    },
                    {
                        "role": "user",
                        "content": f"{prompt}\n\nText:\n\"\"\"\n{context_text}\n\"\"\"",
                    },
                ],
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 512},
            }
            r = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60,
            )
            r.raise_for_status()
            content = r.json().get("message", {}).get("content", "").strip()
            logger.info(f"Text query response ({len(content)} chars)")
            return content or None
        except requests.Timeout:
            logger.warning("Text query timed out")
            return None
        except Exception as e:
            logger.warning(f"Text query failed: {e}")
            return None
