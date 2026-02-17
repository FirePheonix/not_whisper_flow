"""
System tray icon and menu with mode switching.
"""

import pystray
from PIL import Image, ImageDraw
from typing import Callable, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


class TrayIcon:
    """System tray icon with menu and mode switching."""

    def __init__(self, app_name: str = "Not Whisper Flow"):
        self.app_name = app_name
        self.icon: Optional[pystray.Icon] = None

        # Callbacks
        self.on_toggle_recording: Optional[Callable] = None
        self.on_settings: Optional[Callable] = None
        self.on_quit: Optional[Callable] = None
        self.on_switch_mode: Optional[Callable[[str], None]] = None

        # State
        self.is_recording = False
        self.current_mode = "code_prompt"

        logger.info("TrayIcon initialized")

    def _create_icon_image(self, recording: bool = False) -> Image.Image:
        size = 64
        image = Image.new('RGB', (size, size), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)

        if recording:
            color = (184, 120, 120)  # Muted red when recording
        elif self.current_mode == "voice_notes":
            color = (125, 168, 136)  # Soft green for notes mode
        else:
            color = (27, 185, 206)   # Seren cyan for code prompt mode

        # Mic body
        draw.ellipse([20, 15, 44, 40], fill=color)
        draw.rectangle([20, 25, 44, 40], fill=color)

        # Mic stand
        draw.rectangle([30, 40, 34, 50], fill=color)
        draw.ellipse([24, 48, 40, 54], fill=color)

        return image

    def _create_menu(self):
        recording_text = "Stop Recording" if self.is_recording else "Start Recording"
        mode_text = "Voice Notes" if self.current_mode == "code_prompt" else "Code Prompt"

        return pystray.Menu(
            pystray.MenuItem(
                recording_text,
                self._on_toggle_recording_clicked
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                f"Current: {'Code Prompt' if self.current_mode == 'code_prompt' else 'Voice Notes'}",
                None,
                enabled=False
            ),
            pystray.MenuItem(
                f"Switch to {mode_text}",
                self._on_switch_mode_clicked
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Quit",
                self._on_quit_clicked
            ),
        )

    def _on_toggle_recording_clicked(self, icon, item):
        if self.on_toggle_recording:
            self.on_toggle_recording()

    def _on_switch_mode_clicked(self, icon, item):
        new_mode = "voice_notes" if self.current_mode == "code_prompt" else "code_prompt"
        self.current_mode = new_mode
        if self.on_switch_mode:
            self.on_switch_mode(new_mode)
        self._update_icon()

    def _on_quit_clicked(self, icon, item):
        if self.on_quit:
            self.on_quit()
        self.stop()

    def _update_icon(self):
        """Update icon image and menu."""
        if self.icon:
            self.icon.icon = self._create_icon_image(self.is_recording)
            self.icon.menu = self._create_menu()

    def set_recording_state(self, recording: bool):
        self.is_recording = recording
        self._update_icon()
        logger.debug(f"Tray: recording={recording}")

    def set_mode(self, mode: str):
        self.current_mode = mode
        self._update_icon()
        logger.debug(f"Tray: mode={mode}")

    def show_notification(self, title: str, message: str):
        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception as e:
                logger.warning(f"Failed to show notification: {e}")

    def run(self):
        """Run the tray icon (blocking)."""
        self.icon = pystray.Icon(
            self.app_name,
            self._create_icon_image(False),
            self.app_name,
            self._create_menu()
        )
        logger.info("Starting tray icon...")
        self.icon.run()

    def stop(self):
        if self.icon:
            self.icon.stop()
            logger.info("Tray icon stopped")
