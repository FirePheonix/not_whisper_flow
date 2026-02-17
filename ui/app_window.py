"""
Main desktop application window - dark themed, sidebar navigation.
Built with CustomTkinter for modern look.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Callable, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

# App colors
COLORS = {
    "bg_dark": "#1a1a1a",
    "bg_sidebar": "#111111",
    "bg_card": "#2a2a2a",
    "bg_input": "#333333",
    "bg_hover": "#3a3a3a",
    "accent": "#f5a623",       # Gold/amber accent like Flowin
    "accent_hover": "#e09000",
    "text_primary": "#ffffff",
    "text_secondary": "#aaaaaa",
    "text_muted": "#666666",
    "recording_red": "#ff4444",
    "success_green": "#44cc66",
    "border": "#333333",
}


class SidebarButton(ctk.CTkButton):
    """Custom sidebar navigation button."""

    def __init__(self, master, text, icon_text="", **kwargs):
        super().__init__(
            master,
            text=f"  {icon_text}  {text}" if icon_text else f"  {text}",
            anchor="w",
            height=44,
            corner_radius=8,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            **kwargs
        )
        self._is_active = False

    def set_active(self, active: bool):
        self._is_active = active
        if active:
            self.configure(
                fg_color=COLORS["bg_card"],
                text_color=COLORS["text_primary"]
            )
        else:
            self.configure(
                fg_color="transparent",
                text_color=COLORS["text_secondary"]
            )


class RecordButton(ctk.CTkButton):
    """Large circular record button with animation."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            text="",
            width=80,
            height=80,
            corner_radius=40,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_hover"],
            border_width=3,
            border_color=COLORS["accent"],
            **kwargs
        )
        self._is_recording = False
        self._update_appearance()

    def set_recording(self, recording: bool):
        self._is_recording = recording
        self._update_appearance()

    def _update_appearance(self):
        if self._is_recording:
            self.configure(
                fg_color=COLORS["recording_red"],
                hover_color="#cc3333",
                border_color=COLORS["recording_red"],
                text="Stop",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="white"
            )
        else:
            self.configure(
                fg_color=COLORS["bg_card"],
                hover_color=COLORS["bg_hover"],
                border_color=COLORS["accent"],
                text="Rec",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLORS["accent"]
            )


class CodePromptPage(ctk.CTkFrame):
    """Code Prompt mode page."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_dark"], **kwargs)

        self.on_record_toggle: Optional[Callable] = None
        self.on_copy: Optional[Callable[[str], None]] = None

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(25, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Code Prompt",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header, text="Speak your coding problem. Get a polished prompt.",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_secondary"]
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Record section
        record_frame = ctk.CTkFrame(self, fg_color="transparent")
        record_frame.grid(row=1, column=0, pady=(20, 10))

        self.record_btn = RecordButton(record_frame, command=self._on_record)
        self.record_btn.pack()

        self.status_label = ctk.CTkLabel(
            record_frame, text="Press to record or Ctrl+Shift+Space",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"]
        )
        self.status_label.pack(pady=(8, 0))

        # Raw transcription
        raw_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        raw_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=(10, 5))
        raw_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            raw_frame, text="What you said:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_secondary"]
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 0))

        self.raw_text = ctk.CTkTextbox(
            raw_frame, height=60,
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_muted"],
            border_width=0,
            wrap="word"
        )
        self.raw_text.grid(row=1, column=0, sticky="ew", padx=15, pady=(4, 12))
        self.raw_text.configure(state="disabled")

        # Enhanced prompt
        enhanced_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        enhanced_frame.grid(row=3, column=0, sticky="nsew", padx=30, pady=(5, 10))
        enhanced_frame.grid_columnconfigure(0, weight=1)
        enhanced_frame.grid_rowconfigure(1, weight=1)

        enhanced_header = ctk.CTkFrame(enhanced_frame, fg_color="transparent")
        enhanced_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 0))
        enhanced_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            enhanced_header, text="Enhanced Prompt:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["accent"]
        ).grid(row=0, column=0, sticky="w")

        self.copy_btn = ctk.CTkButton(
            enhanced_header, text="Copy",
            width=70, height=28, corner_radius=6,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg_dark"],
            command=self._on_copy
        )
        self.copy_btn.grid(row=0, column=1, sticky="e")

        self.enhanced_text = ctk.CTkTextbox(
            enhanced_frame,
            font=ctk.CTkFont(size=14),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            border_width=0,
            wrap="word"
        )
        self.enhanced_text.grid(row=1, column=0, sticky="nsew", padx=15, pady=(4, 12))

    def _on_record(self):
        if self.on_record_toggle:
            self.on_record_toggle()

    def _on_copy(self):
        text = self.enhanced_text.get("1.0", "end").strip()
        if text and self.on_copy:
            self.on_copy(text)

    def set_recording(self, recording: bool):
        self.record_btn.set_recording(recording)
        if recording:
            self.status_label.configure(text="Listening... speak now", text_color=COLORS["recording_red"])
        else:
            self.status_label.configure(text="Press to record or Ctrl+Shift+Space", text_color=COLORS["text_muted"])

    def set_processing(self):
        self.status_label.configure(text="Processing...", text_color=COLORS["accent"])

    def show_result(self, raw: str, enhanced: str):
        self.raw_text.configure(state="normal")
        self.raw_text.delete("1.0", "end")
        self.raw_text.insert("1.0", raw)
        self.raw_text.configure(state="disabled")

        self.enhanced_text.delete("1.0", "end")
        self.enhanced_text.insert("1.0", enhanced)

        self.status_label.configure(text="Done! Edit the prompt or copy it.", text_color=COLORS["success_green"])


class NoteCard(ctk.CTkFrame):
    """A single note card in the list."""

    def __init__(self, master, note_data: dict, on_click: Callable = None, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_card"], corner_radius=10,
                         height=70, **kwargs)
        self.note_data = note_data
        self._on_click = on_click

        self.grid_columnconfigure(0, weight=1)

        # Parse timestamp
        try:
            dt = datetime.fromisoformat(note_data["timestamp"])
            time_str = dt.strftime("%b %d, %Y  %H:%M")
        except Exception:
            time_str = note_data.get("timestamp", "")

        preview = note_data.get("preview", "")[:80]

        ctk.CTkLabel(
            self, text=time_str,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"],
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))

        ctk.CTkLabel(
            self, text=preview,
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_primary"],
            anchor="w",
            wraplength=400
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(2, 10))

        self.bind("<Button-1>", self._clicked)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._clicked)

    def _clicked(self, event=None):
        if self._on_click:
            self._on_click(self.note_data)


class VoiceNotesPage(ctk.CTkFrame):
    """Voice Notes mode page."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_dark"], **kwargs)

        self.on_record_toggle: Optional[Callable] = None
        self.on_delete_note: Optional[Callable[[str], None]] = None
        self._notes_store = None

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(25, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Voice Notes",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=0, sticky="w")

        # Record button in header
        self.record_btn = RecordButton(header)
        self.record_btn.configure(
            width=50, height=50, corner_radius=25,
            command=self._on_record
        )
        self.record_btn.grid(row=0, column=1, sticky="e")

        self.status_label = ctk.CTkLabel(
            header, text="Press to record a new note",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"]
        )
        self.status_label.grid(row=1, column=0, sticky="w", pady=(4, 0), columnspan=2)

        # Search bar
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", padx=30, pady=(15, 10))
        search_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="Search notes...",
            height=38, corner_radius=10,
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.search_entry.grid(row=0, column=0, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # Notes list (scrollable)
        self.notes_scroll = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_dark"],
            scrollbar_button_color=COLORS["bg_card"],
            scrollbar_button_hover_color=COLORS["bg_hover"]
        )
        self.notes_scroll.grid(row=2, column=0, sticky="nsew", padx=30, pady=(5, 10))
        self.notes_scroll.grid_columnconfigure(0, weight=1)

        # Note detail overlay (hidden by default)
        self.detail_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"])
        self.detail_frame.grid_columnconfigure(0, weight=1)
        self.detail_frame.grid_rowconfigure(1, weight=1)
        # Don't grid it yet - shown on demand

        self._empty_label = ctk.CTkLabel(
            self.notes_scroll, text="No notes yet. Record your first one!",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_muted"]
        )

    def set_notes_store(self, store):
        self._notes_store = store
        self.refresh_notes()

    def refresh_notes(self):
        """Reload notes from store."""
        if not self._notes_store:
            return

        # Clear existing
        for widget in self.notes_scroll.winfo_children():
            widget.destroy()

        notes = self._notes_store.list_notes(limit=100)

        if not notes:
            self._empty_label = ctk.CTkLabel(
                self.notes_scroll, text="No notes yet. Record your first one!",
                font=ctk.CTkFont(size=14),
                text_color=COLORS["text_muted"]
            )
            self._empty_label.grid(row=0, column=0, pady=40)
            return

        for i, note in enumerate(notes):
            card = NoteCard(self.notes_scroll, note, on_click=self._show_note_detail)
            card.grid(row=i, column=0, sticky="ew", pady=(0, 6))

    def _show_note_detail(self, note_data: dict):
        """Show full note content."""
        if not self._notes_store:
            return

        full_note = self._notes_store.get_note(note_data["id"])
        if not full_note:
            return

        # Clear detail
        for w in self.detail_frame.winfo_children():
            w.destroy()

        # Back button
        back_btn = ctk.CTkButton(
            self.detail_frame, text="< Back",
            width=80, height=32, corner_radius=6,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            command=self._hide_note_detail
        )
        back_btn.grid(row=0, column=0, sticky="w", padx=30, pady=(20, 10))

        # Delete button
        del_btn = ctk.CTkButton(
            self.detail_frame, text="Delete",
            width=70, height=32, corner_radius=6,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["recording_red"],
            hover_color="#cc3333",
            command=lambda: self._delete_note(full_note["id"])
        )
        del_btn.grid(row=0, column=0, sticky="e", padx=30, pady=(20, 10))

        # Note content
        content_text = ctk.CTkTextbox(
            self.detail_frame,
            font=ctk.CTkFont(size=14),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            corner_radius=12,
            wrap="word"
        )
        content_text.grid(row=1, column=0, sticky="nsew", padx=30, pady=(0, 20))
        content_text.insert("1.0", full_note.get("text", ""))

        # Show detail, hide list
        self.notes_scroll.grid_remove()
        self.search_entry.master.grid_remove()
        self.detail_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        self.detail_frame.grid_rowconfigure(1, weight=1)

    def _hide_note_detail(self):
        self.detail_frame.grid_remove()
        self.search_entry.master.grid()
        self.notes_scroll.grid()

    def _delete_note(self, note_id: str):
        if self._notes_store:
            self._notes_store.delete_note(note_id)
        self._hide_note_detail()
        self.refresh_notes()

    def _on_record(self):
        if self.on_record_toggle:
            self.on_record_toggle()

    def _on_search(self, event=None):
        query = self.search_entry.get().strip()
        if not self._notes_store:
            return

        for widget in self.notes_scroll.winfo_children():
            widget.destroy()

        if query:
            notes = self._notes_store.search_notes(query)
        else:
            notes = self._notes_store.list_notes(limit=100)

        if not notes:
            ctk.CTkLabel(
                self.notes_scroll, text="No notes found.",
                font=ctk.CTkFont(size=14),
                text_color=COLORS["text_muted"]
            ).grid(row=0, column=0, pady=40)
            return

        for i, note in enumerate(notes):
            card = NoteCard(self.notes_scroll, note, on_click=self._show_note_detail)
            card.grid(row=i, column=0, sticky="ew", pady=(0, 6))

    def set_recording(self, recording: bool):
        self.record_btn.set_recording(recording)
        if recording:
            self.status_label.configure(text="Listening...", text_color=COLORS["recording_red"])
        else:
            self.status_label.configure(text="Press to record a new note", text_color=COLORS["text_muted"])

    def set_processing(self):
        self.status_label.configure(text="Processing...", text_color=COLORS["accent"])

    def show_saved(self):
        self.status_label.configure(text="Note saved!", text_color=COLORS["success_green"])
        self.refresh_notes()


class AppWindow(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # Window setup
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("Not Whisper Flow")
        self.geometry("900x650")
        self.minsize(700, 500)
        self.configure(fg_color=COLORS["bg_dark"])

        # Callbacks
        self.on_record_toggle: Optional[Callable] = None
        self.on_copy_text: Optional[Callable[[str], None]] = None
        self.on_quit: Optional[Callable] = None

        self._current_page = "code_prompt"
        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ===== SIDEBAR =====
        sidebar = ctk.CTkFrame(self, width=220, fg_color=COLORS["bg_sidebar"], corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        # App title
        title_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(20, 25))

        ctk.CTkLabel(
            title_frame, text="Not Whisper",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["accent"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame, text="Flow",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w")

        # Nav buttons
        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.grid(row=1, column=0, sticky="ew", padx=10)
        nav_frame.grid_columnconfigure(0, weight=1)

        self.btn_code = SidebarButton(
            nav_frame, text="Code Prompt", icon_text=">_",
            command=lambda: self._switch_page("code_prompt")
        )
        self.btn_code.grid(row=0, column=0, sticky="ew", pady=2)

        self.btn_notes = SidebarButton(
            nav_frame, text="Voice Notes", icon_text="~",
            command=lambda: self._switch_page("voice_notes")
        )
        self.btn_notes.grid(row=1, column=0, sticky="ew", pady=2)

        # Spacer
        sidebar.grid_rowconfigure(2, weight=1)

        # Bottom info
        info_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        info_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 15))

        ctk.CTkLabel(
            info_frame,
            text="100% Local & Free",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"]
        ).pack(anchor="w")

        hotkey_label = ctk.CTkLabel(
            info_frame,
            text="Ctrl+Shift+Space",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"]
        )
        hotkey_label.pack(anchor="w")

        # ===== CONTENT AREA =====
        self.content_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"], corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Pages
        self.code_page = CodePromptPage(self.content_frame)
        self.code_page.on_record_toggle = self._on_record
        self.code_page.on_copy = self._on_copy

        self.notes_page = VoiceNotesPage(self.content_frame)
        self.notes_page.on_record_toggle = self._on_record

        # Show default page
        self._switch_page("code_prompt")

    def _switch_page(self, page: str):
        self._current_page = page

        self.code_page.grid_remove()
        self.notes_page.grid_remove()

        if page == "code_prompt":
            self.code_page.grid(row=0, column=0, sticky="nsew")
            self.btn_code.set_active(True)
            self.btn_notes.set_active(False)
        elif page == "voice_notes":
            self.notes_page.grid(row=0, column=0, sticky="nsew")
            self.btn_code.set_active(False)
            self.btn_notes.set_active(True)

    def _on_record(self):
        if self.on_record_toggle:
            self.on_record_toggle()

    def _on_copy(self, text: str):
        if self.on_copy_text:
            self.on_copy_text(text)

    def _on_close(self):
        if self.on_quit:
            self.on_quit()
        self.destroy()

    @property
    def current_page(self) -> str:
        return self._current_page

    def set_recording(self, recording: bool):
        """Update recording state on the active page."""
        self.code_page.set_recording(recording)
        self.notes_page.set_recording(recording)

    def set_processing(self):
        if self._current_page == "code_prompt":
            self.code_page.set_processing()
        else:
            self.notes_page.set_processing()

    def show_code_result(self, raw: str, enhanced: str):
        self.code_page.show_result(raw, enhanced)

    def show_note_saved(self):
        self.notes_page.show_saved()

    def set_notes_store(self, store):
        self.notes_page.set_notes_store(store)
