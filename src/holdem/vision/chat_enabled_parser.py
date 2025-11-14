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
from holdem.vision.button_detector import ButtonDetector
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
        perf_config: Optional[VisionPerformanceConfig] = None
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
        """
        self.profile = profile
        self.perf_config = perf_config or VisionPerformanceConfig.default()
        
        self.state_parser = StateParser(
            profile=profile,
            card_recognizer=card_recognizer,
            ocr_engine=ocr_engine,
            debug_dir=debug_dir,
            vision_metrics=vision_metrics,
            perf_config=self.perf_config
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
                logger.info(f"Extracted {len(chat_events)} events from chat")
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
        self._detect_button_position(current_state, chat_events + vision_events, reliable_events)
        
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
        reliable_events: List[FusedEvent]
    ):
        """Detect and update button position from blind events.
        
        This method is called once per hand when transitioning to PREFLOP
        with an empty board and blind events are detected.
        
        Args:
            state: Current table state to update
            all_events: All events (chat + vision, before fusion)
            reliable_events: Fused reliable events
        """
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
        
        # Check if we have any blind events in chat/vision
        has_blind_events = any(
            getattr(e, 'event_type', None) in ['post_small_blind', 'post_big_blind']
            for e in all_events
        )
        
        if not has_blind_events:
            logger.debug("[BUTTON] No blind events detected, skipping button detection")
            return
        
        # Build name_to_seat mapping from current state
        name_to_seat: Dict[str, int] = {}
        for player in state.players:
            if player.name and player.name not in ["", "Player0", "Player1", "Player2", 
                                                    "Player3", "Player4", "Player5"]:
                name_to_seat[player.name] = player.position
        
        # Get active seats (players not folded)
        active_seats = [p.position for p in state.players if not p.folded]
        
        if not name_to_seat or not active_seats:
            logger.debug("[BUTTON] No valid players or active seats for button detection")
            return
        
        # Call button detector
        result = self.button_detector.infer_button(
            events=all_events,
            name_to_seat=name_to_seat,
            active_seats=active_seats
        )
        
        # Update state if button was inferred successfully
        if result.button_seat is not None:
            state.button_position = result.button_seat
            self._current_hand_button = result.button_seat
            self._last_button_detection_street = state.street
            logger.info(
                f"[BUTTON] Updated button_position to {result.button_seat} "
                f"(SB={result.sb_seat}, BB={result.bb_seat})"
            )
        else:
            logger.debug("[BUTTON] Could not infer button position from available events")
    
    def _extract_chat_events(self, screenshot: np.ndarray) -> List[GameEvent]:
        """Extract events from chat region."""
        if not self.chat_parser or not self.profile.chat_region:
            return []
        
        # Extract chat region
        region = self.profile.chat_region
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if y + h > screenshot.shape[0] or x + w > screenshot.shape[1]:
            logger.warning(f"Chat region ({x},{y},{w},{h}) out of bounds")
            return []
        
        chat_region = screenshot[y:y+h, x:x+w]
        
        # Parse chat for events
        events = self.chat_parser.parse_chat_region(chat_region)
        
        return events
