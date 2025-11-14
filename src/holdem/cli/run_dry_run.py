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
from holdem.vision.chat_enabled_parser import ChatEnabledStateParser
from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.search_controller import SearchController
from holdem.rt_resolver.leaf_evaluator import LeafEvaluator
from holdem.utils.logging import setup_logger

logger = setup_logger("run_dry_run")


def _report_vision_metrics(vision_metrics, args, logger, header, do_export):
    """Helper function to generate and report vision metrics.
    
    Args:
        vision_metrics: VisionMetrics instance
        args: Command line arguments
        logger: Logger instance
        header: Report header text
        do_export: Whether to export to files
    """
    logger.info("\n" + "="*80)
    logger.info(header)
    logger.info("="*80)
    report = vision_metrics.generate_report(format=args.metrics_format)
    logger.info(report)
    
    if do_export and args.metrics_output:
        args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.metrics_output, 'w') as f:
            f.write(report)
        logger.info(f"Metrics report saved to {args.metrics_output}")
        
        # Export JSON lines for further analysis
        jsonl_path = args.metrics_output.with_suffix('.jsonl')
        vision_metrics.export_jsonlines(str(jsonl_path))
        logger.info(f"Metrics data exported to {jsonl_path}")


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
    parser.add_argument("--num-workers", type=int, default=1,
                       help="Number of parallel workers for real-time solving (1 = single process, 0 = use all CPU cores)")
    parser.add_argument("--interval", type=float, default=1.0,
                       help="Seconds between observations")
    parser.add_argument("--debug-images", type=Path,
                       help="Directory to save debug images (optional)")
    parser.add_argument("--cfv-net", type=Path,
                       default=Path("assets/cfv_net/6max_mid_125k_m2.onnx"),
                       help="Path to CFV net ONNX model (default: assets/cfv_net/6max_mid_125k_m2.onnx)")
    parser.add_argument("--no-cfv-net", action="store_true",
                       help="Disable CFV net and use only blueprint/rollouts for leaf evaluation")
    parser.add_argument("--disable-chat-parsing", action="store_true",
                       help="Disable chat parsing (only use vision for state detection)")
    parser.add_argument("--ocr-backend", type=str, choices=["paddleocr", "easyocr", "pytesseract"],
                       default=None,
                       help="OCR backend to use (paddleocr, easyocr, or pytesseract). Overrides --force-tesseract flag.")
    parser.add_argument("--force-tesseract", action="store_true",
                       help="Force use of Tesseract OCR instead of PaddleOCR (deprecated, use --ocr-backend pytesseract instead)")
    parser.add_argument("--enable-vision-metrics", action="store_true", default=True,
                       help="Enable vision metrics tracking (default: enabled)")
    parser.add_argument("--disable-vision-metrics", action="store_true",
                       help="Disable vision metrics tracking")
    parser.add_argument("--metrics-report-interval", type=int, default=60,
                       help="Seconds between metrics reports (0 = only at end, default: 60)")
    parser.add_argument("--metrics-output", type=Path,
                       help="File to save metrics report (optional, default: console only)")
    parser.add_argument("--metrics-format", type=str, choices=["text", "json"], default="text",
                       help="Metrics report format (text or json, default: text)")
    
    args = parser.parse_args()
    
    # Determine if vision metrics should be enabled
    enable_metrics = args.enable_vision_metrics and not args.disable_vision_metrics
    
    # Create vision metrics instance if enabled
    vision_metrics = None
    if enable_metrics:
        metrics_config = VisionMetricsConfig()
        vision_metrics = VisionMetrics(metrics_config)
        logger.info("Vision metrics tracking enabled")
        logger.info(f"Metrics report interval: {args.metrics_report_interval}s")
    else:
        logger.info("Vision metrics tracking disabled")
    
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
    
    # Determine OCR backend based on arguments
    # --ocr-backend takes precedence over --force-tesseract
    if args.ocr_backend:
        ocr_backend = args.ocr_backend
        logger.info(f"Using OCR backend: {ocr_backend} (specified via --ocr-backend)")
    elif args.force_tesseract:
        ocr_backend = "pytesseract"
        logger.info("Using OCR backend: pytesseract (specified via --force-tesseract)")
    else:
        ocr_backend = "paddleocr"
        logger.info("Using OCR backend: paddleocr (default)")
    
    ocr_engine = OCREngine(backend=ocr_backend)
    
    # Load vision performance config
    from holdem.vision.vision_performance_config import VisionPerformanceConfig
    from pathlib import Path
    perf_config_path = Path("configs/vision_performance.yaml")
    if perf_config_path.exists():
        perf_config = VisionPerformanceConfig.from_yaml(perf_config_path)
        logger.info("Loaded vision performance config from configs/vision_performance.yaml")
    else:
        perf_config = VisionPerformanceConfig.default()
        logger.info("Using default vision performance config (all optimizations enabled)")
    
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
        enable_chat_parsing=enable_chat,
        debug_dir=args.debug_images,
        vision_metrics=vision_metrics,
        perf_config=perf_config
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
    
    # Setup search
    search_config = SearchConfig(
        time_budget_ms=args.time_budget_ms,
        min_iterations=args.min_iters,
        num_workers=args.num_workers
    )
    search_controller = SearchController(search_config, bucketing, policy, leaf_evaluator)
    
    logger.info("Starting dry-run mode (press Ctrl+C to stop)")
    logger.info(f"Observing every {args.interval} seconds")
    logger.info(f"Real-time search: time_budget={args.time_budget_ms}ms, min_iters={args.min_iters}, workers={args.num_workers}")
    
    # Log performance config
    if perf_config.enable_light_parse:
        logger.info(f"Light parse enabled: full parse every {perf_config.light_parse_interval} frames")
    if perf_config.enable_caching:
        logger.info("Caching enabled: board, hero cards, and OCR regions")
    
    # Track metrics reporting
    last_metrics_report = time.time()
    
    # Track frame index for light parse
    frame_index = 0
    
    try:
        # Track action history for belief updates
        # Resets on street changes to maintain accurate belief state
        action_history = []
        last_street = None
        
        while True:
            # Increment frame index
            frame_index += 1
            
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
            
            # Parse state with events (using chat if enabled) with frame_index
            state, events = state_parser.parse_with_events(warped, frame_index=frame_index)
            
            if state:
                logger.info(f"State: {state.street.name}, Pot={state.pot:.2f}, Players={state.num_players}")
                
                # Log fused events if any
                if events:
                    for event in events:
                        sources_str = ", ".join(s.value for s in event.sources)
                        confirmed = " [MULTI-SOURCE]" if event.is_multi_source() else ""
                        logger.info(f"[EVENT] {event.event_type}: {event.action or event.street} "
                                  f"(sources: {sources_str}, confidence: {event.confidence:.2f}){confirmed}")
                
                # Reset history on new street
                if last_street != state.street:
                    logger.info(f"New street detected: {state.street.name}")
                    action_history = []
                    last_street = state.street
                
                # Log board cards (community cards: flop, turn, river)
                if state.board:
                    board_str = ", ".join([str(c) for c in state.board])
                    logger.info(f"Board: {board_str}")
                
                # Get hero's hole cards using cache if available
                hero_cards = state.get_hero_cards()
                
                if hero_cards and len(hero_cards) > 0:
                    cards_str = ", ".join([str(c) for c in hero_cards])
                    logger.info(f"Hero cards: {cards_str}")
                else:
                    # No cards detected yet - that's fine, we can still observe game state
                    logger.debug("[DRY RUN] Hero cards missing, tracking game state only...")
                
                # Game can progress without hero cards - log observed actions
                # This allows blinds, bets, raises, calls, folds to be tracked
                logger.debug("[DRY RUN] Observing game state and actions...")
                
                # Use real-time search to decide action when we have our cards
                if hero_cards and len(hero_cards) == 2:
                    # Check if we should skip real-time search
                    skip_reason = None
                    
                    if not state.hand_in_progress:
                        skip_reason = "no hand in progress"
                    elif not state.hero_active:
                        skip_reason = "hero not active (folded)"
                    elif state.frame_has_showdown_label:
                        skip_reason = "showdown frame (Won X,XXX labels detected)"
                    elif state.state_inconsistent:
                        skip_reason = "inconsistent state (pot regression or other anomaly)"
                    
                    if skip_reason:
                        logger.debug(f"[REAL-TIME SEARCH] Skipped: {skip_reason}")
                    else:
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
                    # No cards detected yet - that's fine, we can still observe
                    if profile.hero_position is not None:
                        logger.debug("[DRY RUN] No hero cards yet - observing other players' actions")
            else:
                logger.warning("Failed to parse state")
            
            # Periodic metrics reporting
            if enable_metrics and args.metrics_report_interval > 0:
                current_time = time.time()
                if current_time - last_metrics_report >= args.metrics_report_interval:
                    _report_vision_metrics(
                        vision_metrics=vision_metrics,
                        args=args,
                        logger=logger,
                        header="VISION METRICS REPORT",
                        do_export=False
                    )
                    last_metrics_report = current_time
            
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        logger.info("Stopping dry-run mode")
    
    # Generate final metrics report
    if enable_metrics:
        _report_vision_metrics(
            vision_metrics=vision_metrics,
            args=args,
            logger=logger,
            header="FINAL VISION METRICS REPORT",
            do_export=True
        )


if __name__ == "__main__":
    main()
