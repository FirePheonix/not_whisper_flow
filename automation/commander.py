"""
System command execution module.
Handles opening/closing applications, web searches, media controls, and text typing.

Launch strategy (same as OpenClaw / Windows Shell):
  1. Protocol URI  → os.startfile() (ms-settings:, etc.)
  2. Registry      → HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}.exe
  3. Known paths   → Hardcoded fallback install directories
  4. ShellExecuteW → Windows Shell API (handles PATH + registered apps)
  5. start cmd     → Last resort shell start
"""

import os
import sys
import subprocess
import webbrowser
import platform
import time
from utils.logger import setup_logger

logger = setup_logger(__name__)


# App name  →  exe stem (no path, no .exe extension)
# Registry lookup will resolve these to full paths
_APP_EXE = {
    # Browsers
    "chrome":               "chrome",
    "google chrome":        "chrome",
    "firefox":              "firefox",
    "firefox browser":      "firefox",
    "edge":                 "msedge",
    "microsoft edge":       "msedge",
    "brave":                "brave",
    "opera":                "opera",
    "opera gx":             "opera",

    # Code editors
    "vs code":              "code",
    "vscode":               "code",
    "visual studio code":   "code",
    "code":                 "code",
    "cursor":               "cursor",
    "sublime":              "sublime_text",
    "sublime text":         "sublime_text",
    "notepad":              "notepad",
    "notepad plus":         "notepad++",
    "notepad++":            "notepad++",

    # System tools (these live in System32 - always found via PATH)
    "explorer":             "explorer",
    "file explorer":        "explorer",
    "files":                "explorer",
    "calculator":           "calc",
    "calc":                 "calc",
    "paint":                "mspaint",
    "snip":                 "SnippingTool",
    "snipping tool":        "SnippingTool",
    "task manager":         "Taskmgr",
    "control panel":        "control",
    "cmd":                  "cmd",
    "command prompt":       "cmd",
    "powershell":           "powershell",
    "terminal":             "wt",
    "windows terminal":     "wt",

    # Protocol URIs - handled via os.startfile()
    "settings":             "ms-settings:",
    "photos":               "ms-photos:",
    "teams":                "ms-teams:",
    "microsoft teams":      "ms-teams:",

    # Media
    "spotify":              "Spotify",
    "vlc":                  "vlc",
    "media player":         "wmplayer",

    # Communication
    "discord":              "Discord",
    "slack":                "slack",
    "zoom":                 "Zoom",
    "telegram":             "Telegram",
    "whatsapp":             "WhatsApp",

    # Productivity
    "word":                 "WINWORD",
    "excel":                "EXCEL",
    "powerpoint":           "POWERPNT",
    "outlook":              "OUTLOOK",
    "onenote":              "ONENOTE",
    "notion":               "Notion",
    "obsidian":             "Obsidian",

    # Creative
    "figma":                "Figma",
    "photoshop":            "Photoshop",

    # Other
    "steam":                "steam",
    "github desktop":       "GitHubDesktop",
    "postman":              "Postman",
}

# Known install paths as final fallback (checked if registry + ShellExecute fail)
_FALLBACK_PATHS = {
    "chrome": [
        r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
        r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    ],
    "msedge": [
        r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
        r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
    ],
    "firefox": [
        r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe",
        r"%PROGRAMFILES(X86)%\Mozilla Firefox\firefox.exe",
    ],
    "brave": [
        r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
    ],
    "Spotify": [
        r"%APPDATA%\Spotify\Spotify.exe",
        r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe",
    ],
    "Discord": [
        r"%LOCALAPPDATA%\Discord\Update.exe",  # Discord uses Update.exe --processStart
        r"%LOCALAPPDATA%\Discord\app-*\Discord.exe",
    ],
    "Notion": [
        r"%LOCALAPPDATA%\Programs\Notion\Notion.exe",
    ],
    "Obsidian": [
        r"%LOCALAPPDATA%\Programs\obsidian\Obsidian.exe",
    ],
    "wt": [
        r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe",
    ],
}

# Process names for taskkill
_PROCESS_NAMES = {
    "chrome":               "chrome.exe",
    "google chrome":        "chrome.exe",
    "firefox":              "firefox.exe",
    "edge":                 "msedge.exe",
    "microsoft edge":       "msedge.exe",
    "vs code":              "Code.exe",
    "vscode":               "Code.exe",
    "visual studio code":   "Code.exe",
    "cursor":               "cursor.exe",
    "notepad":              "notepad.exe",
    "spotify":              "Spotify.exe",
    "discord":              "Discord.exe",
    "slack":                "slack.exe",
    "zoom":                 "Zoom.exe",
    "teams":                "Teams.exe",
    "explorer":             "explorer.exe",
    "calculator":           "CalculatorApp.exe",
    "vlc":                  "vlc.exe",
    "steam":                "steam.exe",
}


# ======================================================================
# Windows registry app path lookup
# ======================================================================
def _find_via_registry(exe_stem: str) -> str | None:
    """
    Look up an app's full path via Windows App Paths registry key.
    HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe}.exe
    """
    if sys.platform != "win32":
        return None
    try:
        import winreg
        key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_stem}.exe"
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, key_path) as k:
                    path = winreg.QueryValue(k, None).strip('"').strip()
                    if path and os.path.exists(path):
                        return path
            except FileNotFoundError:
                continue
    except Exception as e:
        logger.debug(f"Registry lookup failed for {exe_stem}: {e}")
    return None


def _find_via_known_paths(exe_stem: str) -> str | None:
    """Check hardcoded fallback installation directories."""
    for pattern in _FALLBACK_PATHS.get(exe_stem, []):
        expanded = os.path.expandvars(pattern)
        # Handle wildcard paths (e.g. app-* for Discord)
        if "*" in expanded:
            import glob
            matches = glob.glob(expanded)
            if matches:
                return matches[-1]  # most recent version
        elif os.path.exists(expanded):
            return expanded
    return None


def _shell_execute(target: str) -> bool:
    """
    Use Windows ShellExecuteW - same mechanism as double-clicking in Explorer.
    Returns True if Windows accepted the call (SW_SHOWNORMAL = 1).
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        result = ctypes.windll.shell32.ShellExecuteW(
            None,   # hwnd
            "open", # verb
            target, # file/app/uri
            None,   # params
            None,   # working dir
            1       # SW_SHOWNORMAL
        )
        # ShellExecuteW returns > 32 on success
        return int(result) > 32
    except Exception as e:
        logger.debug(f"ShellExecuteW failed: {e}")
        return False


# ======================================================================
# Commander
# ======================================================================
class Commander:
    """Executes system commands based on routed voice intent."""

    def __init__(self):
        self.os_type = platform.system().lower()
        logger.info(f"Commander initialized on {self.os_type}")

    def execute(self, action: str, target: str = "") -> tuple:
        """
        Execute a command.

        Args:
            action: "open_app" | "close_app" | "search_web" | "media_control" | "type_text"
            target: app name, search query, media key name, or text to type

        Returns:
            (success: bool, message: str)
        """
        logger.info(f"Commander: {action} → '{target}'")
        try:
            if action == "open_app":
                return self._open_app(target)
            elif action == "close_app":
                return self._close_app(target)
            elif action == "search_web":
                return self._search_web(target)
            elif action == "media_control":
                return self._media_control(target)
            elif action == "type_text":
                return self._type_text(target)
            else:
                logger.warning(f"Unknown action: {action}")
                return False, f"unknown action: {action}"
        except Exception as e:
            logger.error(f"Commander failed: {e}")
            return False, str(e)

    # ------------------------------------------------------------------
    def _open_app(self, app_name: str) -> tuple:
        key = app_name.lower().strip()
        exe_stem = _APP_EXE.get(key, key)

        logger.info(f"Open app: '{app_name}' → exe_stem='{exe_stem}'")

        if self.os_type == "windows":

            # --- 1. Protocol URIs (ms-settings:, ms-photos:, etc.) ---
            if ":" in exe_stem and not exe_stem.endswith(".exe"):
                try:
                    os.startfile(exe_stem)
                    return True, f"opening {app_name}"
                except Exception as e:
                    return False, f"failed to open {app_name}: {e}"

            # --- 2. Registry App Paths lookup ---
            path = _find_via_registry(exe_stem)
            if path:
                logger.info(f"Registry resolved: {path}")
                subprocess.Popen([path])
                return True, f"opening {app_name}"

            # --- 3. Known fallback install paths ---
            path = _find_via_known_paths(exe_stem)
            if path:
                logger.info(f"Fallback path resolved: {path}")
                # Discord needs special handling
                if "Discord" in path and "Update.exe" in path:
                    subprocess.Popen([path, "--processStart", "Discord.exe"])
                else:
                    subprocess.Popen([path])
                return True, f"opening {app_name}"

            # --- 4. ShellExecuteW (handles apps registered in Windows Shell) ---
            if _shell_execute(exe_stem):
                logger.info(f"ShellExecuteW succeeded for: {exe_stem}")
                return True, f"opening {app_name}"

            # Try with .exe suffix too
            if _shell_execute(exe_stem + ".exe"):
                return True, f"opening {app_name}"

            # --- 5. Last resort: start command (no quotes around exe name) ---
            logger.info(f"Last resort: start {exe_stem}")
            subprocess.Popen(f"start {exe_stem}", shell=True)
            return True, f"opening {app_name} (may take a moment)"

        elif self.os_type == "darwin":
            subprocess.Popen(["open", "-a", app_name])
            return True, f"opening {app_name}"

        else:
            subprocess.Popen([app_name.lower()])
            return True, f"opening {app_name}"

    def _close_app(self, app_name: str) -> tuple:
        key = app_name.lower().strip()

        if self.os_type == "windows":
            proc = _PROCESS_NAMES.get(key, key.replace(" ", "") + ".exe")
            result = subprocess.run(
                ["taskkill", "/F", "/IM", proc],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return True, f"closed {app_name}"
            return False, f"could not close {app_name} — is it open?"

        elif self.os_type == "darwin":
            subprocess.run(["pkill", "-x", app_name], capture_output=True)
            return True, f"closed {app_name}"

        else:
            subprocess.run(["pkill", app_name.lower()], capture_output=True)
            return True, f"closed {app_name}"

    def _search_web(self, query: str) -> tuple:
        import urllib.parse
        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
        webbrowser.open(url)
        return True, f"searching: {query}"

    def _media_control(self, action: str) -> tuple:
        if self.os_type != "windows":
            return False, "media control only available on Windows"
        try:
            import ctypes
            VK_MEDIA = {
                "play":        0xB3,  # VK_MEDIA_PLAY_PAUSE
                "pause":       0xB3,
                "stop":        0xB2,  # VK_MEDIA_STOP
                "next":        0xB0,  # VK_MEDIA_NEXT_TRACK
                "previous":    0xB1,  # VK_MEDIA_PREV_TRACK
                "volume_up":   0xAF,  # VK_VOLUME_UP
                "volume_down": 0xAE,  # VK_VOLUME_DOWN
                "mute":        0xAD,  # VK_VOLUME_MUTE
                "unmute":      0xAD,
            }
            vk = VK_MEDIA.get(action)
            if vk:
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.05)
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # KEYEVENTF_KEYUP
                return True, f"media: {action}"
            return False, f"unknown media action: {action}"
        except Exception as e:
            return False, f"media control failed: {e}"

    def _type_text(self, text: str) -> tuple:
        try:
            import pyperclip
            import keyboard as kb
            pyperclip.copy(text)
            time.sleep(0.15)
            kb.send("ctrl+v")
            preview = text[:40] + ("..." if len(text) > 40 else "")
            return True, f"typed: {preview}"
        except Exception as e:
            return False, f"failed to type: {e}"
