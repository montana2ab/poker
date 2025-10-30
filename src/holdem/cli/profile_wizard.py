"""CLI: Profile wizard for table calibration."""

import argparse
from pathlib import Path
from holdem.vision.screen import ScreenCapture
from holdem.vision.calibrate import calibrate_interactive, TableProfile
from holdem.utils.logging import setup_logger

logger = setup_logger("profile_wizard")


def main():
    parser = argparse.ArgumentParser(description="Table calibration wizard")
    parser.add_argument("--window-title", type=str,
                       help="Window title to capture")
    parser.add_argument("--region", type=int, nargs=4, metavar=("X", "Y", "W", "H"),
                       help="Screen region (x y width height)")
    parser.add_argument("--out", type=Path, required=True,
                       help="Output profile JSON file")
    
    args = parser.parse_args()
    
    logger.info("Table Profile Wizard")
    logger.info("=" * 50)
    
    # Capture screenshot
    screen_capture = ScreenCapture()
    
    if args.window_title:
        logger.info(f"Capturing window: {args.window_title}")
        screenshot = screen_capture.capture_window(args.window_title)
        window_region = screen_capture.find_window_region(args.window_title)
    elif args.region:
        x, y, w, h = args.region
        logger.info(f"Capturing region: ({x}, {y}, {w}, {h})")
        screenshot = screen_capture.capture_region(x, y, w, h)
        window_region = tuple(args.region)
    else:
        logger.error("Must specify --window-title or --region")
        return
    
    if screenshot is None:
        logger.error("Failed to capture screenshot")
        return
    
    logger.info(f"Screenshot captured: {screenshot.shape}")
    
    # Run calibration
    logger.info("Running calibration...")
    profile = calibrate_interactive(
        screenshot,
        args.window_title or "Screen Region"
    )
    
    profile.screen_region = window_region
    
    # Save profile
    profile.save(args.out)
    
    logger.info("=" * 50)
    logger.info("Calibration complete!")
    logger.info(f"Profile saved to: {args.out}")
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Build abstraction buckets")
    logger.info("2. Train blueprint strategy")
    logger.info("3. Run dry-run mode to test")


if __name__ == "__main__":
    main()
