"""
ContextCapture — snapshot the desktop context before the overlay appears.

Captures:
  - Which app is currently focused (process name)
  - The window title (document name, page title, tab title, etc.)
  - Any text currently selected in that window (via clipboard sniff)

Call capture() BEFORE showing the overlay so the foreground window hasn't
changed yet.  The returned AppContext is passed to Ollama so it can respond
smartly to commands like "summarize this", "explain this code", "open this".
"""

import ctypes
import os
import time
from dataclasses import dataclass
from typing import Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class AppContext:
    """Snapshot of what's currently active on the desktop."""
    app_name:      str = ""   # e.g. "chrome", "code", "notepad"
    window_title:  str = ""   # e.g. "Article Title - Google Chrome"
    selected_text: str = ""   # whatever text was highlighted when triggered

    def is_empty(self) -> bool:
        return not self.window_title and not self.selected_text

    def to_prompt_prefix(self) -> str:
        """
        Format as a compact context block to prepend to the Ollama user message.
        Empty fields are omitted.
        """
        parts = []
        if self.app_name:
            parts.append(f"Active app: {self.app_name}")
        if self.window_title:
            parts.append(f"Window: {self.window_title}")
        if self.selected_text:
            preview = self.selected_text[:600]
            if len(self.selected_text) > 600:
                preview += "…"
            parts.append(f'Selected text:\n"""\n{preview}\n"""')
        if not parts:
            return ""
        return "[Desktop context]\n" + "\n".join(parts)


class ContextCapture:
    """
    Captures foreground window info and selected text.

    Usage:
        ctx = capture.capture()   # call BEFORE showing the overlay
        agent.parse(text, context=ctx)
    """

    def capture(self) -> AppContext:
        ctx = AppContext()

        # 1. Foreground window — app name + title
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            ctx.window_title = self._get_window_title(hwnd)
            ctx.app_name = self._get_process_name(hwnd)
        except Exception as e:
            logger.debug(f"Window info failed: {e}")

        # 2. Selected text — clipboard sniff (non-destructive)
        try:
            ctx.selected_text = self._sniff_selection()
        except Exception as e:
            logger.debug(f"Selection sniff failed: {e}")

        if not ctx.is_empty():
            logger.info(
                f"Context: [{ctx.app_name}] '{ctx.window_title[:60]}'"
                + (f" +{len(ctx.selected_text)}ch selected" if ctx.selected_text else "")
            )

        return ctx

    # ── Window helpers ────────────────────────────────────────────────────────

    def _get_window_title(self, hwnd: int) -> str:
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value

    def _get_process_name(self, hwnd: int) -> str:
        try:
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_VM_READ           = 0x0010
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value
            )
            if not handle:
                return ""
            buf = ctypes.create_unicode_buffer(1024)
            ctypes.windll.psapi.GetModuleFileNameExW(handle, None, buf, 1024)
            ctypes.windll.kernel32.CloseHandle(handle)
            return os.path.splitext(os.path.basename(buf.value))[0].lower()
        except Exception:
            return ""

    # ── Selected-text helpers ─────────────────────────────────────────────────

    def _sniff_selection(self) -> str:
        """
        Non-destructively check if any text is selected by temporarily
        simulating Ctrl+C and reading the clipboard.

        Restores the previous clipboard content afterwards.
        """
        import pyperclip
        import keyboard

        # Save current clipboard
        try:
            old_clip = pyperclip.paste()
        except Exception:
            old_clip = ""

        # Clear clipboard so we can detect if Ctrl+C changed it
        try:
            pyperclip.copy("\x00")   # sentinel — unlikely to be real content
        except Exception:
            return ""

        # Ask the active window to copy its selection
        try:
            keyboard.send("ctrl+c")
            time.sleep(0.12)
        except Exception:
            _restore_clipboard(old_clip)
            return ""

        # Read result
        try:
            new_clip = pyperclip.paste()
        except Exception:
            new_clip = ""

        # Restore original
        _restore_clipboard(old_clip)

        # Return only if something new was actually copied
        if new_clip and new_clip != "\x00" and new_clip != old_clip:
            result = new_clip.strip()
            if result:
                return result
        return ""


def _restore_clipboard(text: str):
    try:
        import pyperclip
        pyperclip.copy(text)
    except Exception:
        pass
