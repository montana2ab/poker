"""Extended StateParser with chat parsing and event fusion capabilities."""

import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple, Dict

from holdem.vision.chat_parser import ChatParser, EventSource, GameEvent
from holdem.vision.event_fusion import EventFuser, FusedEvent
from holdem.vision.ocr import OCREngine
from holdem.vision.calibrate import TableProfile
from holdem.vision.parse_state import StateParser
from holdem.vision.cards import CardRecognizer
from holdem.vision.vision_performance_config import VisionPerformanceConfig
from holdem.vision.button_detector import ButtonDetector, detect_button_by_color
from holdem.types import TableState, ActionType, Street, Card
from holdem.utils.logging import get_logger

logger = get_logger("vision.chat_enabled_parser")

# Import timing profiler
try:
    from holdem.vision.vision_timing import get_profiler
    _TIMING_AVAILABLE = True
except ImportError:
    _TIMING_AVAILABLE = False
    get_profiler = None


def apply_fused_events_to_state(state: TableState, fused_events: List[FusedEvent], logger_instance=None):
    """Apply fused events (vision + chat) to the current hand state.
    
    This function updates the state based on reliable events from multiple sources:
    - Updates street (PREFLOP/FLOP/TURN/RIVER/SHOWDOWN) from board_update events
    - Updates pot from pot_update events
    - Updates player actions and states from player_action events
    - Prioritizes chat over vision when confidence >= 0.75
    
    This is a lightweight function that only performs simple logic (no OCR).
    
    Args:
        state: Current TableState to update
        fused_events: List of fused events to apply
        logger_instance: Optional logger instance for logging
        
    Returns:
        None (modifies state in-place)
    """
    if not fused_events:
        return
    
    log = logger_instance or logger
    
    # Process each event
    for event in fused_events:
        # 1. Handle board_update / street_update events
        if event.event_type in ["board_update", "street_update"]:
            if event.street:
                # Check if event has chat source with good confidence
                has_chat = EventSource.CHAT_OCR in event.sources or EventSource.CHAT in event.sources
                
                # Apply street update if:
                # - Event has chat source with confidence >= 0.75 (prioritize chat)
                # - OR event has high confidence (>= 0.85) from any source
                should_apply = (has_chat and event.confidence >= 0.75) or (event.confidence >= 0.85)
                
                if should_apply:
                    old_street = state.street
                    new_street_str = event.street.upper()
                    
                    # Map string to Street enum
                    street_mapping = {
                        "PREFLOP": Street.PREFLOP,
                        "FLOP": Street.FLOP,
                        "TURN": Street.TURN,
                        "RIVER": Street.RIVER,
                        "SHOWDOWN": Street.RIVER  # Treat showdown as river for street tracking
                    }
                    
                    new_street = street_mapping.get(new_street_str, state.street)
                    
                    # Only update if street is progressing (never go backwards)
                    street_order = {Street.PREFLOP: 0, Street.FLOP: 1, Street.TURN: 2, Street.RIVER: 3}
                    current_order = street_order.get(old_street, 0)
                    new_order = street_order.get(new_street, 0)
                    
                    if new_order > current_order:
                        state.street = new_street
                        sources_str = ", ".join(s.value for s in event.sources)
                        log.info(
                            f"[STREET UPDATE] Street updated from chat: {old_street.name} -> {new_street.name} "
                            f"(sources={sources_str}, confidence={event.confidence:.2f})"
                        )
                        
                        # Mark that board came from chat if applicable
                        if has_chat:
                            # Add a flag to state to track board source (optional, for debugging)
                            state.__dict__['board_from_chat'] = True
                    elif new_order == current_order:
                        log.debug(
                            f"[STREET UPDATE] Street already at {new_street.name}, skipping update "
                            f"(confidence={event.confidence:.2f})"
                        )
                    else:
                        log.warning(
                            f"[STREET UPDATE] Ignoring backwards street transition: "
                            f"{old_street.name} -> {new_street.name}"
                        )
                
                # Note: Board card updates are handled by _update_board_cache_from_event()
                # which is called separately after this function
        
        # 2. Handle pot_update events
        elif event.event_type == "pot_update":
            if event.pot_amount is not None and event.confidence >= 0.7:
                has_chat = EventSource.CHAT_OCR in event.sources or EventSource.CHAT in event.sources
                
                # Prioritize chat pot updates
                if has_chat or event.confidence >= 0.85:
                    old_pot = state.pot
                    state.pot = event.pot_amount
                    sources_str = ", ".join(s.value for s in event.sources)
                    log.info(
                        f"[POT UPDATE] Pot updated: {old_pot:.2f} -> {state.pot:.2f} "
                        f"(sources={sources_str}, confidence={event.confidence:.2f})"
                    )
        
        # 3. Handle player_action events
        elif event.event_type == "action":
            if event.player and event.action and event.confidence >= 0.7:
                # Find player in state
                player_state = None
                for p in state.players:
                    if p.name == event.player:
                        player_state = p
                        break
                
                if player_state:
                    # Update player's last action
                    old_action = player_state.last_action
                    player_state.last_action = event.action
                    
                    # Update bet amount if provided
                    if event.amount is not None:
                        player_state.bet_this_round = event.amount
                    
                    # Update folded status
                    if event.action == ActionType.FOLD:
                        player_state.folded = True
                    
                    # Update all-in status
                    if event.action == ActionType.ALLIN:
                        player_state.all_in = True
                    
                    sources_str = ", ".join(s.value for s in event.sources)
                    log.debug(
                        f"[PLAYER ACTION] {event.player}: {event.action.value} "
                        f"(amount={event.amount}, sources={sources_str}, confidence={event.confidence:.2f})"
                    )


class ChatEnabledStateParser:
    """Extended StateParser with chat parsing and event fusion."""
    
    def __init__(
        self,
        profile: TableProfile,
        card_recognizer: CardRecognizer,
        ocr_engine: OCREngine,
        enable_chat_parsing: bool = True,
        debug_dir: Optional[Path] = None,
        vision_metrics: Optional['VisionMetrics'] = None,
        perf_config: Optional[VisionPerformanceConfig] = None,
        hero_position: Optional[int] = None
    ):
        """Initialize chat-enabled state parser.
        
        Args:
            profile: Table calibration profile
            card_recognizer: Card recognition engine
            ocr_engine: OCR engine for text extraction
            enable_chat_parsing: Whether to parse chat for events
            debug_dir: Optional directory for debug images
            vision_metrics: Optional VisionMetrics instance for tracking
            perf_config: Optional performance configuration
            hero_position: Optional fixed hero position (overrides profile.hero_position)
        """
        self.profile = profile
        self.perf_config = perf_config or VisionPerformanceConfig.default()
        
        # Determine hero position: CLI > config > None
        self.hero_pos: Optional[int] = None
        hero_pos_source = None
        
        if hero_position is not None:
            # CLI argument provided
            self.hero_pos = hero_position
            hero_pos_source = "cli"
        elif profile.hero_position is not None:
            # Config value provided
            self.hero_pos = profile.hero_position
            hero_pos_source = "config"
        # else: remain None, use fallback behavior
        
        # Log hero position source
        if self.hero_pos is not None:
            logger.info(f"Using fixed hero position: {self.hero_pos} (source: {hero_pos_source})")
        else:
            logger.info("No fixed hero position - using automatic detection")
        
        self.state_parser = StateParser(
            profile=profile,
            card_recognizer=card_recognizer,
            ocr_engine=ocr_engine,
            debug_dir=debug_dir,
            vision_metrics=vision_metrics,
            perf_config=self.perf_config,
            hero_position=self.hero_pos
        )
        
        self.enable_chat_parsing = enable_chat_parsing
        self.chat_parser = ChatParser(ocr_engine) if enable_chat_parsing else None
        self.event_fuser = EventFuser(
            time_window_seconds=5.0,
            confidence_threshold=0.7
        )
        
        # Store vision_metrics for board tracking
        self.vision_metrics = vision_metrics
        
        # Button detector for automatic button position detection
        # Assumes 6-max table by default (can be made configurable if needed)
        self.button_detector = ButtonDetector(num_seats=6)
        
        self.prev_state: Optional[TableState] = None
        self._last_button_detection_street: Optional[Street] = None
        self._current_hand_button: Optional[int] = None
        
        # Visual button detection state tracking for stability
        self._visual_button_history: List[Optional[int]] = []  # Last N button positions from visual detection
        self._visual_button_stable_position: Optional[int] = None
        
        # Chat region caching to avoid redundant OCR
        self._chat_region_hash: Optional[int] = None
        self._cached_chat_events: List['GameEvent'] = []
    
    def parse(self, screenshot: np.ndarray, frame_index: int = 0) -> Optional[TableState]:
        """Parse table state from screenshot (without events).
        
        This method provides compatibility with the standard StateParser interface.
        Use parse_with_events() to get both state and fused events.
        
        Args:
            screenshot: Screenshot of poker table
            frame_index: Frame number for light parse logic
            
        Returns:
            TableState or None if parsing failed
        """
        state, _ = self.parse_with_events(screenshot, frame_index=frame_index)
        return state
    
    def parse_with_events(
        self, 
        screenshot: np.ndarray,
        frame_index: int = 0
    ) -> Tuple[Optional[TableState], List[FusedEvent]]:
        """Parse table state and extract fused events.
        
        Args:
            screenshot: Screenshot of poker table
            frame_index: Frame number for light parse logic
            
        Returns:
            Tuple of (TableState, List[FusedEvent])
        """
        # Parse vision state with frame_index for light parse
        current_state = self.state_parser.parse(screenshot, frame_index=frame_index)
        
        if current_state is None:
            logger.debug("Failed to parse table state from vision")
            return None, []
        
        # Extract vision events by comparing states
        vision_events = []
        if self.prev_state is not None:
            vision_events = self.event_fuser.create_vision_events_from_state(
                self.prev_state, current_state
            )
            if vision_events:
                logger.debug(f"Extracted {len(vision_events)} events from vision")
                for event in vision_events:
                    sources_str = ", ".join(s.value for s in event.sources)
                    logger.debug(f"  Vision event: {event.event_type}, sources: {sources_str}")
        
        # Extract chat events if enabled and on appropriate frame
        chat_events = []
        should_parse_chat = (
            self.enable_chat_parsing 
            and self.profile.chat_region
            and (frame_index == 0 or self.perf_config.chat_parse_interval == 0 or frame_index % self.perf_config.chat_parse_interval == 0)
        )
        
        if should_parse_chat:
            # Get timing recorder if available
            timing_recorder = None
            if _TIMING_AVAILABLE:
                profiler = get_profiler()
                if profiler:
                    # Get the most recent recorder (from state_parser.parse)
                    # Note: This is a bit of a hack - we're assuming the state_parser just created one
                    # A better approach would be to pass it through, but that requires more refactoring
                    # For now, we'll create timing blocks that will be recorded separately
                    pass
            
            chat_events = self._extract_chat_events(screenshot, timing_recorder=timing_recorder)
            if chat_events:
                logger.info(f"[CHAT OCR] Extracted {len(chat_events)} events from chat")
                for event in chat_events:
                    sources_str = ", ".join(s.value for s in event.sources)
                    logger.info(f"  Chat event: {event.event_type}, sources: {sources_str}")
        elif self.enable_chat_parsing and frame_index > 0:
            logger.debug(f"[LIGHT PARSE] Skipping chat parsing on frame {frame_index}")
        
        # Fuse events from both sources
        fused_events = self.event_fuser.fuse_events(chat_events, vision_events)
        
        # Filter for reliable events only
        reliable_events = self.event_fuser.get_reliable_events(fused_events)
        
        # Apply fused events to state (updates street, pot, player actions)
        if reliable_events:
            apply_fused_events_to_state(current_state, reliable_events, logger_instance=logger)
        
        if reliable_events:
            logger.info(f"Fused {len(fused_events)} events, {len(reliable_events)} reliable")
            
            # Log event details and update board cache from board_update events
            for event in reliable_events:
                sources_str = ", ".join(s.value for s in event.sources)
                multi_source = " [CONFIRMED]" if event.is_multi_source() else ""
                logger.info(
                    f"Event: {event.event_type} - "
                    f"Player: {event.player} - "
                    f"Action: {event.action} - "
                    f"Amount: {event.amount} - "
                    f"Confidence: {event.confidence:.2f} - "
                    f"Sources: {sources_str}{multi_source}"
                )
                
                # Update board cache from board_update events
                if event.event_type == "board_update" and event.cards and event.street:
                    # Record conflict in metrics if detected
                    if event.has_source_conflict and self.vision_metrics:
                        self.vision_metrics.record_board_detection(
                            source="conflict",
                            street=event.street,
                            confidence=event.confidence,
                            cards=[str(c) for c in event.cards]
                        )
                    
                    self._update_board_cache_from_event(event, current_state)
            
            # Update hero_active flag based on events
            self._update_hero_state_from_events(current_state, reliable_events)
        
        # Detect button position if we have blind events and are at start of hand
        # Only call once per hand (when transitioning to PREFLOP with empty board)
        # Pass screenshot for visual detection (only used on full parses)
        self._detect_button_position(current_state, chat_events + vision_events, reliable_events, screenshot)
        
        # Update previous state
        self.prev_state = current_state
        
        return current_state, reliable_events
    
    def _update_hero_state_from_events(self, state: TableState, events: List[FusedEvent]):
        """Update hero_active flag based on detected events.
        
        Args:
            state: Current table state
            events: List of fused events
        """
        if state.hero_position is None:
            return
        
        # Get hero player name
        if state.hero_position < len(state.players):
            hero_player = state.players[state.hero_position]
            hero_name = hero_player.name
            
            # Check for hero fold action
            for event in events:
                if event.event_type == "action" and event.player == hero_name:
                    if event.action == ActionType.FOLD:
                        state.hero_active = False
                        logger.info(f"[HERO STATE] Hero folded - marking hero_active=False")
                        break
    
    def _update_board_cache_from_event(self, event: FusedEvent, state: TableState):
        """Update BoardCache from a board_update event.
        
        This allows chat events to populate the board cache and skip vision detection.
        
        Args:
            event: Board update event with cards and street
            state: Current table state
        """
        # Check if board cache is available
        if not hasattr(self.state_parser, 'board_cache') or not self.state_parser.board_cache:
            return
        
        board_cache = self.state_parser.board_cache
        street = event.street
        cards = event.cards
        
        if not cards or not street:
            return
        
        # Determine source for logging and metrics
        has_chat = any(src == EventSource.CHAT_OCR for src in event.sources)
        has_vision = any(src == EventSource.VISION for src in event.sources)
        is_multi_source = has_chat and has_vision
        
        source_str = "chat" if has_chat else "vision"
        cards_str = [str(c) for c in cards]
        
        # Record metrics
        if self.vision_metrics:
            if is_multi_source:
                # Both sources agree
                self.vision_metrics.record_board_detection(
                    source="fusion_agree",
                    street=street,
                    confidence=event.confidence,
                    cards=cards_str
                )
            elif has_chat:
                self.vision_metrics.record_board_detection(
                    source="chat",
                    street=street,
                    confidence=event.confidence,
                    cards=cards_str
                )
            elif has_vision:
                self.vision_metrics.record_board_detection(
                    source="vision",
                    street=street,
                    confidence=event.confidence,
                    cards=cards_str
                )
        
        # Update board cache based on street
        if street == "FLOP" and len(cards) == 3:
            if not board_cache.has_flop():
                board_cache.mark_flop(cards)
                state.board = cards + state.board[3:]  # Update state board
                logger.info(
                    f"[BOARD CACHE] Flop marked from {source_str}: "
                    f"{cards_str} (confidence={event.confidence:.2f})"
                )
        
        elif street == "TURN" and len(cards) == 1:
            if board_cache.has_flop() and not board_cache.has_turn():
                board_cache.mark_turn(cards[0])
                # Ensure flop is in state.board, then add turn
                if len(state.board) >= 3:
                    state.board = state.board[:3] + [cards[0]] + state.board[4:]
                logger.info(
                    f"[BOARD CACHE] Turn marked from {source_str}: "
                    f"{str(cards[0])} (confidence={event.confidence:.2f})"
                )
        
        elif street == "RIVER" and len(cards) == 1:
            if board_cache.has_turn() and not board_cache.has_river():
                board_cache.mark_river(cards[0])
                # Ensure flop + turn are in state.board, then add river
                if len(state.board) >= 4:
                    state.board = state.board[:4] + [cards[0]]
                logger.info(
                    f"[BOARD CACHE] River marked from {source_str}: "
                    f"{str(cards[0])} (confidence={event.confidence:.2f})"
                )
    
    def _detect_button_position(
        self,
        state: TableState,
        all_events: List[GameEvent],
        reliable_events: List[FusedEvent],
        screenshot: Optional[np.ndarray] = None
    ):
        """Detect and update button position using hybrid approach (logical + visual).
        
        This method implements a hybrid detection strategy:
        1. First try logical detection from SB/BB blind events (fast, reliable)
        2. If logical detection fails, try visual color-based detection (fallback)
        3. Use configuration to control detection mode
        
        Visual detection is only attempted on full parses and when configured.
        
        Args:
            state: Current table state to update
            all_events: All events (chat + vision, before fusion)
            reliable_events: Fused reliable events
            screenshot: Optional screenshot for visual detection
        """
        # Get button detection mode from config
        button_config = self.perf_config.vision_button_detection
        detection_mode = button_config.mode if button_config else "hybrid"
        
        if detection_mode == "off":
            logger.debug("[BUTTON] Button detection disabled by config")
            return
        
        # Only detect button at start of new hand (PREFLOP with empty board)
        is_new_hand = (
            state.street == Street.PREFLOP 
            and len(state.board) == 0
        )
        
        # Check if we already detected button for this street transition
        if self._last_button_detection_street == state.street and self._current_hand_button is not None:
            # Already detected for this hand, reuse cached value
            state.button_position = self._current_hand_button
            return
        
        # Only run detection on new hands or street changes
        if not is_new_hand:
            return
        
        button_seat = None
        detection_source = None
        
        # Strategy 1: Logical detection from SB/BB (fast and reliable when blinds present)
        if detection_mode in ["logical_only", "hybrid"]:
            button_seat = self._detect_button_logical(state, all_events)
            if button_seat is not None:
                detection_source = "logical"
                logger.info(f"[BUTTON] Using logical detection: seat={button_seat}")
        
        # Strategy 2: Visual detection (fallback when logical fails)
        if button_seat is None and detection_mode in ["visual_only", "hybrid"] and screenshot is not None:
            button_seat = self._detect_button_visual(screenshot)
            if button_seat is not None:
                detection_source = "visual"
                logger.info(f"[BUTTON] Using visual detection: seat={button_seat}")
        
        # Update state if button was detected
        if button_seat is not None:
            state.button_position = button_seat
            self._current_hand_button = button_seat
            self._last_button_detection_street = state.street
            logger.info(
                f"[BUTTON] Updated button_position to {button_seat} "
                f"(source: {detection_source})"
            )
        else:
            logger.debug("[BUTTON] Could not detect button position from any method")
    
    def _detect_button_logical(
        self,
        state: TableState,
        all_events: List[GameEvent]
    ) -> Optional[int]:
        """Detect button position using logical deduction from SB/BB blind events.
        
        This is the existing logic that uses blind posting events to infer
        the button position.
        
        Args:
            state: Current table state
            all_events: All game events (chat + vision)
            
        Returns:
            Button seat index or None if cannot determine
        """
        # Check if we have any blind events in chat/vision
        has_blind_events = any(
            getattr(e, 'event_type', None) in ['post_small_blind', 'post_big_blind']
            for e in all_events
        )
        
        if not has_blind_events:
            logger.debug("[BUTTON] No blind events detected for logical detection")
            return None
        
        # Build name_to_seat mapping from current state
        name_to_seat: Dict[str, int] = {}
        for player in state.players:
            if player.name and player.name not in ["", "Player0", "Player1", "Player2", 
                                                    "Player3", "Player4", "Player5"]:
                name_to_seat[player.name] = player.position
        
        # Get active seats (players not folded)
        active_seats = [p.position for p in state.players if not p.folded]
        
        if not name_to_seat or not active_seats:
            logger.debug("[BUTTON] No valid players or active seats for logical button detection")
            return None
        
        # Call button detector
        result = self.button_detector.infer_button(
            events=all_events,
            name_to_seat=name_to_seat,
            active_seats=active_seats
        )
        
        if result.button_seat is not None:
            logger.debug(
                f"[BUTTON] Logical detection succeeded: button={result.button_seat}, "
                f"SB={result.sb_seat}, BB={result.bb_seat}"
            )
            return result.button_seat
        else:
            logger.debug("[BUTTON] Logical detection could not determine button")
            return None
    
    def _detect_button_visual(self, screenshot: np.ndarray) -> Optional[int]:
        """Detect button position using visual color-based detection.
        
        This method uses the detect_button_by_color function to find the dealer
        button by analyzing color patches at each seat. It includes frame
        stabilization to reduce false positives.
        
        Args:
            screenshot: Current screenshot
            
        Returns:
            Button seat index or None if cannot determine
        """
        # Call visual detection function
        button_seat = detect_button_by_color(screenshot, self.profile)
        
        if button_seat is None:
            logger.debug("[BUTTON] Visual detection returned no candidate")
            return None
        
        # Stabilization: track button position over multiple frames
        button_config = self.perf_config.vision_button_detection
        min_stable = button_config.min_stable_frames if button_config else 2
        
        # Add to history
        self._visual_button_history.append(button_seat)
        
        # Keep only last min_stable frames
        if len(self._visual_button_history) > min_stable:
            self._visual_button_history.pop(0)
        
        # Check if stable (all recent frames agree)
        if len(self._visual_button_history) >= min_stable:
            if all(pos == button_seat for pos in self._visual_button_history):
                # Stable detection
                if self._visual_button_stable_position != button_seat:
                    logger.info(
                        f"[BUTTON] Visual detection stabilized at seat {button_seat} "
                        f"({min_stable} consecutive frames)"
                    )
                    self._visual_button_stable_position = button_seat
                return button_seat
            else:
                logger.debug(
                    f"[BUTTON] Visual detection not stable yet: history={self._visual_button_history}"
                )
                return None
        else:
            logger.debug(
                f"[BUTTON] Visual detection needs more frames: {len(self._visual_button_history)}/{min_stable}"
            )
            return None
    
    def _extract_chat_events(self, screenshot: np.ndarray, timing_recorder=None) -> List[GameEvent]:
        """Extract events from chat region with image hash caching to avoid redundant OCR.
        
        Args:
            screenshot: Screenshot image
            timing_recorder: Optional timing recorder for profiling
        """
        if not self.chat_parser or not self.profile.chat_region:
            if not self.profile.chat_region:
                logger.debug("[CHAT OCR] No chat_region configured in profile")
            return []
        
        # Extract chat region
        region = self.profile.chat_region
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if y + h > screenshot.shape[0] or x + w > screenshot.shape[1]:
            logger.warning(f"[CHAT OCR] Chat region ({x},{y},{w},{h}) out of bounds")
            return []
        
        chat_region = screenshot[y:y+h, x:x+w]
        
        # Use image hash to avoid redundant OCR if chat hasn't changed
        # This is the same caching strategy used for other vision regions
        import hashlib
        chat_hash = hashlib.md5(chat_region.tobytes()).hexdigest()
        current_hash = hash(chat_hash)
        
        if self._chat_region_hash == current_hash:
            # Chat region unchanged, reuse cached events
            logger.debug("[CHAT OCR] Chat region unchanged (hash match), reusing cached events")
            return self._cached_chat_events
        
        # Chat region changed, run OCR
        logger.debug(f"[CHAT OCR] Chat region changed (new hash), running OCR on {w}x{h} region")
        events = self.chat_parser.parse_chat_region(chat_region)
        
        # Update cache
        self._chat_region_hash = current_hash
        self._cached_chat_events = events
        
        return events
