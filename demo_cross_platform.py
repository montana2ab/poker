#!/usr/bin/env python3
"""
Demonstration script for cross-platform window detection.

This script shows how the new cross-platform window management works
on Windows, macOS, and Linux.
"""

import sys
import platform

def main():
    print("=" * 70)
    print("Cross-Platform Window Detection Demonstration")
    print("=" * 70)
    print()
    
    # Display platform information
    print(f"Platform: {sys.platform}")
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    print()
    
    # Show which window management library will be used
    print("Window Management Library:")
    if sys.platform == 'win32':
        print("  → pywinauto (Windows native Win32 API)")
        print("    - Uses UI Automation backend")
        print("    - Provides reliable window detection on Windows")
    elif sys.platform == 'darwin':
        print("  → pyobjc-framework-Quartz (macOS native)")
        print("    - Uses Quartz Window Services API")
        print("    - Fallback to pygetwindow if Quartz not available")
        print("    - Provides native macOS window detection")
    else:
        print("  → pygetwindow (Linux/X11)")
        print("    - Works with X11 window system")
        print("    - Compatible with most Linux desktop environments")
    
    print()
    print("Dependencies to install:")
    if sys.platform == 'win32':
        print("  pip install pywinauto")
    elif sys.platform == 'darwin':
        print("  pip install pyobjc-framework-Quartz pygetwindow")
    else:
        print("  pip install pygetwindow")
    
    print()
    print("-" * 70)
    print("Usage Example:")
    print("-" * 70)
    print("""
from holdem.vision.screen import ScreenCapture

# Create screen capture instance
screen = ScreenCapture()

# Find and capture a window by title
screenshot = screen.capture_window("MyPokerTable")

# Or just get window coordinates
coords = screen.find_window_region("MyPokerTable")
if coords:
    left, top, width, height = coords
    print(f"Window found at: ({left}, {top}) size: {width}x{height}")
""")
    
    print("=" * 70)
    print("Ready to use! The system will automatically select the")
    print("appropriate window management library for your platform.")
    print("=" * 70)


if __name__ == "__main__":
    main()
