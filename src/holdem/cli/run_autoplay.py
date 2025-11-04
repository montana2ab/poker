"""CLI: Run auto-play mode (with safety checks)."""

import argparse
import time
from pathlib import Path
from holdem.types import SearchConfig, ControlConfig
from holdem.vision.screen import ScreenCapture
from holdem.vision.calibrate import TableProfile
from holdem.vision.detect_table import TableDetector
from holdem.vision.cards import CardRecognizer
from holdem.vision.ocr import OCREngine
from holdem.vision.parse_state import StateParser
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.search_controller import SearchController
from holdem.control.executor import ActionExecutor
from holdem.control.safety import SafetyChecker
from holdem.utils.logging import setup_logger

logger = setup_logger("run_autoplay")


def main():
    parser = argparse.ArgumentParser(description="Run auto-play mode (USE WITH CAUTION)")
    parser.add_argument("--profile", type=Path, required=True,
                       help="Table profile JSON file")
    parser.add_argument("--policy", type=Path, required=True,
                       help="Blueprint policy file")
    parser.add_argument("--buckets", type=Path,
                       help="Buckets file")
    parser.add_argument("--time-budget-ms", type=int, default=80,
                       help="Time budget for search (ms)")
    parser.add_argument("--min-iters", type=int, default=100,
                       help="Minimum iterations for search")
    parser.add_argument("--confirm-every-action", type=bool, default=True,
                       help="Confirm each action")
    parser.add_argument("--i-understand-the-tos", action="store_true",
                       help="Required flag to enable auto-play")
    
    args = parser.parse_args()
    
    if not args.i_understand_the_tos:
        logger.error("Auto-play requires --i-understand-the-tos flag")
        logger.error("You must understand and comply with platform Terms of Service")
        return
    
    logger.warning("⚠️  AUTO-PLAY MODE ENABLED ⚠️")
    logger.warning("This will click on your screen automatically!")
    logger.warning("Press Ctrl+C to stop at any time")
    logger.warning("Move mouse to corner to trigger failsafe")
    
    response = input("Continue? (yes/no): ")
    if response.lower() != "yes":
        logger.info("Aborted")
        return
    
    # Load profile
    logger.info(f"Loading table profile from {args.profile}")
    profile = TableProfile.load(args.profile)
    
    # Load policy
    logger.info(f"Loading policy from {args.policy}")
    if args.policy.suffix == '.json':
        policy = PolicyStore.load_json(args.policy)
    else:
        policy = PolicyStore.load(args.policy)
    
    # Load buckets
    if args.buckets:
        bucketing = HandBucketing.load(args.buckets)
    else:
        from holdem.types import BucketConfig
        bucketing = HandBucketing(BucketConfig())
        bucketing.fitted = True
    
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
    ocr_engine = OCREngine()
    state_parser = StateParser(profile, card_recognizer, ocr_engine)
    
    search_config = SearchConfig(
        time_budget_ms=args.time_budget_ms,
        min_iterations=args.min_iters
    )
    search_controller = SearchController(search_config, bucketing, policy)
    
    control_config = ControlConfig(
        dry_run=False,
        confirm_every_action=args.confirm_every_action,
        i_understand_the_tos=args.i_understand_the_tos
    )
    executor = ActionExecutor(control_config, profile)
    safety = SafetyChecker()
    
    logger.info("Auto-play mode started")
    logger.info(f"Real-time search: time_budget={args.time_budget_ms}ms, min_iters={args.min_iters}")
    
    try:
        # Track action history for belief updates
        # Resets on street changes to maintain accurate belief state
        action_history = []
        last_street = None
        
        while True:
            # Capture and parse state
            if profile.screen_region:
                x, y, w, h = profile.screen_region
                screenshot = screen_capture.capture_region(x, y, w, h)
            else:
                screenshot = screen_capture.capture_window(
                    profile.window_title,
                    owner_name=profile.owner_name,
                    screen_region=profile.screen_region
                )
            
            if screenshot is None:
                time.sleep(1.0)
                continue
            
            warped = table_detector.detect(screenshot)
            state = state_parser.parse(warped)
            
            if not state:
                time.sleep(1.0)
                continue
            
            # Reset history on new street
            if last_street != state.street:
                logger.info(f"New street: {state.street.name}")
                action_history = []
                last_street = state.street
            
            logger.info(f"State: {state.street.name}, Pot={state.pot:.2f}, Players={state.num_players}")
            
            # Get hero cards
            hero_cards = None
            if profile.hero_position is not None and profile.hero_position < len(state.players):
                hero = state.players[profile.hero_position]
                if hero.hole_cards:
                    hero_cards = hero.hole_cards
                    cards_str = ", ".join([str(c) for c in hero_cards])
                    logger.info(f"Hero cards: {cards_str}")
            
            # Use real-time search to decide and execute action
            if hero_cards and len(hero_cards) == 2:
                try:
                    # Safety check
                    if not safety.check_safe_to_act(state):
                        logger.warning("Safety check failed, skipping action")
                        time.sleep(2.0)
                        continue
                    
                    logger.info("[REAL-TIME SEARCH] Computing optimal action...")
                    start_time = time.time()
                    
                    # Get action from search controller
                    suggested_action = search_controller.get_action(
                        state=state,
                        our_cards=hero_cards,
                        history=action_history
                    )
                    
                    elapsed_ms = (time.time() - start_time) * 1000
                    logger.info(f"[REAL-TIME SEARCH] Action decided: {suggested_action.name} (in {elapsed_ms:.1f}ms)")
                    
                    # Execute the action
                    success = executor.execute(suggested_action, state)
                    if success:
                        logger.info(f"[AUTO-PLAY] Executed action: {suggested_action.name}")
                        # Track this action in history
                        action_history.append(suggested_action.name)
                    else:
                        logger.warning(f"[AUTO-PLAY] Failed to execute action: {suggested_action.name}")
                    
                except Exception as e:
                    logger.error(f"[REAL-TIME SEARCH] Error: {e}", exc_info=True)
                    logger.info("[AUTO-PLAY] Skipping action due to error")
            
            time.sleep(2.0)
            
    except KeyboardInterrupt:
        logger.info("Stopping auto-play mode")
        executor.stop()


if __name__ == "__main__":
    main()
