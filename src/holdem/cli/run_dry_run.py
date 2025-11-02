"""CLI: Run dry-run mode (observe only)."""

import argparse
import time
from pathlib import Path
from holdem.types import SearchConfig, VisionConfig, ControlConfig
from holdem.vision.screen import ScreenCapture
from holdem.vision.calibrate import TableProfile
from holdem.vision.detect_table import TableDetector
from holdem.vision.cards import CardRecognizer
from holdem.vision.ocr import OCREngine
from holdem.vision.parse_state import StateParser
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.search_controller import SearchController
from holdem.utils.logging import setup_logger

logger = setup_logger("run_dry_run")


def main():
    parser = argparse.ArgumentParser(description="Run in dry-run mode (observe only)")
    parser.add_argument("--profile", type=Path, required=True,
                       help="Table profile JSON file")
    parser.add_argument("--policy", type=Path, required=True,
                       help="Blueprint policy file")
    parser.add_argument("--buckets", type=Path,
                       help="Buckets file (if not using policy's buckets)")
    parser.add_argument("--time-budget-ms", type=int, default=80,
                       help="Time budget for real-time search (ms)")
    parser.add_argument("--min-iters", type=int, default=100,
                       help="Minimum iterations for search")
    parser.add_argument("--interval", type=float, default=1.0,
                       help="Seconds between observations")
    
    args = parser.parse_args()
    
    # Load profile
    logger.info(f"Loading table profile from {args.profile}")
    profile = TableProfile.load(args.profile)
    
    # Load policy
    logger.info(f"Loading policy from {args.policy}")
    if args.policy.suffix == '.json':
        policy = PolicyStore.load_json(args.policy)
    else:
        policy = PolicyStore.load(args.policy)
    
    logger.info(f"Policy has {policy.num_infosets()} infosets")
    
    # Load buckets (if provided)
    if args.buckets:
        logger.info(f"Loading buckets from {args.buckets}")
        bucketing = HandBucketing.load(args.buckets)
    else:
        logger.warning("No buckets provided, using mock buckets")
        from holdem.types import BucketConfig
        bucketing = HandBucketing(BucketConfig())
        bucketing.fitted = True  # Mark as fitted to avoid errors
    
    # Setup components
    screen_capture = ScreenCapture()
    table_detector = TableDetector(profile)
    card_recognizer = CardRecognizer(
        templates_dir=Path("assets/templates"),
        method="template"
    )
    ocr_engine = OCREngine(backend="paddleocr")
    state_parser = StateParser(profile, card_recognizer, ocr_engine)
    
    # Setup search
    search_config = SearchConfig(
        time_budget_ms=args.time_budget_ms,
        min_iterations=args.min_iters
    )
    search_controller = SearchController(search_config, bucketing, policy)
    
    logger.info("Starting dry-run mode (press Ctrl+C to stop)")
    logger.info(f"Observing every {args.interval} seconds")
    
    try:
        while True:
            # Capture screen
            if profile.screen_region:
                x, y, w, h = profile.screen_region
                screenshot = screen_capture.capture_region(x, y, w, h)
            elif profile.window_title:
                screenshot = screen_capture.capture_window(
                    profile.window_title,
                    owner_name=profile.owner_name,
                    screen_region=profile.screen_region
                )
            else:
                logger.error("No screen region or window title in profile")
                break
            
            if screenshot is None:
                logger.warning("Failed to capture screenshot")
                time.sleep(args.interval)
                continue
            
            # Detect table
            warped = table_detector.detect(screenshot)
            
            # Parse state
            state = state_parser.parse(warped)
            
            if state:
                logger.info(f"State: {state.street.name}, Pot={state.pot:.2f}, Players={state.num_players}")
                
                # Demonstrate what action we would take (if we had our cards)
                logger.info("[DRY RUN] Would analyze and suggest action here")
            else:
                logger.warning("Failed to parse state")
            
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        logger.info("Stopping dry-run mode")


if __name__ == "__main__":
    main()
