"""
Floating overlay window for prompt preview and voice notes.
Thread-safe: all tkinter calls go through the main tk thread via queue.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional
from queue import Queue, Empty
from utils.logger import setup_logger

logger = setup_logger(__name__)


class OverlayWindow:
    """Floating overlay window - thread-safe."""

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
        self.root.geometry("650x420")
        self.root.attributes('-topmost', True)

        try:
            self.root.attributes('-alpha', 0.95)
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
        """Process pending commands from other threads. Runs in tk mainloop."""
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
        """Create UI elements."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=2)

        # Mode indicator
        self.mode_label = ttk.Label(main_frame, text="Mode: Code Prompt",
                                     font=('Arial', 9, 'bold'))
        self.mode_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        # Raw transcription
        raw_label = ttk.Label(main_frame, text="What you said:",
                              font=('Arial', 10, 'bold'))
        raw_label.grid(row=0, column=0, sticky=tk.E, pady=(0, 5))

        self.raw_text_widget = tk.Text(main_frame, height=3, wrap=tk.WORD,
                                       font=('Arial', 10), bg='#f0f0f0')
        self.raw_text_widget.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Enhanced output
        self.enhanced_label = ttk.Label(main_frame, text="Enhanced Prompt:",
                                         font=('Arial', 10, 'bold'))
        self.enhanced_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 5))

        self.enhanced_text_widget = tk.Text(main_frame, height=8, wrap=tk.WORD,
                                            font=('Arial', 10), bg='#e8f4f8')
        self.enhanced_text_widget.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        self.accept_btn = ttk.Button(button_frame, text="Accept (Enter)",
                                     command=self._on_accept_clicked)
        self.accept_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.raw_btn = ttk.Button(button_frame, text="Use Raw",
                                  command=self._on_use_raw_clicked)
        self.raw_btn.pack(side=tk.LEFT, padx=5)

        self.edit_btn = ttk.Button(button_frame, text="Edit",
                                   command=self._on_edit_clicked)
        self.edit_btn.pack(side=tk.LEFT, padx=5)

        # Save Note button (only shown in voice_notes mode)
        self.save_note_btn = ttk.Button(button_frame, text="Save Note",
                                         command=self._on_save_note_clicked)

        self.cancel_btn = ttk.Button(button_frame, text="Cancel (Esc)",
                                     command=self._on_cancel_clicked)
        self.cancel_btn.pack(side=tk.RIGHT)

    def show(self, raw_text: str, enhanced_text: str):
        """Thread-safe: queue a show command."""
        self._cmd_queue.put(("show", (raw_text, enhanced_text)))

    def hide(self):
        """Thread-safe: queue a hide command."""
        self._cmd_queue.put(("hide", ()))

    def set_mode(self, mode: str):
        """Thread-safe: queue a mode change."""
        self._cmd_queue.put(("set_mode", (mode,)))

    def _do_set_mode(self, mode: str):
        """Update UI for mode change. Called from tk thread."""
        self.current_mode = mode
        if mode == "voice_notes":
            self.mode_label.config(text="Mode: Voice Notes")
            self.enhanced_label.config(text="Cleaned Up Note:")
            self.enhanced_text_widget.config(bg='#e8f0e8')
            self.accept_btn.config(text="Copy (Enter)")
            self.save_note_btn.pack(side=tk.LEFT, padx=5)
        else:
            self.mode_label.config(text="Mode: Code Prompt")
            self.enhanced_label.config(text="Enhanced Prompt:")
            self.enhanced_text_widget.config(bg='#e8f4f8')
            self.accept_btn.config(text="Accept (Enter)")
            self.save_note_btn.pack_forget()

    def _do_show(self, raw_text: str, enhanced_text: str):
        """Show overlay. Called from tk thread."""
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
        self.edit_btn.config(text="Edit", command=self._on_edit_clicked)

        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.is_visible = True

    def _do_hide(self):
        """Hide overlay. Called from tk thread."""
        if self.root:
            self.root.withdraw()
            self.is_visible = False

    def _do_destroy(self):
        """Destroy overlay. Called from tk thread."""
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
        self.edit_btn.config(text="Done", command=self._on_save_edit_clicked)

    def _on_save_edit_clicked(self):
        self.enhanced_text = self.enhanced_text_widget.get('1.0', tk.END).strip()
        self.enhanced_text_widget.config(state=tk.DISABLED)
        self.edit_btn.config(text="Edit", command=self._on_edit_clicked)

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
        """Run the overlay window mainloop (blocking)."""
        if self.root is None:
            self.create_window()
        self.root.mainloop()

    def destroy(self):
        """Thread-safe destroy."""
        self._cmd_queue.put(("destroy", ()))
