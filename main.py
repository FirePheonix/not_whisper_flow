"""
Not Whisper Flow - Local Voice-to-Prompt Desktop Agent

ClawBot-inspired architecture (100% local, 100% free):
  - Whisper STT  →  AgentRunner (SLM brain)  →  tool list
  - Tools executed serially: open_app, search_web, enhance_prompt, save_note, ...
  - JSONL session memory across interactions
  - SLM fallback: regex CommandRouter when model isn't loaded yet
"""

from threading import Thread, Event
import time
import numpy as np
import pyperclip

from config import get_config
from utils.logger import setup_logger
from audio import AudioCapture, VoiceActivityDetector, preprocess_audio
from transcription import WhisperEngine
from slm import PromptEnhancer, AgentRunner, ToolCall, OllamaClient
from automation import HotkeyManager, Commander, ContextCapture
from ui import AppWindow, TrayIcon, FloatingOverlay
from notes import NotesStore

logger = setup_logger(__name__)


class NotWhisperFlowApp:
    """Main application — wires voice pipeline to the desktop UI."""

    def __init__(self):
        logger.info("=" * 60)
        logger.info("Not Whisper Flow  ·  local agent")
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

        # SLM prompt enhancer (also owns the shared SLM model instance)
        self.enhancer = PromptEnhancer(
            model_name=self.config.slm_model,
            use_slm=(self.config.enhancement_mode != "off"),
        )

        # Ollama — primary agent brain (7-8B, native tool calling)
        self.ollama = OllamaClient(
            model=self.config.get("ollama_model", "qwen2.5:7b"),
            base_url=self.config.get("ollama_url", "http://localhost:11434"),
        )

        # AgentRunner — Ollama first, then SLM, then regex
        self.agent = AgentRunner(slm=self.enhancer.slm, ollama=self.ollama)

        # Commander — executes system tool calls
        self.commander = Commander()

        # Context capture — grabs foreground window + selected text before overlay
        self.context_capture = ContextCapture()
        self._pending_context = None

        # Hotkeys (optional — in-app buttons are primary)
        self.hotkey_manager = HotkeyManager()

        # Voice notes storage
        self.notes_store = NotesStore(self.config.notes_directory)

        # Desktop UI
        self.window = AppWindow()
        self.window.on_record_toggle = self.toggle_recording
        self.window.on_copy_text = self.copy_to_clipboard
        self.window.on_quit = self.quit
        self.window.set_notes_store(self.notes_store)

        # Floating overlay (Lemon-style listening card)
        self.overlay = FloatingOverlay(master=self.window)
        self.overlay.set_audio_source(self.audio_capture)

        # System tray
        self.tray = TrayIcon()
        self.tray.on_toggle_recording = self.toggle_recording
        self.tray.on_quit = self.quit
        self.tray.on_switch_mode = self._on_tray_mode_switch

        # State
        self.is_recording = Event()

        logger.info("All components initialized")

    def setup(self):
        """Load models in background and optionally register global hotkey."""
        logger.info("Setting up...")

        def load_models():
            try:
                logger.info("Loading Whisper model...")
                self.whisper.load_model()
                logger.info("Whisper ready")

                # Load Qwen so AgentRunner can think — not just enhance
                if self.enhancer.slm is not None:
                    logger.info("Loading Qwen for agent reasoning...")
                    self.enhancer.slm.load_model()
                    logger.info("Qwen ready — agent will use SLM for intent parsing")
            except Exception as e:
                logger.error(f"Failed to load models: {e}")

        Thread(target=load_models, daemon=True).start()

        # Tray icon runs in its own daemon thread (pystray.run() blocks)
        Thread(target=self.tray.run, daemon=True).start()
        logger.info("System tray started")

        # Global hotkey is optional — in-app orb + space bar are the primary controls
        hotkey = self.config.get("hotkey_toggle_recording", "ctrl+shift+space")
        try:
            self.hotkey_manager.register(hotkey, self.toggle_recording, "Toggle recording")
            logger.info(f"Global hotkey registered: {hotkey}")
        except Exception as e:
            logger.warning(f"Global hotkey unavailable ({e}) — use the in-app button or Space bar")

        logger.info("Setup complete")

    # ── Recording control ──────────────────────────────────────

    def toggle_recording(self):
        if self.is_recording.is_set():
            self.stop_recording()
        else:
            # Capture desktop context BEFORE the overlay steals focus
            self._pending_context = self.context_capture.capture()
            self.start_recording()

    def start_recording(self):
        if self.is_recording.is_set():
            return
        logger.info("Recording started")
        self.audio_capture.start()
        self.is_recording.set()
        self.window.set_recording(True)
        self.tray.set_recording_state(True)
        self.overlay.show_listening()

    def stop_recording(self):
        if not self.is_recording.is_set():
            return
        logger.info("Recording stopped")
        self.is_recording.clear()

        audio = self.audio_capture.get_all_audio()
        self.audio_capture.stop()

        self.window.set_recording(False)
        self.tray.set_recording_state(False)
        self.window.set_processing()
        self.overlay.show_processing()

        ctx = self._pending_context
        self._pending_context = None
        Thread(target=self._process_audio, args=(audio, ctx), daemon=True).start()

    # ── Audio processing pipeline ──────────────────────────────

    def _process_audio(self, audio: np.ndarray, context=None):
        """
        Full pipeline (runs in background thread):
          audio → preprocess → VAD → Whisper → AgentRunner → serial tool execution
        """
        try:
            if len(audio) == 0:
                logger.warning("No audio captured")
                self.overlay.dismiss()
                return

            # 1. Preprocess
            processed = preprocess_audio(audio, sample_rate=self.config.sample_rate)

            # 2. VAD — filter silence
            speech_audio = self.vad.get_speech_audio(processed)
            if len(speech_audio) == 0:
                logger.warning("No speech detected")
                self.overlay.dismiss()
                return

            # 3. Transcribe
            logger.info("Transcribing...")
            result = self.whisper.transcribe(
                speech_audio,
                language=self.config.get("whisper_language")
            )
            raw_text = result.get("text", "").strip()

            if not raw_text:
                logger.warning("Empty transcription")
                self.overlay.dismiss()
                return

            logger.info(f"Transcribed: '{raw_text}'")

            # 4. AgentRunner → tool call list (pass desktop context to Ollama)
            current_mode = self.window.current_page
            agent_result = self.agent.parse(raw_text, mode=current_mode, context=context)

            logger.info(
                f"Agent[{agent_result.backend}]→ {len(agent_result.calls)} call(s): "
                f"{[str(c) for c in agent_result.calls]}"
            )

            # 5. Execute tool calls serially (ClawBot lane pattern)
            prev_tc = None
            for tc in agent_result.calls:
                self._execute_tool(tc, raw_text, prev_tc=prev_tc, context=context)
                prev_tc = tc

        except Exception as e:
            logger.error(f"Processing error: {e}", exc_info=True)

    # Apps that take longer to launch before they can accept input
    _SLOW_APPS = {"powershell", "cmd", "wt", "windows terminal", "terminal",
                  "code", "cursor", "word", "excel", "powerpoint"}
    _TERMINAL_APPS = {"powershell", "cmd", "wt", "windows terminal", "terminal"}

    def _execute_tool(self, tc: ToolCall, raw_text: str, prev_tc: ToolCall = None, context=None):
        """
        Dispatch a single tool call. Runs in the processing thread.

        prev_tc: the ToolCall that ran immediately before this one.
                 Used to add launch-delay when typing into a freshly opened app.
        """

        # ── enhance_prompt ────────────────────────────────────
        if tc.tool == "enhance_prompt":
            text = tc.args.get("text", raw_text)
            enhanced = self.enhancer.enhance(text, mode="code_prompt")
            logger.info(f"Enhanced: '{enhanced[:80]}...'")
            self.window.after(
                0,
                lambda r=raw_text, e=enhanced: self.window.show_code_result(r, e)
            )
            self.overlay.show_result(raw_text, enhanced, success=True)

        # ── save_note ─────────────────────────────────────────
        elif tc.tool == "save_note":
            text = tc.args.get("text", raw_text)
            cleaned = self.enhancer.enhance(text, mode="voice_notes")
            self.notes_store.save_note(text, cleaned)
            logger.info("Note saved")
            self.window.after(0, self.window.show_note_saved)
            self.overlay.show_result(raw_text, "Note saved.", success=True)

        # ── respond (direct AI answer / summary / explanation) ─
        elif tc.tool == "respond":
            message = tc.args.get("text", "")
            logger.info(f"Respond: '{message[:80]}...'")
            self.overlay.show_result(raw_text, message, success=True)

        # ── screenshot_and_describe (vision or text) ──────────
        elif tc.tool == "screenshot_and_describe":
            query = tc.args.get("query", raw_text)
            try:
                # If selected text is available, use text query — no vision needed
                if context and context.selected_text:
                    logger.info(f"Text query (selected text, {len(context.selected_text)} chars): '{query}'")
                    response = self.ollama.text_query(query, context.selected_text)
                    if response:
                        self.overlay.show_result(raw_text, response, success=True)
                    else:
                        self.overlay.show_result(raw_text, "Couldn't get a response — is Ollama running?", success=False)
                else:
                    # No selected text — fall back to vision model
                    logger.info(f"Vision query: '{query}'")
                    from PIL import ImageGrab
                    screenshot = ImageGrab.grab()
                    vision_model = self.config.get("vision_model", "llava:7b")
                    response = self.ollama.vision_query(query, screenshot, model=vision_model)
                    if response:
                        logger.info(f"Vision response: '{response[:80]}...'")
                        self.overlay.show_result(raw_text, response, success=True)
                    else:
                        msg = f"Vision model unavailable — run: ollama pull {vision_model}"
                        logger.warning(msg)
                        self.overlay.show_result(raw_text, msg, success=False)
            except Exception as e:
                logger.error(f"Screen query failed: {e}", exc_info=True)
                self.overlay.show_result(raw_text, f"Error: {e}", success=False)

        # ── system commands via Commander ─────────────────────
        else:
            action = tc.tool
            args   = tc.args

            # If we're about to type into a freshly opened app, wait for it
            if action == "type_text" and prev_tc and prev_tc.tool == "open_app":
                opened_app = prev_tc.args.get("app", "").lower()
                delay = 3.0 if opened_app in self._SLOW_APPS else 1.5
                logger.info(f"Waiting {delay}s for '{opened_app}' to be ready...")
                time.sleep(delay)

            if action == "open_app":
                target = args.get("app", "")
            elif action == "close_app":
                target = args.get("app", "")
            elif action == "search_web":
                target = args.get("query", "")
            elif action == "media_control":
                target = args.get("action", "")
            elif action == "type_text":
                target = args.get("text", "")
            else:
                target = args.get("target", str(args))

            success, message = self.commander.execute(action, target)
            logger.info(f"Commander: {action}('{target}') → success={success}, {message}")

            # Press Enter after typing if Ollama requested it or we're in a terminal
            if action == "type_text" and success:
                send_enter = args.get("send_enter", False)
                if not send_enter and prev_tc and prev_tc.tool == "open_app":
                    opened_app = prev_tc.args.get("app", "").lower()
                    send_enter = opened_app in self._TERMINAL_APPS
                if send_enter:
                    try:
                        import keyboard
                        time.sleep(0.15)
                        keyboard.send("enter")
                        logger.info("Enter sent — command executed")
                    except Exception as e:
                        logger.warning(f"Could not send Enter: {e}")

            self.window.after(
                0,
                lambda s=success, m=message, a=action, t=target:
                    self.window.show_command_result(s, m, a, t, raw_text)
            )
            self.overlay.show_result(raw_text, message, success=success)

    # ── Helpers ───────────────────────────────────────────────

    def _on_tray_mode_switch(self, mode: str):
        """Called from the tray icon when the user switches mode via the menu."""
        self.window.after(0, lambda m=mode: self.window._switch_page(m))

    def copy_to_clipboard(self, text: str):
        try:
            pyperclip.copy(text)
            logger.info(f"Clipboard: '{text[:50]}...'")
        except Exception as e:
            logger.error(f"Clipboard failed: {e}")

    def quit(self):
        logger.info("Quitting...")
        if self.is_recording.is_set():
            self.audio_capture.stop()
        self.hotkey_manager.unregister_all()
        self.tray.stop()
        self.overlay.dismiss()
        logger.info("Goodbye!")

    def run(self):
        self.setup()
        logger.info("Not Whisper Flow is running!")
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
