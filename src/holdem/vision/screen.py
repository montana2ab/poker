"""Screen capture utilities."""

import sys
import mss
import numpy as np
from PIL import Image
from typing import Optional, Tuple
from holdem.utils.logging import get_logger

logger = get_logger("vision.screen")


def _find_window_by_title(window_title: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Find window by title across different platforms.
    Returns (left, top, width, height) or None if not found.
    """
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
                
                # Search for window with matching title
                for window in window_list:
                    w_name = window.get('kCGWindowName', '')
                    if w_name and window_title.lower() in w_name.lower():
                        bounds = window['kCGWindowBounds']
                        return (
                            int(bounds['X']),
                            int(bounds['Y']),
                            int(bounds['Width']),
                            int(bounds['Height'])
                        )
                
                logger.warning(f"Window '{window_title}' not found in window list")
                return None
                
            except ImportError:
                # Fallback to pygetwindow if Quartz is not available
                logger.info("Quartz not available, falling back to pygetwindow")
                import pygetwindow as gw
                windows = gw.getWindowsWithTitle(window_title)
                if windows:
                    w = windows[0]
                    return (w.left, w.top, w.width, w.height)
                return None
        
        else:
            # Linux and other platforms: Use pygetwindow
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(window_title)
            if windows:
                w = windows[0]
                return (w.left, w.top, w.width, w.height)
            return None
            
    except Exception as e:
        logger.warning(f"Failed to find window '{window_title}': {e}")
        return None


class ScreenCapture:
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
    
    def capture_window(self, window_title: str) -> Optional[np.ndarray]:
        """Capture a specific window by title."""
        window_region = _find_window_by_title(window_title)
        if window_region is None:
            logger.warning(f"Failed to capture window '{window_title}': window not found")
            return None
        
        left, top, width, height = window_region
        return self.capture_region(left, top, width, height)
    
    def find_window_region(self, window_title: str) -> Optional[Tuple[int, int, int, int]]:
        """Find window coordinates."""
        return _find_window_by_title(window_title)
    
    def save_screenshot(self, img: np.ndarray, path: str):
        """Save screenshot to file."""
        Image.fromarray(img).save(path)
    
    def __del__(self):
        if hasattr(self, 'sct'):
            self.sct.close()
