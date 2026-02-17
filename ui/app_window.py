"""
Main desktop application window - Seren-inspired calm, dark therapeutic UI.
Built with CustomTkinter. Uses Imbue for display text, Inter/system for body.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Callable, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Try to load custom fonts (Imbue + Inter)
try:
    from ui.fonts import get_display_font, get_body_font, load_fonts
    _fonts = load_fonts()
    DISPLAY_FONT = _fonts["display"]
    BODY_FONT = _fonts["body"]
except Exception:
    DISPLAY_FONT = "Georgia"
    BODY_FONT = "Segoe UI"

# ============================================================
# Seren-inspired color palette - calm, therapeutic, dark
# ============================================================
COLORS = {
    # Backgrounds - deep, layered darks
    "bg_dark": "#191A1A",
    "bg_secondary": "#202222",
    "bg_sidebar": "#202222",
    "bg_card": "#262626",
    "bg_input": "#202222",
    "bg_hover": "#2F302F",
    "bg_elevated": "#2A2D2E",

    # Accent - soft cyan (Seren primary)
    "accent": "#1BB9CE",
    "accent_hover": "#17A3B6",
    "accent_soft": "#1BB9CE22",
    "accent_purple": "#9B8FE8",

    # Text - layered hierarchy
    "text_primary": "#FFFFFF",
    "text_secondary": "#AAAAAA",
    "text_tertiary": "#909090",
    "text_muted": "#737373",

    # Borders - subtle
    "border": "#3C3F40",
    "border_light": "#2A2D2E",

    # Status - muted for calm UI
    "recording_red": "#B87878",
    "recording_red_hover": "#A06868",
    "success": "#7DA888",
    "warning": "#D4A574",
    "error": "#B87878",

    # Voice orb
    "orb_core": "#4DA8E8",
    "orb_glow": "#2E8BC0",
    "orb_ring": "#1E5F8A",
}


def _display_font(size: int, weight: str = "normal") -> ctk.CTkFont:
    """Create a display/heading font (Imbue style)."""
    return ctk.CTkFont(family=DISPLAY_FONT, size=size, weight=weight)


def _body_font(size: int, weight: str = "normal") -> ctk.CTkFont:
    """Create a body text font (Inter style)."""
    return ctk.CTkFont(family=BODY_FONT, size=size, weight=weight)


# ============================================================
# Sidebar Button
# ============================================================
class SidebarButton(ctk.CTkButton):
    """Minimal sidebar navigation button - Seren style."""

    def __init__(self, master, text, icon_text="", **kwargs):
        super().__init__(
            master,
            text=f"  {icon_text}  {text}" if icon_text else f"  {text}",
            anchor="w",
            height=46,
            corner_radius=10,
            font=_body_font(14, "bold"),
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_muted"],
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
                text_color=COLORS["text_muted"]
            )


# ============================================================
# Record Button - Voice Orb inspired
# ============================================================
class RecordButton(ctk.CTkButton):
    """Circular record button inspired by Seren's voice orb."""

    def __init__(self, master, size=90, **kwargs):
        self._size = size
        super().__init__(
            master,
            text="",
            width=size,
            height=size,
            corner_radius=size // 2,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_elevated"],
            border_width=2,
            border_color=COLORS["orb_core"],
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
                hover_color=COLORS["recording_red_hover"],
                border_color=COLORS["recording_red"],
                border_width=3,
                text="stop",
                font=_body_font(13, "bold"),
                text_color="#FFFFFF"
            )
        else:
            self.configure(
                fg_color=COLORS["bg_card"],
                hover_color=COLORS["bg_elevated"],
                border_color=COLORS["orb_core"],
                border_width=2,
                text="rec",
                font=_body_font(13, "bold"),
                text_color=COLORS["orb_core"]
            )


# ============================================================
# Code Prompt Page
# ============================================================
class CodePromptPage(ctk.CTkFrame):
    """Code Prompt mode page - Seren aesthetic."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_dark"], **kwargs)

        self.on_record_toggle: Optional[Callable] = None
        self.on_copy: Optional[Callable[[str], None]] = None

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # ---- Header with Imbue display font ----
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=36, pady=(32, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="code prompt",
            font=_display_font(36),
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="speak your coding problem. get a polished prompt.",
            font=_body_font(14),
            text_color=COLORS["text_tertiary"]
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # ---- Record section ----
        record_frame = ctk.CTkFrame(self, fg_color="transparent")
        record_frame.grid(row=1, column=0, pady=(24, 16))

        self.record_btn = RecordButton(record_frame, command=self._on_record)
        self.record_btn.pack()

        self.status_label = ctk.CTkLabel(
            record_frame,
            text="press to record or ctrl+shift+space",
            font=_body_font(12),
            text_color=COLORS["text_muted"]
        )
        self.status_label.pack(pady=(12, 0))

        # ---- Raw transcription card ----
        raw_frame = ctk.CTkFrame(
            self, fg_color=COLORS["bg_card"], corner_radius=14,
            border_width=1, border_color=COLORS["border_light"]
        )
        raw_frame.grid(row=2, column=0, sticky="ew", padx=36, pady=(8, 6))
        raw_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            raw_frame, text="what you said",
            font=_body_font(12, "bold"),
            text_color=COLORS["text_muted"]
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 0))

        self.raw_text = ctk.CTkTextbox(
            raw_frame, height=60,
            font=_display_font(16),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_tertiary"],
            border_width=0,
            wrap="word"
        )
        self.raw_text.grid(row=1, column=0, sticky="ew", padx=18, pady=(4, 14))
        self.raw_text.configure(state="disabled")

        # ---- Enhanced prompt card ----
        enhanced_frame = ctk.CTkFrame(
            self, fg_color=COLORS["bg_card"], corner_radius=14,
            border_width=1, border_color=COLORS["border_light"]
        )
        enhanced_frame.grid(row=3, column=0, sticky="nsew", padx=36, pady=(6, 16))
        enhanced_frame.grid_columnconfigure(0, weight=1)
        enhanced_frame.grid_rowconfigure(1, weight=1)

        enhanced_header = ctk.CTkFrame(enhanced_frame, fg_color="transparent")
        enhanced_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 0))
        enhanced_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            enhanced_header, text="enhanced prompt",
            font=_body_font(12, "bold"),
            text_color=COLORS["accent"]
        ).grid(row=0, column=0, sticky="w")

        self.copy_btn = ctk.CTkButton(
            enhanced_header, text="copy",
            width=72, height=30, corner_radius=20,
            font=_body_font(12, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg_dark"],
            command=self._on_copy
        )
        self.copy_btn.grid(row=0, column=1, sticky="e")

        self.enhanced_text = ctk.CTkTextbox(
            enhanced_frame,
            font=_body_font(14),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            border_width=0,
            wrap="word"
        )
        self.enhanced_text.grid(row=1, column=0, sticky="nsew", padx=18, pady=(6, 14))

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
            self.status_label.configure(
                text="listening... speak now",
                text_color=COLORS["recording_red"]
            )
        else:
            self.status_label.configure(
                text="press to record or ctrl+shift+space",
                text_color=COLORS["text_muted"]
            )

    def set_processing(self):
        self.status_label.configure(
            text="processing...",
            text_color=COLORS["accent"]
        )

    def show_result(self, raw: str, enhanced: str):
        self.raw_text.configure(state="normal")
        self.raw_text.delete("1.0", "end")
        self.raw_text.insert("1.0", raw)
        self.raw_text.configure(state="disabled")

        self.enhanced_text.delete("1.0", "end")
        self.enhanced_text.insert("1.0", enhanced)

        self.status_label.configure(
            text="done! edit the prompt or copy it.",
            text_color=COLORS["success"]
        )


# ============================================================
# Note Card
# ============================================================
class NoteCard(ctk.CTkFrame):
    """A single note card - soft, rounded, Seren style."""

    def __init__(self, master, note_data: dict, on_click: Callable = None, **kwargs):
        super().__init__(
            master, fg_color=COLORS["bg_card"], corner_radius=12,
            height=76, border_width=1, border_color=COLORS["border_light"],
            **kwargs
        )
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
            font=_body_font(11),
            text_color=COLORS["text_muted"],
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 0))

        ctk.CTkLabel(
            self, text=preview,
            font=_body_font(13),
            text_color=COLORS["text_secondary"],
            anchor="w",
            wraplength=420
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(3, 12))

        self.bind("<Button-1>", self._clicked)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._clicked)

    def _clicked(self, event=None):
        if self._on_click:
            self._on_click(self.note_data)


# ============================================================
# Voice Notes Page
# ============================================================
class VoiceNotesPage(ctk.CTkFrame):
    """Voice Notes mode page - Seren aesthetic."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_dark"], **kwargs)

        self.on_record_toggle: Optional[Callable] = None
        self.on_delete_note: Optional[Callable[[str], None]] = None
        self._notes_store = None

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ---- Header ----
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=36, pady=(32, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="voice notes",
            font=_display_font(36),
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=0, sticky="w")

        # Record button in header
        self.record_btn = RecordButton(header, size=52)
        self.record_btn.configure(command=self._on_record)
        self.record_btn.grid(row=0, column=1, sticky="e")

        self.status_label = ctk.CTkLabel(
            header,
            text="press to record a new note",
            font=_body_font(12),
            text_color=COLORS["text_muted"]
        )
        self.status_label.grid(row=1, column=0, sticky="w", pady=(4, 0), columnspan=2)

        # ---- Search bar ----
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", padx=36, pady=(16, 12))
        search_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="search notes...",
            height=42, corner_radius=12,
            font=_body_font(13),
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"],
            placeholder_text_color=COLORS["text_muted"]
        )
        self.search_entry.grid(row=0, column=0, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # ---- Notes list ----
        self.notes_scroll = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_dark"],
            scrollbar_button_color=COLORS["bg_card"],
            scrollbar_button_hover_color=COLORS["bg_hover"]
        )
        self.notes_scroll.grid(row=2, column=0, sticky="nsew", padx=36, pady=(4, 16))
        self.notes_scroll.grid_columnconfigure(0, weight=1)

        # Note detail overlay (hidden by default)
        self.detail_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"])
        self.detail_frame.grid_columnconfigure(0, weight=1)
        self.detail_frame.grid_rowconfigure(1, weight=1)

        self._empty_label = ctk.CTkLabel(
            self.notes_scroll,
            text="no notes yet. record your first one!",
            font=_display_font(18),
            text_color=COLORS["text_muted"]
        )

    def set_notes_store(self, store):
        self._notes_store = store
        self.refresh_notes()

    def refresh_notes(self):
        if not self._notes_store:
            return

        for widget in self.notes_scroll.winfo_children():
            widget.destroy()

        notes = self._notes_store.list_notes(limit=100)

        if not notes:
            self._empty_label = ctk.CTkLabel(
                self.notes_scroll,
                text="no notes yet. record your first one!",
                font=_display_font(18),
                text_color=COLORS["text_muted"]
            )
            self._empty_label.grid(row=0, column=0, pady=50)
            return

        for i, note in enumerate(notes):
            card = NoteCard(self.notes_scroll, note, on_click=self._show_note_detail)
            card.grid(row=i, column=0, sticky="ew", pady=(0, 8))

    def _show_note_detail(self, note_data: dict):
        if not self._notes_store:
            return

        full_note = self._notes_store.get_note(note_data["id"])
        if not full_note:
            return

        for w in self.detail_frame.winfo_children():
            w.destroy()

        # Top bar with back + delete
        top_bar = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=36, pady=(24, 12))
        top_bar.grid_columnconfigure(0, weight=1)

        back_btn = ctk.CTkButton(
            top_bar, text="< back",
            width=80, height=34, corner_radius=10,
            font=_body_font(13),
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            command=self._hide_note_detail
        )
        back_btn.grid(row=0, column=0, sticky="w")

        del_btn = ctk.CTkButton(
            top_bar, text="delete",
            width=72, height=34, corner_radius=10,
            font=_body_font(12, "bold"),
            fg_color=COLORS["recording_red"],
            hover_color=COLORS["recording_red_hover"],
            text_color="#FFFFFF",
            command=lambda: self._delete_note(full_note["id"])
        )
        del_btn.grid(row=0, column=1, sticky="e")

        # Note content
        content_text = ctk.CTkTextbox(
            self.detail_frame,
            font=_body_font(14),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            corner_radius=14,
            border_width=1,
            border_color=COLORS["border_light"],
            wrap="word"
        )
        content_text.grid(row=1, column=0, sticky="nsew", padx=36, pady=(0, 24))
        content_text.insert("1.0", full_note.get("text", ""))

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
                self.notes_scroll,
                text="no notes found.",
                font=_body_font(14),
                text_color=COLORS["text_muted"]
            ).grid(row=0, column=0, pady=50)
            return

        for i, note in enumerate(notes):
            card = NoteCard(self.notes_scroll, note, on_click=self._show_note_detail)
            card.grid(row=i, column=0, sticky="ew", pady=(0, 8))

    def set_recording(self, recording: bool):
        self.record_btn.set_recording(recording)
        if recording:
            self.status_label.configure(
                text="listening...",
                text_color=COLORS["recording_red"]
            )
        else:
            self.status_label.configure(
                text="press to record a new note",
                text_color=COLORS["text_muted"]
            )

    def set_processing(self):
        self.status_label.configure(
            text="processing...",
            text_color=COLORS["accent"]
        )

    def show_saved(self):
        self.status_label.configure(
            text="note saved!",
            text_color=COLORS["success"]
        )
        self.refresh_notes()


# ============================================================
# Main App Window
# ============================================================
class AppWindow(ctk.CTk):
    """Main application window - Seren-inspired dark therapeutic aesthetic."""

    def __init__(self):
        super().__init__()

        # Window setup
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("Not Whisper Flow")
        self.geometry("920x680")
        self.minsize(720, 520)
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

        # ===== SIDEBAR - Seren style =====
        sidebar = ctk.CTkFrame(
            self, width=230, fg_color=COLORS["bg_sidebar"], corner_radius=0,
            border_width=0
        )
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        # Subtle right border for sidebar
        border_line = ctk.CTkFrame(
            self, width=1, fg_color=COLORS["border_light"], corner_radius=0
        )
        border_line.grid(row=0, column=0, sticky="nse")

        # App title - Imbue display font
        title_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(28, 32))

        ctk.CTkLabel(
            title_frame, text="not whisper",
            font=_display_font(24),
            text_color=COLORS["accent"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame, text="flow",
            font=_display_font(24),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w")

        # Nav buttons
        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.grid(row=1, column=0, sticky="ew", padx=12)
        nav_frame.grid_columnconfigure(0, weight=1)

        self.btn_code = SidebarButton(
            nav_frame, text="Code Prompt", icon_text=">_",
            command=lambda: self._switch_page("code_prompt")
        )
        self.btn_code.grid(row=0, column=0, sticky="ew", pady=3)

        self.btn_notes = SidebarButton(
            nav_frame, text="Voice Notes", icon_text="~",
            command=lambda: self._switch_page("voice_notes")
        )
        self.btn_notes.grid(row=1, column=0, sticky="ew", pady=3)

        # Spacer
        sidebar.grid_rowconfigure(2, weight=1)

        # Bottom info - calm, muted
        info_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        info_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))

        ctk.CTkLabel(
            info_frame,
            text="100% local & private",
            font=_body_font(11),
            text_color=COLORS["text_muted"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            info_frame,
            text="ctrl+shift+space",
            font=_body_font(11),
            text_color=COLORS["text_muted"]
        ).pack(anchor="w", pady=(2, 0))

        # ===== CONTENT AREA =====
        self.content_frame = ctk.CTkFrame(
            self, fg_color=COLORS["bg_dark"], corner_radius=0
        )
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
