"""
Not Whisper Flow - Local Voice-to-Prompt Desktop App
Two modes:
  1. Code Prompt: speak a coding problem, get a polished prompt for AI assistants
  2. Voice Notes: speak to save notes/docs locally
"""

from threading import Thread, Event
import numpy as np
import pyperclip

from config import get_config
from utils.logger import setup_logger
from audio import AudioCapture, VoiceActivityDetector, preprocess_audio
from transcription import WhisperEngine
from slm import PromptEnhancer
from automation import HotkeyManager
from ui import AppWindow
from notes import NotesStore

logger = setup_logger(__name__)


class NotWhisperFlowApp:
    """Main application - wires backend to the desktop UI."""

    def __init__(self):
        logger.info("=" * 60)
        logger.info("Not Whisper Flow - Local Voice-to-Prompt")
        logger.info("=" * 60)

        self.config = get_config()

        # Audio pipeline
        self.audio_capture = AudioCapture(
            sample_rate=self.config.sample_rate,
            channels=self.config.get("channels", 1)
        )
        self.vad = VoiceActivityDetector(
            sample_rate=self.config.sample_rate,
            aggressiveness=self.config.get("vad_aggressiveness", 2)
        )

        # Whisper STT
        self.whisper = WhisperEngine(
            model_name=self.config.whisper_model,
            device=self.config.get("whisper_device", "auto")
        )

        # SLM prompt enhancer
        self.enhancer = PromptEnhancer(
            model_name=self.config.slm_model,
            use_slm=(self.config.enhancement_mode != "off"),
        )

        # Hotkeys
        self.hotkey_manager = HotkeyManager()

        # Voice notes storage
        self.notes_store = NotesStore(self.config.notes_directory)

        # Desktop UI
        self.window = AppWindow()
        self.window.on_record_toggle = self.toggle_recording
        self.window.on_copy_text = self.copy_to_clipboard
        self.window.on_quit = self.quit
        self.window.set_notes_store(self.notes_store)

        # State
        self.is_recording = Event()

        logger.info("All components initialized")

    def setup(self):
        """Load models and register hotkeys."""
        logger.info("Setting up...")

        # Load Whisper in background so UI appears fast
        def load_models():
            try:
                logger.info("Loading Whisper model...")
                self.whisper.load_model()
                logger.info("Whisper model ready")
            except Exception as e:
                logger.error(f"Failed to load Whisper: {e}")

        Thread(target=load_models, daemon=True).start()

        # Register global hotkey
        hotkey = self.config.get("hotkey_toggle_recording", "ctrl+shift+space")
        try:
            self.hotkey_manager.register(hotkey, self.toggle_recording, "Toggle recording")
            logger.info(f"Hotkey registered: {hotkey}")
        except Exception as e:
            logger.error(f"Failed to register hotkey: {e}")

        logger.info("Setup complete")

    def toggle_recording(self):
        if self.is_recording.is_set():
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.is_recording.is_set():
            return

        logger.info("Starting recording...")
        self.audio_capture.start()
        self.is_recording.set()
        self.window.set_recording(True)

    def stop_recording(self):
        if not self.is_recording.is_set():
            return

        logger.info("Stopping recording...")
        self.is_recording.clear()

        audio = self.audio_capture.get_all_audio()
        self.audio_capture.stop()

        self.window.set_recording(False)
        self.window.set_processing()

        # Process in background
        Thread(target=self._process_audio, args=(audio,), daemon=True).start()

    def _process_audio(self, audio: np.ndarray):
        """Process recorded audio through the pipeline."""
        try:
            if len(audio) == 0:
                logger.warning("No audio recorded")
                return

            # Preprocess
            processed = preprocess_audio(audio, sample_rate=self.config.sample_rate)

            # VAD
            speech_audio = self.vad.get_speech_audio(processed)
            if len(speech_audio) == 0:
                logger.warning("No speech detected")
                return

            # Transcribe
            logger.info("Transcribing...")
            result = self.whisper.transcribe(
                speech_audio,
                language=self.config.get("whisper_language")
            )
            raw_text = result.get("text", "").strip()

            if not raw_text:
                logger.warning("Empty transcription")
                return

            logger.info(f"Transcribed: '{raw_text}'")

            # Enhance based on which page is active
            current_mode = self.window.current_page
            enhanced = self.enhancer.enhance(raw_text, mode=current_mode)
            logger.info(f"Enhanced: '{enhanced[:100]}...'")

            # Update UI (schedule on main thread)
            if current_mode == "code_prompt":
                self.window.after(0, lambda: self.window.show_code_result(raw_text, enhanced))
            elif current_mode == "voice_notes":
                self.notes_store.save_note(raw_text, enhanced)
                self.window.after(0, self.window.show_note_saved)

        except Exception as e:
            logger.error(f"Error processing audio: {e}", exc_info=True)

    def copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        try:
            pyperclip.copy(text)
            logger.info(f"Copied to clipboard: '{text[:50]}...'")
        except Exception as e:
            logger.error(f"Failed to copy: {e}")

    def quit(self):
        logger.info("Quitting...")

        if self.is_recording.is_set():
            self.audio_capture.stop()

        self.hotkey_manager.unregister_all()
        logger.info("Goodbye!")

    def run(self):
        """Run the application."""
        self.setup()

        logger.info("Not Whisper Flow is running!")
        logger.info(f"Hotkey: {self.config.get('hotkey_toggle_recording', 'Ctrl+Shift+Space')}")

        # Run the desktop window (blocking)
        self.window.mainloop()


def main():
    try:
        app = NotWhisperFlowApp()
        app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
