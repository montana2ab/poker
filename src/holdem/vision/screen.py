"""Screen capture utilities."""

import mss
import numpy as np
from PIL import Image
from typing import Optional, Tuple
from holdem.utils.logging import get_logger

logger = get_logger("vision.screen")


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
        try:
            import pywinauto
            app = pywinauto.Application(backend="uia").connect(title_re=f".*{window_title}.*")
            window = app.window(title_re=f".*{window_title}.*")
            rect = window.rectangle()
            return self.capture_region(
                rect.left, rect.top, 
                rect.width(), rect.height()
            )
        except Exception as e:
            logger.warning(f"Failed to capture window '{window_title}': {e}")
            return None
    
    def find_window_region(self, window_title: str) -> Optional[Tuple[int, int, int, int]]:
        """Find window coordinates."""
        try:
            import pywinauto
            app = pywinauto.Application(backend="uia").connect(title_re=f".*{window_title}.*")
            window = app.window(title_re=f".*{window_title}.*")
            rect = window.rectangle()
            return (rect.left, rect.top, rect.width(), rect.height())
        except Exception as e:
            logger.warning(f"Failed to find window '{window_title}': {e}")
            return None
    
    def save_screenshot(self, img: np.ndarray, path: str):
        """Save screenshot to file."""
        Image.fromarray(img).save(path)
    
    def __del__(self):
        if hasattr(self, 'sct'):
            self.sct.close()
