"""
Configuration management for Not Whisper Flow.
Handles all user settings with JSON persistence.
"""

import json
from pathlib import Path
from typing import Dict, Any


class Config:
    """Manages application configuration with JSON persistence."""

    DEFAULT_CONFIG = {
        # App mode
        "app_mode": "code_prompt",  # code_prompt, voice_notes

        # Whisper settings
        "whisper_model": "base",  # tiny, base, small, medium, large
        "whisper_device": "auto",  # auto, cpu, cuda
        "whisper_language": None,  # None = auto-detect, or language code like "en"

        # SLM settings
        "slm_model": "qwen2.5-0.5b",  # smollm2-360m, qwen2.5-0.5b, qwen2.5-1.5b
        "slm_device": "cpu",  # auto, cpu, cuda
        "enhancement_mode": "preview",  # auto, preview, off

        # Audio settings
        "sample_rate": 16000,
        "channels": 1,
        "chunk_duration_ms": 30,
        "vad_aggressiveness": 2,  # 0-3

        # Hotkeys
        "hotkey_toggle_recording": "ctrl+shift+space",
        "hotkey_accept": "enter",
        "hotkey_cancel": "escape",

        # Automation settings
        "typing_speed_cps": 0,  # 0 = instant
        "use_clipboard_fallback": True,

        # UI settings
        "show_overlay": True,
        "overlay_position": {"x": 100, "y": 100},
        "show_tray_notifications": True,

        # Voice notes settings
        "notes_directory": None,  # None = default (~/.whisper_flow/notes/)

        # Ollama (local 7-8B agent brain)
        "ollama_model": "qwen2.5:7b",   # any model: llama3.1:8b, llama3.2:3b, etc.
        "ollama_url": "http://localhost:11434",
        "vision_model": "llava:7b",     # vision: llava:7b, minicpm-v, moondream

        # Advanced
        "enable_gpu": True,
        "model_cache_dir": "E:\\not_whisper_flow\\model_cache",
        "log_level": "INFO",
    }

    def __init__(self, config_path: str = None):
        if config_path is None:
            app_data = Path.home() / ".whisper_flow"
            app_data.mkdir(exist_ok=True)
            config_path = app_data / "config.json"

        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.load()

    def load(self):
        """Load configuration from file, or create default if not exists."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                self.config = {**self.DEFAULT_CONFIG, **loaded_config}
            except Exception as e:
                print(f"Error loading config: {e}. Using defaults.")
                self.config = self.DEFAULT_CONFIG.copy()
        else:
            self.config = self.DEFAULT_CONFIG.copy()
            self.save()

    def save(self):
        """Save current configuration to file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        self.save()

    def update(self, updates: Dict[str, Any]):
        self.config.update(updates)
        self.save()

    def reset_to_defaults(self):
        self.config = self.DEFAULT_CONFIG.copy()
        self.save()

    @property
    def whisper_model(self) -> str:
        return self.get("whisper_model")

    @property
    def slm_model(self) -> str:
        return self.get("slm_model")

    @property
    def enhancement_mode(self) -> str:
        return self.get("enhancement_mode")

    @property
    def sample_rate(self) -> int:
        return self.get("sample_rate")

    @property
    def show_overlay(self) -> bool:
        return self.get("show_overlay")

    @property
    def app_mode(self) -> str:
        return self.get("app_mode")

    @property
    def notes_directory(self) -> Path:
        custom = self.get("notes_directory")
        if custom:
            return Path(custom)
        return Path.home() / ".whisper_flow" / "notes"


_config_instance = None

def get_config() -> Config:
    """Get the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
