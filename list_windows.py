#!/usr/bin/env python3
"""
List Windows Helper Script

This script helps you find the correct window title and owner name
for your poker table on macOS. Run this while your poker table is open
to see all available windows and their details.

Usage:
    python list_windows.py
    python list_windows.py --filter "poker"
"""

import sys
import argparse


def list_windows_macos(filter_text=None):
    """List all windows on macOS using Quartz."""
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID
        )
        
        print("=" * 70)
        print("Available Windows on macOS")
        print("=" * 70)
        print()
        
        # Get list of all windows
        window_list = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, 
            kCGNullWindowID
        )
        
        count = 0
        for window in window_list:
            w_name = window.get('kCGWindowName', '')
            w_owner = window.get('kCGWindowOwnerName', '')
            w_layer = window.get('kCGWindowLayer', '')
            bounds = window.get('kCGWindowBounds', {})
            
            # Skip windows without names or from Window Server
            if not w_name and not w_owner:
                continue
            if w_owner == 'Window Server':
                continue
                
            # Apply filter if provided
            if filter_text:
                filter_lower = filter_text.lower()
                if filter_lower not in w_name.lower() and filter_lower not in w_owner.lower():
                    continue
            
            count += 1
            print(f"Window #{count}")
            print(f"  Title:  {w_name}")
            print(f"  Owner:  {w_owner}")
            print(f"  Layer:  {w_layer}")
            print(f"  Bounds: X={int(bounds.get('X', 0))}, Y={int(bounds.get('Y', 0))}, "
                  f"W={int(bounds.get('Width', 0))}, H={int(bounds.get('Height', 0))}")
            print()
        
        if count == 0:
            if filter_text:
                print(f"No windows found matching filter: '{filter_text}'")
            else:
                print("No windows found")
        else:
            print("=" * 70)
            print(f"Total windows shown: {count}")
            print()
            print("To use with profile wizard:")
            print("  python -m holdem.cli.profile_wizard \\")
            print("    --window-title \"<Title>\" \\")
            print("    --owner-name \"<Owner>\" \\")
            print("    --out assets/table_profiles/my_profile.json")
        
    except ImportError:
        print("Error: pyobjc-framework-Quartz is not installed")
        print("Install it with: pip install pyobjc-framework-Quartz")
        return 1


def list_windows_other(filter_text=None):
    """List windows using pygetwindow (cross-platform)."""
    try:
        import pygetwindow as gw
        
        print("=" * 70)
        print("Available Windows")
        print("=" * 70)
        print()
        
        windows = gw.getAllWindows()
        count = 0
        
        for w in windows:
            if not w.title:
                continue
                
            # Apply filter if provided
            if filter_text and filter_text.lower() not in w.title.lower():
                continue
            
            count += 1
            print(f"Window #{count}")
            print(f"  Title:  {w.title}")
            print(f"  Bounds: X={w.left}, Y={w.top}, W={w.width}, H={w.height}")
            print()
        
        if count == 0:
            if filter_text:
                print(f"No windows found matching filter: '{filter_text}'")
            else:
                print("No windows found")
        else:
            print("=" * 70)
            print(f"Total windows shown: {count}")
            print()
            print("To use with profile wizard:")
            print("  python -m holdem.cli.profile_wizard \\")
            print("    --window-title \"<Title>\" \\")
            print("    --out assets/table_profiles/my_profile.json")
        
    except ImportError:
        print("Error: pygetwindow is not installed")
        print("Install it with: pip install pygetwindow")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="List available windows for poker table detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all windows
  python list_windows.py
  
  # List only poker-related windows
  python list_windows.py --filter poker
  python list_windows.py --filter stars
  python list_windows.py --filter "hold'em"
        """
    )
    parser.add_argument("--filter", type=str, 
                       help="Filter windows by title or owner name (case-insensitive)")
    
    args = parser.parse_args()
    
    if sys.platform == 'darwin':
        return list_windows_macos(args.filter)
    else:
        return list_windows_other(args.filter)


if __name__ == "__main__":
    sys.exit(main() or 0)
