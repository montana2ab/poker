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
from holdem.vision.chat_enabled_parser import ChatEnabledStateParser
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.search_controller import SearchController
from holdem.rt_resolver.leaf_evaluator import LeafEvaluator
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
    parser.add_argument("--num-workers", type=int, default=1,
                       help="Number of parallel workers for real-time solving (1 = single process, 0 = use all CPU cores)")
    parser.add_argument("--confirm-every-action", type=bool, default=True,
                       help="Confirm each action")
    parser.add_argument("--i-understand-the-tos", action="store_true",
                       help="Required flag to enable auto-play")
    parser.add_argument("--cfv-net", type=Path,
                       default=Path("assets/cfv_net/6max_mid_125k_m2.onnx"),
                       help="Path to CFV net ONNX model (default: assets/cfv_net/6max_mid_125k_m2.onnx)")
    parser.add_argument("--no-cfv-net", action="store_true",
                       help="Disable CFV net and use only blueprint/rollouts for leaf evaluation")
    parser.add_argument("--disable-chat-parsing", action="store_true",
                       help="Disable chat parsing (only use vision for state detection)")
    parser.add_argument("--force-tesseract", action="store_true",
                       help="Force use of Tesseract OCR instead of PaddleOCR (useful if PaddleOCR has issues)")
    
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
    
    # Use Tesseract if forced, otherwise default to PaddleOCR
    ocr_backend = "pytesseract" if args.force_tesseract else "paddleocr"
    ocr_engine = OCREngine(backend=ocr_backend)
    if args.force_tesseract:
        logger.info("Forcing Tesseract OCR backend (--force-tesseract flag)")
    
    # Create chat-enabled state parser
    enable_chat = not args.disable_chat_parsing
    if enable_chat and profile.chat_region:
        logger.info("Chat parsing enabled - will extract events from chat")
    elif enable_chat and not profile.chat_region:
        logger.warning("Chat parsing enabled but no chat_region in profile - only using vision")
        enable_chat = False
    else:
        logger.info("Chat parsing disabled - only using vision")
    
    state_parser = ChatEnabledStateParser(
        profile=profile,
        card_recognizer=card_recognizer,
        ocr_engine=ocr_engine,
        enable_chat_parsing=enable_chat
    )
    
    # Create leaf evaluator based on arguments
    if args.no_cfv_net:
        # Use blueprint/rollouts mode
        leaf_evaluator = LeafEvaluator(
            blueprint=policy,
            mode="blueprint",
            use_cfv=True,
            num_rollout_samples=10,
            enable_cache=True,
            cache_max_size=10000
        )
        logger.info("Using blueprint/rollouts for leaf evaluation (CFV net disabled)")
    else:
        # Use CFV net mode if model file exists
        if args.cfv_net.exists():
            leaf_evaluator = LeafEvaluator(
                blueprint=policy,
                mode="cfv_net",
                cfv_net_config={
                    "checkpoint": str(args.cfv_net),
                    "cache_max_size": 10000,
                    "gating": {
                        "tau_flop": 0.20,
                        "tau_turn": 0.16,
                        "tau_river": 0.12,
                    },
                }
            )
            logger.info(f"Using CFV net for leaf evaluation: {args.cfv_net}")
        else:
            # Fallback to blueprint/rollouts if CFV net file doesn't exist
            leaf_evaluator = LeafEvaluator(
                blueprint=policy,
                mode="blueprint",
                use_cfv=True,
                num_rollout_samples=10,
                enable_cache=True,
                cache_max_size=10000
            )
            logger.warning(f"CFV net file not found: {args.cfv_net}, using blueprint/rollouts instead")
    
    search_config = SearchConfig(
        time_budget_ms=args.time_budget_ms,
        min_iterations=args.min_iters,
        num_workers=args.num_workers
    )
    search_controller = SearchController(search_config, bucketing, policy, leaf_evaluator)
    
    control_config = ControlConfig(
        dry_run=False,
        confirm_every_action=args.confirm_every_action,
        i_understand_the_tos=args.i_understand_the_tos
    )
    executor = ActionExecutor(control_config, profile)
    safety = SafetyChecker()
    
    logger.info("Auto-play mode started")
    logger.info(f"Real-time search: time_budget={args.time_budget_ms}ms, min_iters={args.min_iters}, workers={args.num_workers}")
    
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
            state, events = state_parser.parse_with_events(warped)
            
            if not state:
                time.sleep(1.0)
                continue
            
            # Log fused events if any
            if events:
                for event in events:
                    sources_str = ", ".join(s.value for s in event.sources)
                    confirmed = " [MULTI-SOURCE]" if event.is_multi_source() else ""
                    logger.info(f"[EVENT] {event.event_type}: {event.action or event.street} "
                              f"(sources: {sources_str}, confidence: {event.confidence:.2f}){confirmed}")
            
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
