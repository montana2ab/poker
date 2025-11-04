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
                       help="Window title to capture (partial match, case-insensitive)")
    parser.add_argument("--owner-name", type=str,
                       help="Application owner name (e.g., 'PokerStars') for fallback detection on macOS")
    parser.add_argument("--region", type=int, nargs=4, metavar=("X", "Y", "W", "H"),
                       help="Screen region (x y width height)")
    parser.add_argument("--seats", type=int, choices=[6, 9], default=9,
                       help="Number of seats at the table (6 for 6-max, 9 for 9-max, default: 9)")
    parser.add_argument("--out", type=Path, required=True,
                       help="Output profile JSON file")
    
    args = parser.parse_args()
    
    # Validate seats parameter (defense in depth)
    if args.seats not in [6, 9]:
        logger.error(f"Invalid seats value: {args.seats}. Must be 6 or 9.")
        return
    
    logger.info("Table Profile Wizard")
    logger.info("=" * 50)
    logger.info(f"Table size: {args.seats}-max")
    
    # Capture screenshot
    screen_capture = ScreenCapture()
    
    if args.window_title:
        logger.info(f"Capturing window: {args.window_title}")
        if args.owner_name:
            logger.info(f"Using owner name for fallback: {args.owner_name}")
        screenshot = screen_capture.capture_window(args.window_title, owner_name=args.owner_name)
        window_region = screen_capture.find_window_region(args.window_title, owner_name=args.owner_name)
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
        args.window_title or "Screen Region",
        seats=args.seats
    )
    
    profile.screen_region = window_region
    
    # Set owner_name if provided (helps with window detection on macOS)
    if args.owner_name:
        profile.owner_name = args.owner_name
        logger.info(f"Set owner_name to: {args.owner_name}")
    
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
    logger.info("")
    logger.info("📖 For detailed calibration instructions, see: CALIBRATION_GUIDE.md")
    logger.info("⚠️  For PokerStars on macOS:")
    logger.info("   - Grant Screen Recording permission in System Preferences")
    logger.info("   - Use --owner-name 'PokerStars' for better window detection")
    logger.info("   - See CALIBRATION_GUIDE.md for platform-specific tips")


if __name__ == "__main__":
    main()
