# Not Whisper Flow

![WhatsApp Image 2026-02-17 at 21 52 46](https://github.com/user-attachments/assets/f0f54be5-9992-4f0f-a02b-c8b6ab0d2ce2)

100% local, free, open-source voice-to-prompt tool. Speak your coding problem, get a polished prompt for AI assistants. Or use it as a voice notes dictionary.

## What It Does

**Two modes:**

1. **Code Prompt Mode** - Speak a rough description of what you want to build/fix/debug. The app transcribes it with Whisper and uses a local SLM to turn it into a clean, structured prompt you can paste into Claude, ChatGPT, Cursor, etc.

2. **Voice Notes Mode** - Speak to save notes, docs, and knowledge snippets. Builds a searchable local knowledge base from your voice.

**Everything runs locally. No API keys. No cloud. No cost.**

## Requirements

- Python 3.8+
- FFmpeg (for Whisper)
- ~6 GB disk space (for models)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# First-time setup (downloads models)
python -m utils.installer

# Run
python main.py
```

Or on Windows, just double-click `start.bat`.

## Usage

1. Press **Ctrl+Shift+Space** to start recording
2. Speak your coding problem or note
3. Press **Ctrl+Shift+Space** again to stop
4. Preview the enhanced prompt in the overlay
5. Press **Enter** to accept and auto-type, or **Esc** to cancel

Switch between Code Prompt and Voice Notes mode via the system tray menu.

## Models

| Model | Size | Speed | Use Case |
|-------|------|-------|----------|
| Whisper base | ~140 MB | Fast | Speech-to-text (default) |
| Whisper tiny | ~75 MB | Fastest | Lower accuracy, faster |
| Qwen2.5-0.5B | ~1 GB | Good on CPU | Prompt enhancement (default) |
| Qwen2.5-1.5B | ~3 GB | Slower on CPU | Better quality prompts |
| SmolLM2-360M | ~720 MB | Fastest on CPU | Lightest option |

## Configuration

Settings are stored in `~/.whisper_flow/config.json`. Key options:

| Setting | Default | Options |
|---------|---------|---------|
| `app_mode` | `code_prompt` | `code_prompt`, `voice_notes` |
| `whisper_model` | `base` | `tiny`, `base`, `small`, `medium`, `large` |
| `slm_model` | `qwen2.5-0.5b` | `smollm2-360m`, `qwen2.5-0.5b`, `qwen2.5-1.5b` |
| `enhancement_mode` | `preview` | `auto`, `preview`, `off` |
| `hotkey_toggle_recording` | `ctrl+shift+space` | Any key combo |

## Project Structure

```
not_whisper_flow/
├── main.py              # App orchestrator
├── config.py            # JSON-persisted settings
├── audio/               # Mic capture, preprocessing, VAD
├── transcription/       # Whisper STT engine
├── slm/                 # Local SLM prompt enhancement
├── notes/               # Voice notes storage
├── automation/          # Hotkeys + auto-typing
├── ui/                  # System tray + overlay window
└── utils/               # Logger + installer
```

## License

Open source. Free to use.
