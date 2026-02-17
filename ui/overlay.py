"""
Floating overlay window for prompt preview and voice notes.
Thread-safe: all tkinter calls go through the main tk thread via queue.
Styled with Seren-inspired dark therapeutic aesthetic.
"""

import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, Optional
from queue import Queue, Empty
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Seren-inspired overlay colors
OV_COLORS = {
    "bg": "#191A1A",
    "bg_card": "#262626",
    "bg_input": "#202222",
    "bg_button": "#2A2D2E",
    "bg_button_hover": "#3C3F40",
    "accent": "#1BB9CE",
    "accent_hover": "#17A3B6",
    "text_primary": "#FFFFFF",
    "text_secondary": "#AAAAAA",
    "text_muted": "#737373",
    "border": "#3C3F40",
    "border_light": "#2A2D2E",
    "recording_red": "#B87878",
    "success": "#7DA888",
}


class _StyledButton(tk.Canvas):
    """A custom styled button using Canvas for the dark overlay theme."""

    def __init__(self, master, text, command=None, accent=False,
                 danger=False, width=120, height=34, **kwargs):
        super().__init__(
            master, width=width, height=height,
            bg=OV_COLORS["bg"], highlightthickness=0, **kwargs
        )
        self._text = text
        self._command = command
        self._width = width
        self._height = height
        self._accent = accent
        self._danger = danger
        self._hovered = False

        if accent:
            self._bg = OV_COLORS["accent"]
            self._bg_hover = OV_COLORS["accent_hover"]
            self._fg = OV_COLORS["bg"]
        elif danger:
            self._bg = OV_COLORS["recording_red"]
            self._bg_hover = "#A06868"
            self._fg = "#FFFFFF"
        else:
            self._bg = OV_COLORS["bg_button"]
            self._bg_hover = OV_COLORS["bg_button_hover"]
            self._fg = OV_COLORS["text_secondary"]

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

        self._draw()

    def _draw(self):
        self.delete("all")
        bg = self._bg_hover if self._hovered else self._bg
        r = 12
        w, h = self._width, self._height

        # Rounded rectangle
        self.create_arc(0, 0, r*2, r*2, start=90, extent=90, fill=bg, outline=bg)
        self.create_arc(w-r*2, 0, w, r*2, start=0, extent=90, fill=bg, outline=bg)
        self.create_arc(0, h-r*2, r*2, h, start=180, extent=90, fill=bg, outline=bg)
        self.create_arc(w-r*2, h-r*2, w, h, start=270, extent=90, fill=bg, outline=bg)
        self.create_rectangle(r, 0, w-r, h, fill=bg, outline=bg)
        self.create_rectangle(0, r, w, h-r, fill=bg, outline=bg)

        # Text
        self.create_text(
            w // 2, h // 2, text=self._text,
            fill=self._fg, font=("Segoe UI", 11)
        )

    def _on_enter(self, e):
        self._hovered = True
        self._draw()

    def _on_leave(self, e):
        self._hovered = False
        self._draw()

    def _on_click(self, e):
        if self._command:
            self._command()

    def set_text(self, text):
        self._text = text
        self._draw()


class OverlayWindow:
    """Floating overlay window - thread-safe, Seren-styled."""

    def __init__(self):
        self.root: Optional[tk.Tk] = None
        self.is_visible = False
        self._cmd_queue: Queue = Queue()

        # Callbacks
        self.on_accept: Optional[Callable[[str], None]] = None
        self.on_use_raw: Optional[Callable[[str], None]] = None
        self.on_cancel: Optional[Callable] = None
        self.on_save_note: Optional[Callable[[str, str], None]] = None

        # Current state
        self.raw_text = ""
        self.enhanced_text = ""
        self.current_mode = "code_prompt"

        logger.info("OverlayWindow initialized")

    def create_window(self):
        """Create the overlay window. Must be called from the overlay thread."""
        if self.root is not None:
            return

        self.root = tk.Tk()
        self.root.title("Not Whisper Flow")
        self.root.geometry("680x460")
        self.root.configure(bg=OV_COLORS["bg"])
        self.root.attributes('-topmost', True)

        try:
            self.root.attributes('-alpha', 0.96)
        except Exception:
            pass

        self._create_ui()

        self.root.bind('<Return>', lambda e: self._on_accept_clicked())
        self.root.bind('<Escape>', lambda e: self._on_cancel_clicked())

        # Hide by default
        self.root.withdraw()

        # Start processing the command queue
        self._process_queue()

        logger.info("Overlay window created")

    def _process_queue(self):
        """Process pending commands from other threads."""
        try:
            while True:
                cmd, args = self._cmd_queue.get_nowait()
                if cmd == "show":
                    self._do_show(*args)
                elif cmd == "hide":
                    self._do_hide()
                elif cmd == "destroy":
                    self._do_destroy()
                    return
                elif cmd == "set_mode":
                    self._do_set_mode(*args)
        except Empty:
            pass

        if self.root:
            self.root.after(50, self._process_queue)

    def _create_ui(self):
        """Create Seren-styled dark UI elements."""
        # Main container with padding
        main_frame = tk.Frame(self.root, bg=OV_COLORS["bg"], padx=24, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ---- Mode indicator ----
        mode_bar = tk.Frame(main_frame, bg=OV_COLORS["bg"])
        mode_bar.pack(fill=tk.X, pady=(0, 16))

        self.mode_label = tk.Label(
            mode_bar, text="code prompt",
            font=("Georgia", 14),
            fg=OV_COLORS["accent"], bg=OV_COLORS["bg"],
            anchor="w"
        )
        self.mode_label.pack(side=tk.LEFT)

        # ---- Raw transcription section ----
        raw_header = tk.Label(
            main_frame, text="what you said",
            font=("Segoe UI", 10, "bold"),
            fg=OV_COLORS["text_muted"], bg=OV_COLORS["bg"],
            anchor="w"
        )
        raw_header.pack(fill=tk.X, pady=(0, 6))

        raw_card = tk.Frame(
            main_frame, bg=OV_COLORS["bg_card"],
            highlightbackground=OV_COLORS["border_light"],
            highlightthickness=1
        )
        raw_card.pack(fill=tk.X, pady=(0, 16))

        self.raw_text_widget = tk.Text(
            raw_card, height=3, wrap=tk.WORD,
            font=("Georgia", 12),
            bg=OV_COLORS["bg_card"],
            fg=OV_COLORS["text_secondary"],
            insertbackground=OV_COLORS["text_primary"],
            relief=tk.FLAT, padx=14, pady=10,
            borderwidth=0,
            selectbackground=OV_COLORS["accent"],
            selectforeground=OV_COLORS["bg"]
        )
        self.raw_text_widget.pack(fill=tk.X)

        # ---- Enhanced output section ----
        self.enhanced_label = tk.Label(
            main_frame, text="enhanced prompt",
            font=("Segoe UI", 10, "bold"),
            fg=OV_COLORS["accent"], bg=OV_COLORS["bg"],
            anchor="w"
        )
        self.enhanced_label.pack(fill=tk.X, pady=(0, 6))

        enhanced_card = tk.Frame(
            main_frame, bg=OV_COLORS["bg_card"],
            highlightbackground=OV_COLORS["border_light"],
            highlightthickness=1
        )
        enhanced_card.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        self.enhanced_text_widget = tk.Text(
            enhanced_card, height=8, wrap=tk.WORD,
            font=("Segoe UI", 12),
            bg=OV_COLORS["bg_card"],
            fg=OV_COLORS["text_primary"],
            insertbackground=OV_COLORS["accent"],
            relief=tk.FLAT, padx=14, pady=10,
            borderwidth=0,
            selectbackground=OV_COLORS["accent"],
            selectforeground=OV_COLORS["bg"]
        )
        self.enhanced_text_widget.pack(fill=tk.BOTH, expand=True)

        # ---- Button row ----
        button_frame = tk.Frame(main_frame, bg=OV_COLORS["bg"])
        button_frame.pack(fill=tk.X)

        self.accept_btn = _StyledButton(
            button_frame, text="accept (enter)",
            command=self._on_accept_clicked,
            accent=True, width=130
        )
        self.accept_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.raw_btn = _StyledButton(
            button_frame, text="use raw",
            command=self._on_use_raw_clicked,
            width=90
        )
        self.raw_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.edit_btn = _StyledButton(
            button_frame, text="edit",
            command=self._on_edit_clicked,
            width=70
        )
        self.edit_btn.pack(side=tk.LEFT, padx=(0, 8))

        # Save Note button (only shown in voice_notes mode)
        self.save_note_btn = _StyledButton(
            button_frame, text="save note",
            command=self._on_save_note_clicked,
            accent=True, width=100
        )

        self.cancel_btn = _StyledButton(
            button_frame, text="cancel (esc)",
            command=self._on_cancel_clicked,
            width=110
        )
        self.cancel_btn.pack(side=tk.RIGHT)

    def show(self, raw_text: str, enhanced_text: str):
        self._cmd_queue.put(("show", (raw_text, enhanced_text)))

    def hide(self):
        self._cmd_queue.put(("hide", ()))

    def set_mode(self, mode: str):
        self._cmd_queue.put(("set_mode", (mode,)))

    def _do_set_mode(self, mode: str):
        self.current_mode = mode
        if mode == "voice_notes":
            self.mode_label.config(text="voice notes")
            self.enhanced_label.config(text="cleaned up note")
            self.accept_btn.set_text("copy (enter)")
            self.save_note_btn.pack(side=tk.LEFT, padx=(0, 8))
        else:
            self.mode_label.config(text="code prompt")
            self.enhanced_label.config(text="enhanced prompt")
            self.accept_btn.set_text("accept (enter)")
            self.save_note_btn.pack_forget()

    def _do_show(self, raw_text: str, enhanced_text: str):
        self.raw_text = raw_text
        self.enhanced_text = enhanced_text

        self.raw_text_widget.config(state=tk.NORMAL)
        self.raw_text_widget.delete('1.0', tk.END)
        self.raw_text_widget.insert('1.0', raw_text)
        self.raw_text_widget.config(state=tk.DISABLED)

        self.enhanced_text_widget.config(state=tk.NORMAL)
        self.enhanced_text_widget.delete('1.0', tk.END)
        self.enhanced_text_widget.insert('1.0', enhanced_text)
        self.enhanced_text_widget.config(state=tk.DISABLED)

        # Reset edit button
        self.edit_btn.set_text("edit")
        self.edit_btn._command = self._on_edit_clicked

        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.is_visible = True

    def _do_hide(self):
        if self.root:
            self.root.withdraw()
            self.is_visible = False

    def _do_destroy(self):
        if self.root:
            self.root.destroy()
            self.root = None

    def _on_accept_clicked(self):
        text = self.enhanced_text_widget.get('1.0', tk.END).strip()
        if self.on_accept:
            self.on_accept(text)
        self._do_hide()

    def _on_use_raw_clicked(self):
        if self.on_use_raw:
            self.on_use_raw(self.raw_text)
        self._do_hide()

    def _on_edit_clicked(self):
        self.enhanced_text_widget.config(state=tk.NORMAL)
        self.enhanced_text_widget.focus()
        self.edit_btn.set_text("done")
        self.edit_btn._command = self._on_save_edit_clicked

    def _on_save_edit_clicked(self):
        self.enhanced_text = self.enhanced_text_widget.get('1.0', tk.END).strip()
        self.enhanced_text_widget.config(state=tk.DISABLED)
        self.edit_btn.set_text("edit")
        self.edit_btn._command = self._on_edit_clicked

    def _on_save_note_clicked(self):
        text = self.enhanced_text_widget.get('1.0', tk.END).strip()
        if self.on_save_note:
            self.on_save_note(self.raw_text, text)
        self._do_hide()

    def _on_cancel_clicked(self):
        if self.on_cancel:
            self.on_cancel()
        self._do_hide()

    def run(self):
        if self.root is None:
            self.create_window()
        self.root.mainloop()

    def destroy(self):
        self._cmd_queue.put(("destroy", ()))
