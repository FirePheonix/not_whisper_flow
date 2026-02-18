"""
First-time setup and installation helper.
"""

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import setup_logger

logger = setup_logger(__name__)


def check_ffmpeg():
    """Check if FFmpeg is installed."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            logger.info("FFmpeg is installed")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    logger.warning("FFmpeg not found")
    return False


def check_cuda():
    """Check if CUDA is available."""
    try:
        import torch
        if torch.cuda.is_available():
            logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
            return True
        else:
            logger.info("CUDA not available (will use CPU)")
            return False
    except ImportError:
        logger.warning("PyTorch not installed yet")
        return False


def download_whisper_model(model_name: str = "base"):
    """Download Whisper model."""
    try:
        import whisper
        logger.info(f"Downloading Whisper {model_name} model...")
        model = whisper.load_model(model_name)
        logger.info(f"Whisper {model_name} model downloaded")
        del model
        return True
    except Exception as e:
        logger.error(f"Failed to download Whisper model: {e}")
        return False


def download_slm_model(model_name: str = "qwen2.5-0.5b"):
    """Download SLM model."""
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM

        model_ids = {
            "smollm2-360m": "HuggingFaceTB/SmolLM2-360M-Instruct",
            "qwen2.5-0.5b": "Qwen/Qwen2.5-0.5B-Instruct",
            "qwen2.5-1.5b": "Qwen/Qwen2.5-1.5B-Instruct",
        }

        model_id = model_ids.get(model_name, model_ids["qwen2.5-0.5b"])

        from config import get_config
        config = get_config()
        cache_dir = config.get("model_cache_dir")

        logger.info(f"Downloading {model_name} ({model_id})...")
        logger.info(f"Using cache directory: {cache_dir}")
        logger.info("This may take a while...")

        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, cache_dir=cache_dir)
        model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, cache_dir=cache_dir)

        logger.info(f"{model_name} model downloaded")

        del tokenizer
        del model
        return True

    except Exception as e:
        logger.error(f"Failed to download SLM model: {e}")
        return False


def test_microphone():
    """Test microphone."""
    try:
        from audio.capture import AudioCapture
        logger.info("Testing microphone...")
        AudioCapture.test_microphone(duration=2.0)
        return True
    except Exception as e:
        logger.error(f"Microphone test failed: {e}")
        return False


def create_default_config():
    """Create default configuration file."""
    try:
        from config import get_config
        config = get_config()
        config.save()
        logger.info(f"Configuration file created: {config.config_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create config: {e}")
        return False


def main():
    """Run installation and setup."""
    print("=" * 60)
    print("Not Whisper Flow - First-Time Setup")
    print("=" * 60)
    print()

    print("1. Checking FFmpeg...")
    if not check_ffmpeg():
        print("\n  FFmpeg is required for Whisper!")
        print("  Install: choco install ffmpeg")
        print("  Or download from: https://ffmpeg.org/download.html")
        print()
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    print()

    print("2. Checking CUDA...")
    has_cuda = check_cuda()
    if not has_cuda:
        print("   Note: Without CUDA, models run on CPU (slower but works fine)")
    print()

    print("3. Creating configuration...")
    create_default_config()
    print()

    print("4. Downloading models...")
    print()

    print("   a) Whisper base model (~140 MB)...")
    download_whisper_model("base")
    print()

    print("   b) SLM model (Qwen2.5-0.5B ~1 GB)...")
    print("      Small, CPU-friendly model for prompt enhancement")
    download_slm_model("qwen2.5-0.5b")
    print()

    print("5. Testing microphone...")
    print("   Speak for 2 seconds when prompted...")
    test_microphone()
    print()

    print("=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print()
    print("To start: python main.py")
    print("Hotkey: Ctrl+Shift+Space")
    print("Modes: Code Prompt (default), Voice Notes (switch via tray)")
    print()


if __name__ == "__main__":
    main()
