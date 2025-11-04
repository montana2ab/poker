#!/usr/bin/env python
"""CLI tool to automatically capture card templates during gameplay."""

import argparse
from pathlib import Path
from holdem.vision.auto_capture import run_auto_capture
from holdem.utils.logging import setup_logger

logger = setup_logger("cli.capture_templates")


def main():
    parser = argparse.ArgumentParser(
        description="Automatically capture card templates during gameplay",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run until stopped with Ctrl+C
  python -m holdem.cli.capture_templates --profile assets/table_profiles/pokerstars.json
  
  # Run for 30 minutes (1800 seconds)
  python -m holdem.cli.capture_templates --profile pokerstars.json --duration 1800
  
  # Capture every 2 seconds
  python -m holdem.cli.capture_templates --profile pokerstars.json --interval 2.0
  
  # Custom output directories
  python -m holdem.cli.capture_templates --profile pokerstars.json \\
      --board-output my_templates/board \\
      --hero-output my_templates/hero

Usage Notes:
  - Play poker normally while this runs in the background
  - The tool will automatically capture cards as they appear
  - Board cards are captured at flop, turn, and river
  - Hero cards are captured when you receive your hole cards
  - After capture, you'll need to manually identify and rename the cards
  - See documentation for organizing captured templates
        """
    )
    
    parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="Table profile JSON file"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Duration in seconds (default: run until Ctrl+C)"
    )
    
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between captures (default: 1.0)"
    )
    
    parser.add_argument(
        "--board-output",
        type=Path,
        default=Path("assets/templates_captured/board"),
        help="Output directory for board card templates"
    )
    
    parser.add_argument(
        "--hero-output",
        type=Path,
        default=Path("assets/templates_captured/hero"),
        help="Output directory for hero card templates"
    )
    
    args = parser.parse_args()
    
    # Validate profile exists
    if not args.profile.exists():
        logger.error(f"Profile not found: {args.profile}")
        logger.error("Create a profile first using the calibration tool")
        return 1
    
    # Show configuration
    logger.info("=" * 60)
    logger.info("AUTOMATIC TEMPLATE CAPTURE")
    logger.info("=" * 60)
    logger.info(f"Profile: {args.profile}")
    logger.info(f"Interval: {args.interval} seconds")
    logger.info(f"Duration: {'Unlimited (Ctrl+C to stop)' if args.duration is None else f'{args.duration} seconds'}")
    logger.info(f"Board output: {args.board_output}")
    logger.info(f"Hero output: {args.hero_output}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Instructions:")
    logger.info("1. Start playing poker normally")
    logger.info("2. This tool will capture cards automatically as they appear")
    logger.info("3. Play multiple hands to capture different cards")
    logger.info("4. After session, organize and rename the captured images")
    logger.info("")
    logger.info("Press Ctrl+C to stop at any time")
    logger.info("=" * 60)
    
    # Run capture
    try:
        run_auto_capture(
            profile_path=args.profile,
            duration_seconds=args.duration,
            interval_seconds=args.interval,
            board_output=args.board_output,
            hero_output=args.hero_output
        )
        return 0
    except Exception as e:
        logger.error(f"Error during capture: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
