"""
Global hotkey management.
"""

import keyboard
from typing import Callable, Dict, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


class HotkeyManager:
    """Manages global hotkeys for the application."""
    
    def __init__(self):
        """Initialize hotkey manager."""
        self.hotkeys: Dict[str, Callable] = {}
        self.registered_keys: set = set()
        
        logger.info("HotkeyManager initialized")
    
    def register(self, hotkey: str, callback: Callable, description: str = ""):
        """Register a global hotkey.
        
        Args:
            hotkey: Hotkey combination (e.g., 'ctrl+shift+space')
            callback: Function to call when hotkey is pressed
            description: Description of what the hotkey does
        """
        try:
            # Unregister if already exists
            if hotkey in self.registered_keys:
                self.unregister(hotkey)
            
            # Register with keyboard library
            keyboard.add_hotkey(hotkey, callback, suppress=False)
            
            self.hotkeys[hotkey] = callback
            self.registered_keys.add(hotkey)
            
            logger.info(f"✓ Registered hotkey: {hotkey} - {description}")
            
        except Exception as e:
            logger.error(f"Failed to register hotkey '{hotkey}': {e}")
            raise
    
    def unregister(self, hotkey: str):
        """Unregister a hotkey.
        
        Args:
            hotkey: Hotkey combination to unregister
        """
        try:
            if hotkey in self.registered_keys:
                keyboard.remove_hotkey(hotkey)
                self.registered_keys.remove(hotkey)
                if hotkey in self.hotkeys:
                    del self.hotkeys[hotkey]
                logger.info(f"Unregistered hotkey: {hotkey}")
        except Exception as e:
            logger.warning(f"Failed to unregister hotkey '{hotkey}': {e}")
    
    def unregister_all(self):
        """Unregister all hotkeys."""
        for hotkey in list(self.registered_keys):
            self.unregister(hotkey)
        logger.info("All hotkeys unregistered")
    
    def is_registered(self, hotkey: str) -> bool:
        """Check if a hotkey is registered.
        
        Args:
            hotkey: Hotkey combination
            
        Returns:
            True if registered
        """
        return hotkey in self.registered_keys
    
    def get_registered_hotkeys(self) -> Dict[str, str]:
        """Get all registered hotkeys.
        
        Returns:
            Dictionary of hotkey -> description
        """
        return {hk: str(callback) for hk, callback in self.hotkeys.items()}
    
    @staticmethod
    def validate_hotkey(hotkey: str) -> bool:
        """Validate hotkey string format.
        
        Args:
            hotkey: Hotkey combination to validate
            
        Returns:
            True if valid
        """
        try:
            # Try to parse the hotkey
            keyboard.parse_hotkey(hotkey)
            return True
        except:
            return False
    
    @staticmethod
    def normalize_hotkey(hotkey: str) -> str:
        """Normalize hotkey string to standard format.
        
        Args:
            hotkey: Hotkey combination
            
        Returns:
            Normalized hotkey string
        """
        try:
            # Parse and reconstruct to normalize
            parsed = keyboard.parse_hotkey(hotkey)
            return keyboard.get_hotkey_name(parsed)
        except:
            return hotkey


if __name__ == "__main__":
    # Test hotkey manager
    import time
    
    print("Hotkey Manager Test")
    print("=" * 60)
    print("Press Ctrl+Shift+T to test")
    print("Press Ctrl+C to exit")
    print("=" * 60)
    
    def test_callback():
        print("\n>>> Hotkey triggered! <<<\n")
    
    manager = HotkeyManager()
    
    try:
        manager.register("ctrl+shift+t", test_callback, "Test hotkey")
        
        print("\nHotkey registered. Waiting for input...")
        
        # Keep running
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nExiting...")
        manager.unregister_all()
        print("Done!")
