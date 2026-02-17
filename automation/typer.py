"""
Auto-typing functionality to insert text into applications.
"""

import time
from pynput.keyboard import Controller, Key
import pyperclip
from utils.logger import setup_logger

logger = setup_logger(__name__)


class AutoTyper:
    """Automatically types text into the active application."""
    
    def __init__(self, 
                 typing_speed_cps: int = 0,
                 use_clipboard_fallback: bool = True):
        """Initialize auto-typer.
        
        Args:
            typing_speed_cps: Typing speed in characters per second (0 = instant)
            use_clipboard_fallback: Use clipboard for problematic apps
        """
        self.typing_speed_cps = typing_speed_cps
        self.use_clipboard_fallback = use_clipboard_fallback
        
        self.keyboard = Controller()
        
        logger.info(f"AutoTyper initialized (speed: {typing_speed_cps} cps)")
    
    def type_text(self, text: str, use_clipboard: bool = False):
        """Type text into the active application.
        
        Args:
            text: Text to type
            use_clipboard: Force clipboard method
        """
        if not text:
            logger.warning("Empty text to type")
            return
        
        logger.info(f"Typing text: '{text[:50]}...'")
        
        # Small delay to ensure focus is correct
        time.sleep(0.1)
        
        # Try clipboard method if requested or for long text
        if use_clipboard or (self.use_clipboard_fallback and len(text) > 500):
            self._type_via_clipboard(text)
        else:
            # Try character-by-character typing
            try:
                self._type_char_by_char(text)
            except Exception as e:
                logger.warning(f"Char-by-char typing failed: {e}, trying clipboard")
                if self.use_clipboard_fallback:
                    self._type_via_clipboard(text)
                else:
                    raise
    
    def _type_char_by_char(self, text: str):
        """Type text character by character.
        
        Args:
            text: Text to type
        """
        delay = 1.0 / self.typing_speed_cps if self.typing_speed_cps > 0 else 0
        
        for char in text:
            try:
                self.keyboard.type(char)
                if delay > 0:
                    time.sleep(delay)
            except Exception as e:
                # Some characters might not be typeable
                logger.warning(f"Failed to type char '{char}': {e}")
                continue
        
        logger.debug("Char-by-char typing complete")
    
    def _type_via_clipboard(self, text: str):
        """Type text by pasting from clipboard.
        
        Args:
            text: Text to type
        """
        try:
            # Save current clipboard
            old_clipboard = None
            try:
                old_clipboard = pyperclip.paste()
            except:
                pass
            
            # Copy text to clipboard
            pyperclip.copy(text)
            time.sleep(0.05)
            
            # Paste with Ctrl+V
            with self.keyboard.pressed(Key.ctrl):
                self.keyboard.press('v')
                self.keyboard.release('v')
            
            time.sleep(0.05)
            
            # Restore old clipboard
            if old_clipboard is not None:
                try:
                    pyperclip.copy(old_clipboard)
                except:
                    pass
            
            logger.debug("Clipboard typing complete")
            
        except Exception as e:
            logger.error(f"Clipboard typing failed: {e}")
            raise
    
    def press_key(self, key):
        """Press a single key.
        
        Args:
            key: Key to press (from pynput.keyboard.Key or string)
        """
        self.keyboard.press(key)
        self.keyboard.release(key)
    
    def press_hotkey(self, *keys):
        """Press a hotkey combination.
        
        Args:
            *keys: Keys to press together
        """
        # Press all keys
        for key in keys:
            self.keyboard.press(key)
        
        # Release in reverse order
        for key in reversed(keys):
            self.keyboard.release(key)
    
    def type_with_newline(self, text: str):
        """Type text and press Enter.
        
        Args:
            text: Text to type
        """
        self.type_text(text)
        time.sleep(0.1)
        self.press_key(Key.enter)
    
    def clear_line(self):
        """Clear the current line (Ctrl+A, Delete)."""
        with self.keyboard.pressed(Key.ctrl):
            self.keyboard.press('a')
            self.keyboard.release('a')
        time.sleep(0.05)
        self.press_key(Key.delete)
    
    def set_typing_speed(self, cps: int):
        """Change typing speed.
        
        Args:
            cps: Characters per second (0 = instant)
        """
        self.typing_speed_cps = cps
        logger.info(f"Typing speed changed to {cps} cps")
    
    @staticmethod
    def test_typing(text: str = "Hello from Whisper Flow!"):
        """Test auto-typing functionality.
        
        Args:
            text: Text to type
        """
        print(f"Testing auto-typing in 3 seconds...")
        print(f"Switch to a text editor and click where you want the text!")
        print(f"Text to type: '{text}'")
        
        for i in range(3, 0, -1):
            print(f"{i}...")
            time.sleep(1)
        
        print("Typing now!")
        
        typer = AutoTyper(typing_speed_cps=50)  # Moderate speed for visibility
        typer.type_text(text)
        
        print("\n✓ Typing complete!")


if __name__ == "__main__":
    # Test auto-typer
    import sys
    
    if len(sys.argv) > 1:
        test_text = " ".join(sys.argv[1:])
    else:
        test_text = "This is a test of the auto-typing system. It should appear in your active window!"
    
    AutoTyper.test_typing(test_text)
