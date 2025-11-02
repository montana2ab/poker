# Cross-Platform Window Management Migration

## Overview
This document describes the changes made to replace the Windows-only `pywinauto` library with a cross-platform solution that supports Windows, macOS, and Linux.

## Problem Statement
The original code used `pywinauto` exclusively, which only works on Windows because it controls windows via the Win32 API. This was incompatible with macOS and Linux systems.

## Solution
Implemented a cross-platform window management system with platform-specific backends:

### Platform Support

1. **Windows** (`sys.platform == 'win32'`)
   - Uses: `pywinauto` (unchanged)
   - Backend: UI Automation (UIA)
   - Provides native Win32 API access

2. **macOS** (`sys.platform == 'darwin'`)
   - Primary: `pyobjc-framework-Quartz`
   - Fallback: `pygetwindow`
   - Uses: Quartz Window Services API for native macOS support
   - Automatically falls back to pygetwindow if Quartz is unavailable

3. **Linux** (other platforms)
   - Uses: `pygetwindow`
   - Works with X11 window system
   - Compatible with most Linux desktop environments

## Changes Made

### 1. Dependencies (`requirements.txt` and `pyproject.toml`)

Added platform-specific dependencies:
```python
pywinauto>=0.6.8; sys_platform == 'win32'            # Windows only
pygetwindow>=0.0.9; sys_platform != 'win32'          # Non-Windows
pyobjc-framework-Quartz>=10.0; sys_platform == 'darwin'  # macOS only
```

### 2. Code Changes (`src/holdem/vision/screen.py`)

**New Helper Function:**
```python
def _find_window_by_title(window_title: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Find window by title across different platforms.
    Returns (left, top, width, height) or None if not found.
    """
```

This function:
- Detects the current platform
- Uses the appropriate window management library
- Returns window coordinates in a consistent format
- Handles errors gracefully with logging

**Updated Methods:**
- `capture_window()`: Simplified to use the new helper function
- `find_window_region()`: Now directly calls the helper function

### 3. Tests (`tests/test_screen_cross_platform.py`)

Created comprehensive unit tests covering:
- Windows pywinauto functionality
- macOS Quartz functionality
- macOS fallback to pygetwindow
- Linux pygetwindow functionality
- Window not found scenarios

### 4. Documentation (`README.md`)

Updated documentation to include:
- Cross-platform support information
- Platform-specific window management details
- macOS-specific installation and troubleshooting
- Dependencies for each platform

### 5. Demo Script (`demo_cross_platform.py`)

Created a demonstration script that:
- Shows platform detection
- Explains which library will be used
- Provides usage examples
- Lists platform-specific dependencies

## API Compatibility

The changes are **100% backward compatible**. The public API remains unchanged:

```python
from holdem.vision.screen import ScreenCapture

screen = ScreenCapture()

# Both methods work exactly as before
screenshot = screen.capture_window("MyPokerTable")
coords = screen.find_window_region("MyPokerTable")
```

## Benefits

1. **Cross-Platform Support**: Works on Windows, macOS, and Linux
2. **Native Performance**: Uses platform-specific APIs for best performance
3. **Graceful Fallbacks**: Automatically falls back on macOS if Quartz unavailable
4. **Minimal Changes**: Only modified the necessary files
5. **Well Tested**: Includes comprehensive unit tests
6. **Well Documented**: Updated README and added demo script

## Installation

### Windows
```bash
pip install -r requirements.txt  # Installs pywinauto
```

### macOS
```bash
pip install -r requirements.txt  # Installs pyobjc-framework-Quartz and pygetwindow
```

### Linux
```bash
pip install -r requirements.txt  # Installs pygetwindow
```

## Testing

Run the test suite:
```bash
pytest tests/test_screen_cross_platform.py -v
```

Run the demo:
```bash
python demo_cross_platform.py
```

## Notes

- Platform detection happens at runtime
- The appropriate library is imported only when needed (lazy import)
- All errors are logged with warnings rather than raising exceptions
- Window title matching is case-insensitive on macOS
- Returns `None` if window is not found (consistent behavior)

## Future Improvements

Potential enhancements (not implemented in this PR):
- Support for multiple monitor setups
- Window activation/focus capabilities
- Window position/size manipulation
- Wayland support for Linux (currently X11 only)
