"""
Floating overlay — Lemon / Apple Intelligence style.

A borderless dark card that appears on top of the desktop when recording starts,
shows a live waveform while listening, a pulse animation while processing, and
the result inline before auto-dismissing.

States:  hidden → listening → processing → result → hidden
"""

import ctypes
import math
import random
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk
from utils.logger import setup_logger

logger = setup_logger(__name__)

# ── Palette (matches AppWindow) ────────────────────────────────────────────────
_BG        = "#0E0F0F"
_BORDER    = "#2A2A2A"
_TEXT      = "#E8DCC8"   # warm cream
_SUBTEXT   = "#8A8A8A"
_ACCENT    = "#1BB9CE"   # cyan
_RED       = "#B87878"   # muted recording red
_GREEN     = "#7DA888"   # success green
_CARD_W    = 680
_CARD_H    = 80          # collapsed (listening / processing)
_CARD_H_R  = 300         # expanded (result)

_AI_ICON   = "✦"         # star / spark — distinguishable AI marker


# ── DWM helpers (Windows 11 rounded corners + shadow) ─────────────────────────

def _apply_dwm_style(hwnd: int):
    """Enable rounded corners and drop shadow for a borderless window."""
    try:
        dwm = ctypes.windll.dwmapi
        # Rounded corners
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        dwm.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(ctypes.c_int(DWMWCP_ROUND)),
            ctypes.sizeof(ctypes.c_int),
        )
        # Re-enable NC rendering so the drop shadow shows
        DWMWA_NCRENDERING_POLICY = 2
        DWMNCRP_ENABLED = 2
        dwm.DwmSetWindowAttribute(
            hwnd,
            DWMWA_NCRENDERING_POLICY,
            ctypes.byref(ctypes.c_int(DWMNCRP_ENABLED)),
            ctypes.sizeof(ctypes.c_int),
        )
    except Exception as e:
        logger.debug(f"DWM style unavailable: {e}")


# ── FloatingOverlay ────────────────────────────────────────────────────────────

class FloatingOverlay(ctk.CTkToplevel):
    """
    Borderless, always-on-top floating card.

    Call show_listening() / show_processing() / show_result() from the main
    thread (or via self.after(0, ...)).  Background threads should use:
        overlay.after(0, lambda: overlay.show_listening())
    """

    def __init__(self, master):
        super().__init__(master)

        # ── Window chrome ──────────────────────────────────────
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.wm_attributes("-alpha", 0.0)   # start invisible; fade in
        self.configure(fg_color=_BG)

        # State
        self._state: str = "hidden"
        self._audio_capture = None
        self._dismiss_job = None
        self._waveform_job = None
        self._pulse_job = None
        self._fade_job = None
        self._pulse_phase: float = 0.0

        # Callback
        self.on_dismiss: Optional[Callable] = None

        # ── Build UI ───────────────────────────────────────────
        self._build()
        self.withdraw()   # hidden until show_listening()

        # Apply DWM after window is mapped
        self.after(50, self._apply_platform_style)

        logger.info("FloatingOverlay ready")

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        self.configure(fg_color=_BG)
        self.resizable(False, False)

        # Outer border frame
        self._border = ctk.CTkFrame(
            self, fg_color=_BORDER, corner_radius=18
        )
        self._border.pack(fill="both", expand=True, padx=0, pady=0)

        # Inner card frame (slightly inset)
        self._card = ctk.CTkFrame(
            self._border, fg_color=_BG, corner_radius=16
        )
        self._card.pack(fill="both", expand=True, padx=1, pady=1)

        # ── Top row: icon | status | waveform ─────────────────
        self._top_row = ctk.CTkFrame(self._card, fg_color="transparent")
        self._top_row.pack(fill="x", padx=20, pady=(18, 14))
        self._top_row.columnconfigure(1, weight=1)

        self._icon_lbl = ctk.CTkLabel(
            self._top_row,
            text=_AI_ICON,
            font=ctk.CTkFont(size=22),
            text_color=_ACCENT,
            width=30,
        )
        self._icon_lbl.grid(row=0, column=0, padx=(0, 14), sticky="w")

        self._status_lbl = ctk.CTkLabel(
            self._top_row,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=15),
            text_color=_TEXT,
            anchor="w",
        )
        self._status_lbl.grid(row=0, column=1, sticky="w")

        # Waveform canvas (5 bars)
        self._wave_canvas = tk.Canvas(
            self._top_row,
            width=44, height=36,
            bg=_BG, highlightthickness=0,
        )
        self._wave_canvas.grid(row=0, column=2, padx=(14, 0), sticky="e")
        self._bar_ids = []
        for i in range(5):
            x = 2 + i * 8
            bid = self._wave_canvas.create_rectangle(
                x, 15, x + 5, 21, fill=_ACCENT, outline=""
            )
            self._bar_ids.append(bid)

        # ── Result section (hidden by default) ────────────────
        self._result_frame = ctk.CTkFrame(self._card, fg_color="transparent")

        # Thin separator
        self._sep = tk.Canvas(
            self._result_frame, height=1, bg=_BORDER, highlightthickness=0
        )
        self._sep.pack(fill="x", padx=20, pady=(0, 12))

        # Transcription (small, muted)
        self._trans_lbl = ctk.CTkLabel(
            self._result_frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=_SUBTEXT,
            anchor="w",
            wraplength=_CARD_W - 60,
            justify="left",
        )
        self._trans_lbl.pack(anchor="w", padx=20, pady=(0, 8))

        # Result text (main body)
        self._result_box = ctk.CTkTextbox(
            self._result_frame,
            height=120,
            fg_color="#161717",
            border_color=_BORDER,
            border_width=1,
            corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=_TEXT,
            wrap="word",
        )
        self._result_box.pack(fill="x", padx=20, pady=(0, 10))
        self._result_box.configure(state="disabled")

        # Dismiss hint
        self._dismiss_lbl = ctk.CTkLabel(
            self._result_frame,
            text="Esc to dismiss",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_SUBTEXT,
        )
        self._dismiss_lbl.pack(anchor="e", padx=24, pady=(0, 12))

        # ── Keyboard dismiss ───────────────────────────────────
        self.bind("<Escape>", lambda _: self.dismiss())

    # ── Platform style ────────────────────────────────────────────────────────

    def _apply_platform_style(self):
        self.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            _apply_dwm_style(hwnd)
        except Exception:
            pass

    # ── Positioning ───────────────────────────────────────────────────────────

    def _position(self, h: int):
        sw = self.winfo_screenwidth()
        x = (sw - _CARD_W) // 2
        y = 70
        self.geometry(f"{_CARD_W}x{h}+{x}+{y}")

    # ── Audio source ──────────────────────────────────────────────────────────

    def set_audio_source(self, audio_capture):
        """Wire up AudioCapture so the waveform can read current_rms."""
        self._audio_capture = audio_capture

    # ── Public state transitions ──────────────────────────────────────────────

    def show_listening(self):
        """Show the overlay in listening / recording state."""
        self.after(0, self._do_show_listening)

    def show_processing(self):
        """Transition to processing state (sine-pulse bars)."""
        self.after(0, self._do_show_processing)

    def show_result(self, transcription: str, message: str, success: bool = True):
        """Expand the card to show transcription + result."""
        self.after(0, lambda: self._do_show_result(transcription, message, success))

    def dismiss(self):
        """Fade out and hide."""
        self.after(0, self._do_dismiss)

    # ── Internal state handlers ───────────────────────────────────────────────

    def _do_show_listening(self):
        self._cancel_jobs()
        self._state = "listening"
        self._result_frame.pack_forget()
        self._position(_CARD_H)

        self._icon_lbl.configure(text_color=_RED)
        self._status_lbl.configure(text="Listening...", text_color=_TEXT)
        self._set_bars_color(_RED)

        self.deiconify()
        self._fade_to(0.96)
        self._waveform_job = self.after(60, self._update_waveform)

    def _do_show_processing(self):
        self._cancel_jobs()
        self._state = "processing"
        self._result_frame.pack_forget()
        self._position(_CARD_H)

        self._icon_lbl.configure(text_color=_ACCENT)
        self._status_lbl.configure(text="Processing...", text_color=_SUBTEXT)
        self._set_bars_color(_ACCENT)
        self._pulse_phase = 0.0
        self._pulse_job = self.after(60, self._update_pulse)

    def _do_show_result(self, transcription: str, message: str, success: bool):
        self._cancel_jobs()
        self._state = "result"

        color = _GREEN if success else _RED
        self._icon_lbl.configure(text_color=color)
        self._status_lbl.configure(
            text="Done" if success else "Failed",
            text_color=color,
        )
        self._set_bars_flat(_SUBTEXT)

        # Populate content
        self._trans_lbl.configure(
            text=f'"{_truncate(transcription, 80)}"' if transcription else ""
        )
        self._result_box.configure(state="normal")
        self._result_box.delete("1.0", "end")
        self._result_box.insert("end", message)
        self._result_box.configure(state="disabled")

        self._result_frame.pack(fill="x")
        self._position(_CARD_H_R)

        # Auto-dismiss after 6 s
        self._dismiss_job = self.after(6000, self._do_dismiss)

    def _do_dismiss(self):
        self._cancel_jobs()
        self._state = "hidden"
        self._fade_to(0.0, on_done=self.withdraw)
        if self.on_dismiss:
            self.on_dismiss()

    # ── Waveform animation ────────────────────────────────────────────────────

    def _update_waveform(self):
        if self._state != "listening":
            return
        rms = self._audio_capture.current_rms if self._audio_capture else 0.0
        # Boost quiet room so there's visible motion
        rms = min(1.0, rms * 6.0)

        canvas_h = 36
        min_h, max_h = 6, canvas_h - 4

        for i, bid in enumerate(self._bar_ids):
            phase = rms + (i - 2) * 0.08 + random.uniform(-0.04, 0.04)
            phase = max(0.0, min(1.0, phase))
            bar_h = int(min_h + phase * (max_h - min_h))
            y_top = (canvas_h - bar_h) // 2
            y_bot = y_top + bar_h
            x = 2 + i * 8
            self._wave_canvas.coords(bid, x, y_top, x + 5, y_bot)

        self._waveform_job = self.after(60, self._update_waveform)

    def _update_pulse(self):
        if self._state != "processing":
            return
        self._pulse_phase += 0.15
        canvas_h = 36
        for i, bid in enumerate(self._bar_ids):
            t = math.sin(self._pulse_phase + i * 0.8) * 0.5 + 0.5
            bar_h = int(6 + t * 18)
            y_top = (canvas_h - bar_h) // 2
            y_bot = y_top + bar_h
            x = 2 + i * 8
            self._wave_canvas.coords(bid, x, y_top, x + 5, y_bot)

        self._pulse_job = self.after(60, self._update_pulse)

    # ── Fade animation ────────────────────────────────────────────────────────

    def _fade_to(self, target: float, on_done: Optional[Callable] = None, step: float = 0.09):
        if self._fade_job:
            self.after_cancel(self._fade_job)
            self._fade_job = None
        self._fade_step(target, on_done, step)

    def _fade_step(self, target: float, on_done, step: float):
        try:
            current = self.wm_attributes("-alpha")
        except Exception:
            return
        diff = target - current
        if abs(diff) < step:
            self.wm_attributes("-alpha", target)
            if on_done:
                on_done()
            return
        self.wm_attributes("-alpha", current + (step if diff > 0 else -step))
        self._fade_job = self.after(16, lambda: self._fade_step(target, on_done, step))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_bars_color(self, color: str):
        for bid in self._bar_ids:
            self._wave_canvas.itemconfigure(bid, fill=color)

    def _set_bars_flat(self, color: str):
        self._set_bars_color(color)
        canvas_h = 36
        bar_h = 6
        y_top = (canvas_h - bar_h) // 2
        y_bot = y_top + bar_h
        for i, bid in enumerate(self._bar_ids):
            x = 2 + i * 8
            self._wave_canvas.coords(bid, x, y_top, x + 5, y_bot)

    def _cancel_jobs(self):
        for attr in ("_dismiss_job", "_waveform_job", "_pulse_job", "_fade_job"):
            job = getattr(self, attr, None)
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
            setattr(self, attr, None)


# ── Utility ───────────────────────────────────────────────────────────────────

def _truncate(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n - 1] + "\u2026"
