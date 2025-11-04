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
    parser.add_argument("--debug-images", type=Path,
                       help="Directory to save debug images (optional)")
    
    args = parser.parse_args()
    
    # Create debug directory if specified
    if args.debug_images:
        args.debug_images.mkdir(parents=True, exist_ok=True)
        logger.info(f"Debug images will be saved to {args.debug_images}")
    
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
    
    # Setup card recognizer with hero templates if configured
    hero_templates_dir = None
    if profile.hero_templates_dir:
        hero_templates_dir = Path(profile.hero_templates_dir)
    
    card_recognizer = CardRecognizer(
        templates_dir=Path("assets/templates"),
        hero_templates_dir=hero_templates_dir,
        method="template"
    )
    ocr_engine = OCREngine(backend="paddleocr")
    state_parser = StateParser(profile, card_recognizer, ocr_engine, debug_dir=args.debug_images)
    
    # Setup search
    search_config = SearchConfig(
        time_budget_ms=args.time_budget_ms,
        min_iterations=args.min_iters
    )
    search_controller = SearchController(search_config, bucketing, policy)
    
    logger.info("Starting dry-run mode (press Ctrl+C to stop)")
    logger.info(f"Observing every {args.interval} seconds")
    logger.info(f"Real-time search: time_budget={args.time_budget_ms}ms, min_iters={args.min_iters}")
    
    # Track action history for belief updates
    action_history = []
    last_street = None
    
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
                
                # Reset history on new street
                if last_street != state.street:
                    logger.info(f"New street detected: {state.street.name}")
                    action_history = []
                    last_street = state.street
                
                # Log board cards (community cards: flop, turn, river)
                if state.board:
                    board_str = ", ".join([str(c) for c in state.board])
                    logger.info(f"Board: {board_str}")
                
                # Log hero's hole cards if detected
                hero_cards = None
                if profile.hero_position is not None and profile.hero_position < len(state.players):
                    hero = state.players[profile.hero_position]
                    if hero.hole_cards:
                        hero_cards = hero.hole_cards
                        cards_str = ", ".join([str(c) for c in hero_cards])
                        logger.info(f"Hero cards: {cards_str}")
                    else:
                        logger.debug("Hero cards not detected")
                
                # Use real-time search to decide action when we have our cards
                if hero_cards and len(hero_cards) == 2:
                    try:
                        logger.info("[REAL-TIME SEARCH] Computing optimal action...")
                        start_time = time.time()
                        
                        # Get action from search controller
                        suggested_action = search_controller.get_action(
                            state=state,
                            our_cards=hero_cards,
                            history=action_history
                        )
                        
                        elapsed_ms = (time.time() - start_time) * 1000
                        logger.info(f"[REAL-TIME SEARCH] Recommended action: {suggested_action.name} (computed in {elapsed_ms:.1f}ms)")
                        
                    except Exception as e:
                        logger.warning(f"[REAL-TIME SEARCH] Failed: {e}")
                        logger.info("[DRY RUN] Would fall back to blueprint or manual decision")
                else:
                    # No cards detected, can't make decision
                    logger.info("[DRY RUN] Waiting for hole cards to be detected...")
            else:
                logger.warning("Failed to parse state")
            
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        logger.info("Stopping dry-run mode")


if __name__ == "__main__":
    main()
