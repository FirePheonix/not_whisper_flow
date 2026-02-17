"""
Font loader for the application.
Downloads and registers Imbue (display) and Inter (body) from Google Fonts.
Works on Windows by loading fonts into the current session via ctypes.
"""

import os
import sys
import urllib.request
import zipfile
import tempfile
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Font storage directory
FONTS_DIR = Path(__file__).parent / "fonts_data"

# Google Fonts direct download URLs (static TTF)
FONT_URLS = {
    "Imbue": "https://fonts.google.com/download?family=Imbue",
    "Inter": "https://fonts.google.com/download?family=Inter",
}

# Font file names we look for after extraction
FONT_FILES = {
    "Imbue": "Imbue-Regular.ttf",
    "Inter": "Inter-Regular.ttf",
}

# Fallback font families if custom fonts aren't available
FALLBACK_DISPLAY = "Georgia"
FALLBACK_BODY = "Segoe UI"

# Track loaded font names
_loaded_fonts = {}


def _ensure_fonts_dir():
    """Create fonts directory if needed."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)


def _find_font_file(family: str, style: str = "Regular") -> str | None:
    """Find a font file in the fonts directory."""
    if not FONTS_DIR.exists():
        return None

    # Search recursively for matching font files
    patterns = [
        f"{family}-{style}.ttf",
        f"{family}_{style}.ttf",
        f"{family[0].upper()}{family[1:]}-{style}.ttf",
    ]

    for root, dirs, files in os.walk(FONTS_DIR):
        for f in files:
            if not f.endswith(".ttf"):
                continue
            for pattern in patterns:
                if f.lower() == pattern.lower():
                    return os.path.join(root, f)
            # Also match partial - e.g. "Imbue_18pt-Regular.ttf"
            if family.lower() in f.lower() and style.lower() in f.lower() and f.endswith(".ttf"):
                return os.path.join(root, f)

    return None


def _download_font(family: str) -> bool:
    """Download a font family from Google Fonts."""
    url = FONT_URLS.get(family)
    if not url:
        return False

    try:
        logger.info(f"Downloading {family} font...")
        _ensure_fonts_dir()

        # Download the zip
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            urllib.request.urlretrieve(url, tmp.name)
            tmp_path = tmp.name

        # Extract
        family_dir = FONTS_DIR / family
        family_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(tmp_path, 'r') as zf:
            for member in zf.namelist():
                if member.endswith('.ttf'):
                    # Extract just the font files
                    data = zf.read(member)
                    filename = os.path.basename(member)
                    with open(family_dir / filename, 'wb') as out:
                        out.write(data)

        os.unlink(tmp_path)
        logger.info(f"{family} font downloaded successfully")
        return True

    except Exception as e:
        logger.warning(f"Failed to download {family} font: {e}")
        return False


def _register_font_windows(font_path: str) -> bool:
    """Register a font on Windows for the current session."""
    if sys.platform != "win32":
        return False

    try:
        import ctypes
        # AddFontResourceExW with FR_PRIVATE flag (0x10)
        result = ctypes.windll.gdi32.AddFontResourceExW(font_path, 0x10, 0)
        if result > 0:
            logger.info(f"Registered font: {os.path.basename(font_path)}")
            return True
        else:
            logger.warning(f"Failed to register font: {font_path}")
            return False
    except Exception as e:
        logger.warning(f"Font registration error: {e}")
        return False


def load_fonts() -> dict:
    """
    Load Imbue and Inter fonts. Downloads if not present.
    Returns dict with font family names to use.
    """
    global _loaded_fonts

    if _loaded_fonts:
        return _loaded_fonts

    result = {
        "display": FALLBACK_DISPLAY,  # For headings (Imbue)
        "body": FALLBACK_BODY,        # For body text (Inter)
    }

    for family, target_key in [("Imbue", "display"), ("Inter", "body")]:
        font_path = _find_font_file(family)

        if not font_path:
            _download_font(family)
            font_path = _find_font_file(family)

        if font_path and sys.platform == "win32":
            if _register_font_windows(font_path):
                # Use the font family name (not filename)
                result[target_key] = family

    _loaded_fonts = result
    logger.info(f"Font config: display={result['display']}, body={result['body']}")
    return result


def get_display_font() -> str:
    """Get the display/heading font family name."""
    fonts = load_fonts()
    return fonts["display"]


def get_body_font() -> str:
    """Get the body text font family name."""
    fonts = load_fonts()
    return fonts["body"]
