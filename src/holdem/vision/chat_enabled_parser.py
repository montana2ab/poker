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
from holdem.types import TableState, ActionType, Street
from holdem.utils.logging import get_logger

logger = get_logger("vision.chat_enabled_parser")


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
            chat_events = self._extract_chat_events(screenshot)
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
        
        if reliable_events:
            logger.info(f"Fused {len(fused_events)} events, {len(reliable_events)} reliable")
            
            # Log event details
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
    
    def _extract_chat_events(self, screenshot: np.ndarray) -> List[GameEvent]:
        """Extract events from chat region with image hash caching to avoid redundant OCR."""
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
