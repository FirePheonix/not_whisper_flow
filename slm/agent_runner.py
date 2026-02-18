"""
AgentRunner - the thinking layer between voice and tools.

Priority chain (ClawBot-inspired):
  1. Ollama  (7-8B, native function calling)   ← best understanding
  2. HuggingFace SLM (0.5-1.5B, JSON prompt)  ← fallback when Ollama not running
  3. Regex CommandRouter (zero-latency)        ← always-on safety net

Every interaction is appended to ~/.whisper_flow/session.jsonl (memory).
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from utils.logger import setup_logger
from slm.command_router import CommandRouter

logger = setup_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────────────────────

@dataclass
class ToolCall:
    """A single tool invocation."""
    tool: str
    args: Dict[str, Any] = field(default_factory=dict)

    def __str__(self):
        return f"{self.tool}({self.args})"


@dataclass
class AgentResult:
    """Parsed intent: an ordered list of tool calls to run serially."""
    calls:    List[ToolCall] = field(default_factory=list)
    raw_text: str  = ""
    backend:  str  = "regex"   # "ollama" | "slm" | "regex"


# ──────────────────────────────────────────────────────────────
# HuggingFace SLM helpers (JSON prompting)
# ──────────────────────────────────────────────────────────────

_TOOL_SYSTEM = """\
You are a voice command parser for a local desktop assistant.
Read the user's voice input and output ONLY a JSON object — no explanation, no chat.

Available tools:
  open_app(app)          – open an application (chrome, firefox, spotify, discord, vscode, notepad, calculator, etc.)
  close_app(app)         – close/quit an application
  search_web(query)      – Google search for a query
  media_control(action)  – play pause stop next previous volume_up volume_down mute
  type_text(text)        – type text at the current cursor position
  enhance_prompt(text)   – polish a rough coding idea into an AI-ready prompt
  save_note(text)        – save a spoken note or reminder

Output format — always valid JSON:
{"calls": [{"tool": "<tool_name>", "args": {<args>}}]}

Examples:
Input: "open chrome"
Output: {"calls": [{"tool": "open_app", "args": {"app": "chrome"}}]}

Input: "open chrome and search youtube"
Output: {"calls": [{"tool": "open_app", "args": {"app": "chrome"}}, {"tool": "search_web", "args": {"query": "youtube"}}]}

Input: "next track"
Output: {"calls": [{"tool": "media_control", "args": {"action": "next"}}]}

Input: "write a react hook that fetches user data"
Output: {"calls": [{"tool": "enhance_prompt", "args": {"text": "write a react hook that fetches user data"}}]}

Input: "note: remember to push the PR before 5pm"
Output: {"calls": [{"tool": "save_note", "args": {"text": "remember to push the PR before 5pm"}}]}
"""


def _extract_calls(raw: str) -> Optional[List[ToolCall]]:
    """Parse raw SLM text output into ToolCalls. Returns None on failure."""
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group())
        entries = data.get("calls", [])
        if not entries:
            return None
        calls = []
        for c in entries:
            tool = str(c.get("tool", "")).strip()
            args = c.get("args", {})
            if tool:
                calls.append(ToolCall(tool=tool, args=args if isinstance(args, dict) else {}))
        return calls if calls else None
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────
# AgentRunner
# ──────────────────────────────────────────────────────────────

class AgentRunner:
    """
    Converts voice text to an ordered list of ToolCalls.

    ┌──────────────────────────────────────────────┐
    │  voice text                                  │
    │    │                                        │
    │    ▼                                        │
    │  Ollama (7-8B, native tool calling)         │
    │    │  not running / model missing           │
    │    ▼                                        │
    │  HuggingFace SLM (0.5-1.5B, JSON prompt)   │
    │    │  not loaded / malformed output         │
    │    ▼                                        │
    │  Regex CommandRouter (instant, always works)│
    │    │                                        │
    │    ▼  executed serially in main.py          │
    │  Commander / PromptEnhancer / NotesStore    │
    └──────────────────────────────────────────────┘
    """

    _MAX_HISTORY = 10

    def __init__(self, slm=None, ollama=None, session_dir: Path = None):
        """
        Args:
            slm:    SLMModelManager (HuggingFace — secondary backend)
            ollama: OllamaClient (primary backend — 7-8B, best quality)
            session_dir: where to persist session.jsonl
        """
        self._ollama = ollama
        self._slm    = slm
        self._regex  = CommandRouter()

        session_dir = session_dir or (Path.home() / ".whisper_flow")
        session_dir.mkdir(parents=True, exist_ok=True)
        self._session_path = session_dir / "session.jsonl"
        self._history: List[Dict] = []
        self._load_session()

        logger.info(
            f"AgentRunner ready  "
            f"ollama={'yes' if ollama else 'no'}  "
            f"slm={'yes' if slm else 'no'}"
        )

    # ── Session memory ────────────────────────────────────────

    def _load_session(self):
        if not self._session_path.exists():
            return
        try:
            lines = self._session_path.read_text(encoding="utf-8").splitlines()
            entries = [json.loads(ln) for ln in lines if ln.strip()]
            self._history = entries[-self._MAX_HISTORY:]
            logger.info(f"Session: {len(self._history)} recent entries loaded")
        except Exception as e:
            logger.warning(f"Session load failed: {e}")

    def _save(self, user_text: str, calls: List[ToolCall], backend: str):
        entry = {
            "ts":      datetime.now().isoformat(),
            "user":    user_text,
            "backend": backend,
            "calls":   [{"tool": tc.tool, "args": tc.args} for tc in calls],
        }
        try:
            with open(self._session_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            self._history.append(entry)
            if len(self._history) > self._MAX_HISTORY:
                self._history = self._history[-self._MAX_HISTORY:]
        except Exception as e:
            logger.warning(f"Session save failed: {e}")

    # ── Main entry point ──────────────────────────────────────

    def parse(self, text: str, mode: str = "code_prompt") -> AgentResult:
        """
        Convert voice input to an ordered list of ToolCalls.

        Args:
            text: Raw Whisper transcription
            mode: "code_prompt" | "voice_notes"  (used by regex fallback)
        """
        if not text or not text.strip():
            return AgentResult(raw_text=text or "")

        # 1. Ollama (primary — 7-8B, native tool calling)
        if self._ollama is not None:
            try:
                calls = self._ollama.parse_tools(text)
                if calls:
                    logger.info(f"Agent[ollama]→ {[str(c) for c in calls]}")
                    self._save(text, calls, "ollama")
                    return AgentResult(calls=calls, raw_text=text, backend="ollama")
            except Exception as e:
                logger.warning(f"Ollama error: {e}")

        # 2. HuggingFace SLM (secondary — only if already loaded)
        if self._slm is not None and self._slm.model is not None:
            try:
                calls = self._slm_parse(text)
                if calls:
                    logger.info(f"Agent[slm]→ {[str(c) for c in calls]}")
                    self._save(text, calls, "slm")
                    return AgentResult(calls=calls, raw_text=text, backend="slm")
            except Exception as e:
                logger.warning(f"SLM error: {e}")

        # 3. Regex fallback (instant, always works)
        calls = self._regex_parse(text, mode)
        logger.info(f"Agent[regex]→ {[str(c) for c in calls]}")
        self._save(text, calls, "regex")
        return AgentResult(calls=calls, raw_text=text, backend="regex")

    def _slm_parse(self, text: str) -> Optional[List[ToolCall]]:
        messages = [
            {"role": "system", "content": _TOOL_SYSTEM},
            {"role": "user",   "content": f"Input: \"{text}\"\nOutput:"},
        ]
        raw = self._slm.chat(messages, max_new_tokens=150, temperature=0.1)
        logger.debug(f"SLM raw: {raw!r}")
        return _extract_calls(raw)

    def _regex_parse(self, text: str, mode: str) -> List[ToolCall]:
        route = self._regex.route(text, mode=mode)
        if route.route == "command":
            a, t = route.action, route.target
            if a in ("open_app", "close_app"):
                args = {"app": t}
            elif a == "search_web":
                args = {"query": t}
            elif a == "media_control":
                args = {"action": t}
            elif a == "type_text":
                args = {"text": t}
            else:
                args = {"target": t}
            return [ToolCall(tool=a, args=args)]
        elif route.route == "note":
            return [ToolCall(tool="save_note", args={"text": text})]
        else:
            return [ToolCall(tool="enhance_prompt", args={"text": text})]
