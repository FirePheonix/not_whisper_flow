"""
Command Router - decides what to do with a voice transcription.

Routes incoming text to one of three paths:
  - "command"  → system action (open app, web search, media control, etc.)
  - "enhance"  → code prompt enhancement
  - "note"     → voice note cleanup & save

Uses fast regex pattern matching - no SLM needed, zero latency.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Words that stop an app/search target when followed by another command verb
_COMMAND_VERBS = (
    "open", "close", "quit", "exit", "kill", "launch", "start", "run",
    "search", "find", "google", "look", "browse",
    "play", "pause", "stop", "next", "skip", "previous",
    "type", "write", "dictate",
)
_COMPOUND_SPLIT = re.compile(
    r'\s+and\s+(?:then\s+)?(?:' + '|'.join(_COMMAND_VERBS) + r')\b',
    re.IGNORECASE,
)

# Preamble phrases spoken before the actual command.
# Uses + quantifier to strip multiple layers, e.g. "Hello, can you open..."
_PREAMBLE = re.compile(
    r'^(?:'
    r'(?:hello|hey|hi|ok|okay|alright)[,!.]?\s+'   # greetings (comma-tolerant)
    r'|'
    r'(?:so|please|can you|could you|would you|will you|'
    r"i(?:'d| would) like(?: you)? to|"
    r'i (?:want|need)(?: you)? to|'
    r'can you please|could you please|'
    r'go ahead and'
    r')\s+'
    r')+',
    re.IGNORECASE,
)


@dataclass
class RouteResult:
    """Result of routing a voice transcription."""
    route: str              # "command" | "enhance" | "note"
    action: str = ""        # command type: "open_app" | "search_web" | "media_control" | "type_text" | "close_app"
    target: str = ""        # app name, search query, text to type, etc.
    raw_text: str = ""      # original transcription
    confidence: float = 1.0


class CommandRouter:
    """
    Fast, zero-latency router for voice transcriptions.

    Decides whether voice input is a system command (open app, search web,
    media control) or should be passed through to prompt enhancement / note saving.
    All routing is regex-based - no model inference needed.
    """

    # --- Open / Launch patterns ---
    _OPEN = [
        r"^open\s+(.+)$",
        r"^launch\s+(.+)$",
        r"^start\s+(.+)$",
        r"^run\s+(.+)$",
        r"^open up\s+(.+)$",
        r"^boot up\s+(.+)$",
    ]

    # --- Close / Quit patterns ---
    _CLOSE = [
        r"^close\s+(.+)$",
        r"^quit\s+(.+)$",
        r"^exit\s+(.+)$",
        r"^kill\s+(.+)$",
        r"^close\s+(?:the\s+)?(.+)$",
    ]

    # --- Web search patterns ---
    _SEARCH = [
        r"^search\s+for\s+(.+)$",
        r"^search\s+(.+)$",
        r"^google\s+(.+)$",
        r"^look\s+up\s+(.+)$",
        r"^find\s+(.+)\s+online$",
        r"^find\s+(.+)$",
        r"^(?:search|look)\s+(.+)\s+on\s+(?:google|the web|youtube|bing)$",
        r"^browse\s+to\s+(.+)$",
    ]

    # --- Media control patterns ---
    _MEDIA = {
        "play":        [r"^play$", r"^play\s+music$", r"^resume$", r"^resume\s+music$", r"^play\s+(.+)$"],
        "pause":       [r"^pause$", r"^pause\s+music$", r"^pause\s+playback$"],
        "stop":        [r"^stop$", r"^stop\s+music$", r"^stop\s+playing$"],
        "next":        [r"^next$", r"^next\s+(?:song|track)$", r"^skip$", r"^skip\s+(?:song|track)$"],
        "previous":    [r"^previous$", r"^previous\s+(?:song|track)$", r"^go\s+back$", r"^last\s+(?:song|track)$"],
        "volume_up":   [r"^volume\s+up$", r"^louder$", r"^increase\s+volume$", r"^turn\s+(?:it\s+)?up$"],
        "volume_down": [r"^volume\s+down$", r"^quieter$", r"^decrease\s+volume$", r"^turn\s+(?:it\s+)?down$"],
        "mute":        [r"^mute$", r"^silence$"],
        "unmute":      [r"^unmute$"],
    }

    # --- Type / dictate patterns ---
    _TYPE = [
        r"^type\s+(.+)$",
        r"^type\s+this[:\s]+(.+)$",
        r"^dictate[:\s]+(.+)$",
        r"^write\s+(.+)$",
    ]

    def route(self, text: str, mode: str = "code_prompt") -> RouteResult:
        """
        Route transcribed text to the appropriate handler.

        Args:
            text: Raw transcription from Whisper
            mode: Current app mode ("code_prompt" | "voice_notes")

        Returns:
            RouteResult describing what to do with the text
        """
        if not text or not text.strip():
            default_route = "enhance" if mode == "code_prompt" else "note"
            return RouteResult(route=default_route, raw_text=text or "")

        # Normalize: lowercase, trim, strip trailing punctuation
        clean = text.strip()
        clean_lower = re.sub(r'[.!?]+$', '', clean.lower()).strip()

        # Strip preamble phrases ("so open chrome" → "open chrome")
        clean_lower = _PREAMBLE.sub('', clean_lower).strip()
        # Re-strip trailing punctuation after preamble removal
        clean_lower = re.sub(r'[.!?]+$', '', clean_lower).strip()

        # --- Open app ---
        for pattern in self._OPEN:
            m = re.match(pattern, clean_lower, re.IGNORECASE)
            if m:
                target = m.group(1).strip()
                target = self._trim_compound(target)
                target = self._clean_app_name(target)
                logger.info(f"Router: open_app '{target}'")
                return RouteResult(route="command", action="open_app", target=target, raw_text=clean)

        # --- Close app ---
        for pattern in self._CLOSE:
            m = re.match(pattern, clean_lower, re.IGNORECASE)
            if m:
                target = m.group(1).strip()
                target = self._trim_compound(target)
                target = self._clean_app_name(target)
                logger.info(f"Router: close_app '{target}'")
                return RouteResult(route="command", action="close_app", target=target, raw_text=clean)

        # --- Search web ---
        for pattern in self._SEARCH:
            m = re.match(pattern, clean_lower, re.IGNORECASE)
            if m:
                target = m.group(1).strip()
                target = self._trim_compound(target)
                logger.info(f"Router: search_web '{target}'")
                return RouteResult(route="command", action="search_web", target=target, raw_text=clean)

        # --- Media control ---
        for action, patterns in self._MEDIA.items():
            for pattern in patterns:
                m = re.match(pattern, clean_lower, re.IGNORECASE)
                if m:
                    # For "play X" the target is the song/playlist name
                    target = m.group(1).strip() if m.lastindex else action
                    logger.info(f"Router: media_control '{action}' target='{target}'")
                    return RouteResult(route="command", action="media_control", target=action, raw_text=clean)

        # --- Type / dictate ---
        for pattern in self._TYPE:
            m = re.match(pattern, clean_lower, re.IGNORECASE)
            if m:
                # Use original case for the text to type
                # Find where the target starts in original text
                target_start = m.start(1)
                target_orig = clean[target_start:] if target_start < len(clean) else m.group(1)
                logger.info(f"Router: type_text '{target_orig[:40]}...'")
                return RouteResult(route="command", action="type_text", target=target_orig, raw_text=clean)

        # --- Fallback: route to mode ---
        if mode == "voice_notes":
            logger.debug(f"Router: note (mode=voice_notes)")
            return RouteResult(route="note", raw_text=clean)

        logger.debug(f"Router: enhance (mode=code_prompt)")
        return RouteResult(route="enhance", raw_text=clean)

    @staticmethod
    def _trim_compound(target: str) -> str:
        """
        Truncate target at the first ' and <command_verb>' boundary.
        e.g. "chrome and search youtube" → "chrome"
        """
        m = _COMPOUND_SPLIT.search(target)
        if m:
            return target[:m.start()].strip()
        return target

    @staticmethod
    def _clean_app_name(name: str) -> str:
        """Strip filler words from app name like 'the', 'app', 'application'."""
        name = re.sub(r'\s+(?:app|application|program|software)\s*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'^(?:the|my)\s+', '', name, flags=re.IGNORECASE)
        return name.strip()
