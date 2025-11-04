"""Screen capture utilities."""

import sys
import mss
import numpy as np
import unicodedata
from PIL import Image
from typing import Optional, Tuple
from holdem.utils.logging import get_logger

logger = get_logger("vision.screen")


def normalize_title(title: str) -> str:
    """
    Normalize window title for comparison.
    
    Handles:
    - Different quote types (', ', `, etc.) → standard apostrophe
    - Unicode normalization (NFD/NFC)
    - Case insensitivity
    - Whitespace normalization
    """
    if not title:
        return ""
    
    # Normalize unicode (handles accented characters)
    normalized = unicodedata.normalize('NFC', title)
    
    # Replace various quote characters with standard apostrophe
    # Using Unicode codepoints to avoid syntax issues
    quote_chars = [
        '\u2018',  # Left single quotation mark '
        '\u2019',  # Right single quotation mark '
        '`',       # Grave accent
        '\u00b4',  # Acute accent ´
        '\u02bc',  # Modifier letter apostrophe ʼ
    ]
    for char in quote_chars:
        normalized = normalized.replace(char, "'")
    
    # Normalize whitespace and case
    normalized = ' '.join(normalized.lower().split())
    
    return normalized


def _find_window_by_title(
    window_title: str,
    owner_name: Optional[str] = None,
    screen_region: Optional[Tuple[int, int, int, int]] = None
) -> Optional[Tuple[int, int, int, int]]:
    """
    Find window by title across different platforms.
    Returns (left, top, width, height) or None if not found.
    
    Args:
        window_title: Window title to search for (partial match, case-insensitive)
        owner_name: Optional application owner name (e.g., "PokerStars") for fallback
        screen_region: Optional fallback region (x, y, width, height) if window not found
    
    Fallback behavior:
    1. Try to find by window_title (normalized)
    2. If not found and owner_name provided, search by owner
    3. If still not found and screen_region provided, use screen_region
    4. Otherwise return None
    """
    # Normalize the search title
    search_title = normalize_title(window_title)
    
    try:
        if sys.platform == 'win32':
            # Windows: Use pywinauto
            import pywinauto
            app = pywinauto.Application(backend="uia").connect(title_re=f".*{window_title}.*")
            window = app.window(title_re=f".*{window_title}.*")
            rect = window.rectangle()
            return (rect.left, rect.top, rect.width(), rect.height())
        
        elif sys.platform == 'darwin':
            # macOS: Use Quartz (pyobjc) for native window management
            try:
                from Quartz import (
                    CGWindowListCopyWindowInfo,
                    kCGWindowListOptionOnScreenOnly,
                    kCGNullWindowID
                )
                
                # Get list of all windows
                window_list = CGWindowListCopyWindowInfo(
                    kCGWindowListOptionOnScreenOnly, 
                    kCGNullWindowID
                )
                
                # First pass: Search for window with matching title
                for window in window_list:
                    w_name = window.get('kCGWindowName', '')
                    if w_name and search_title in normalize_title(w_name):
                        bounds = window['kCGWindowBounds']
                        logger.info(f"Found window by title: '{w_name}'")
                        return (
                            int(bounds['X']),
                            int(bounds['Y']),
                            int(bounds['Width']),
                            int(bounds['Height'])
                        )
                
                # Second pass: If owner_name provided, search by owner (application name)
                if owner_name:
                    search_owner = normalize_title(owner_name)
                    for window in window_list:
                        w_owner = window.get('kCGWindowOwnerName', '')
                        w_name = window.get('kCGWindowName', '')
                        if w_owner and search_owner in normalize_title(w_owner):
                            bounds = window['kCGWindowBounds']
                            logger.info(f"Found window by owner: '{w_owner}' (title: '{w_name}')")
                            return (
                                int(bounds['X']),
                                int(bounds['Y']),
                                int(bounds['Width']),
                                int(bounds['Height'])
                            )
                
                # Third fallback: Use screen_region if provided
                if screen_region:
                    logger.info(f"Using fallback screen_region: {screen_region}")
                    return screen_region
                
                logger.warning(f"Window '{window_title}' not found in window list")
                return None
                
            except ImportError:
                # Fallback to pygetwindow if Quartz is not available
                logger.info("Quartz not available, falling back to pygetwindow")
                import pygetwindow as gw
                
                # Try exact title match first
                windows = gw.getWindowsWithTitle(window_title)
                if windows:
                    w = windows[0]
                    return (w.left, w.top, w.width, w.height)
                
                # Try normalized search
                all_windows = gw.getAllWindows()
                for w in all_windows:
                    if search_title in normalize_title(w.title):
                        return (w.left, w.top, w.width, w.height)
                
                # Use screen_region fallback if provided
                if screen_region:
                    logger.info(f"Using fallback screen_region: {screen_region}")
                    return screen_region
                
                return None
        
        else:
            # Linux and other platforms: Use pygetwindow
            import pygetwindow as gw
            
            # Try exact title match
            windows = gw.getWindowsWithTitle(window_title)
            if windows:
                w = windows[0]
                return (w.left, w.top, w.width, w.height)
            
            # Try normalized search
            all_windows = gw.getAllWindows()
            for w in all_windows:
                if search_title in normalize_title(w.title):
                    return (w.left, w.top, w.width, w.height)
            
            # Use screen_region fallback if provided
            if screen_region:
                logger.info(f"Using fallback screen_region: {screen_region}")
                return screen_region
            
            return None
            
    except Exception as e:
        logger.warning(f"Failed to find window '{window_title}': {e}")
        # Use screen_region fallback if provided
        if screen_region:
            logger.info(f"Using fallback screen_region after error: {screen_region}")
            return screen_region
        return None


class ScreenCapture:

    def capture(self):
        """Capture tout l'écran (moniteur principal)."""
        monitor = self.sct.monitors[0]
        screenshot = self.sct.grab(monitor)
        import numpy as _np
        img = _np.array(screenshot)
        return img[:, :, :3]

    """Captures screen regions using mss."""
    
    def __init__(self):
        self.sct = mss.mss()
    
    def capture_region(
        self, 
        x: int, 
        y: int, 
        width: int, 
        height: int
    ) -> np.ndarray:
        """Capture a specific screen region."""
        monitor = {"top": y, "left": x, "width": width, "height": height}
        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        return img[:, :, :3]  # Remove alpha channel
    
    def capture_window(
        self, 
        window_title: str,
        owner_name: Optional[str] = None,
        screen_region: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[np.ndarray]:
        """
        Capture a specific window by title.
        
        Args:
            window_title: Window title to search for
            owner_name: Optional application owner name for fallback (e.g., "PokerStars")
            screen_region: Optional fallback region if window not found
        """
        window_region = _find_window_by_title(window_title, owner_name, screen_region)
        if window_region is None:
            logger.warning(f"Failed to capture window '{window_title}': window not found")
            return None
        
        left, top, width, height = window_region
        return self.capture_region(left, top, width, height)
    
    def find_window_region(
        self, 
        window_title: str,
        owner_name: Optional[str] = None,
        screen_region: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Find window coordinates.
        
        Args:
            window_title: Window title to search for
            owner_name: Optional application owner name for fallback (e.g., "PokerStars")
            screen_region: Optional fallback region if window not found
        """
        return _find_window_by_title(window_title, owner_name, screen_region)
    
    def save_screenshot(self, img: np.ndarray, path: str):
        """Save screenshot to file."""
        Image.fromarray(img).save(path)
    
    def __del__(self):
        if hasattr(self, 'sct'):
            self.sct.close()
