"""Extended StateParser with chat parsing and event fusion capabilities."""

import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple

from holdem.vision.chat_parser import ChatParser, EventSource, GameEvent
from holdem.vision.event_fusion import EventFuser, FusedEvent
from holdem.vision.ocr import OCREngine
from holdem.vision.calibrate import TableProfile
from holdem.vision.parse_state import StateParser
from holdem.vision.cards import CardRecognizer
from holdem.types import TableState, ActionType
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
        vision_metrics: Optional['VisionMetrics'] = None
    ):
        """Initialize chat-enabled state parser.
        
        Args:
            profile: Table calibration profile
            card_recognizer: Card recognition engine
            ocr_engine: OCR engine for text extraction
            enable_chat_parsing: Whether to parse chat for events
            debug_dir: Optional directory for debug images
            vision_metrics: Optional VisionMetrics instance for tracking
        """
        self.profile = profile
        self.state_parser = StateParser(
            profile=profile,
            card_recognizer=card_recognizer,
            ocr_engine=ocr_engine,
            debug_dir=debug_dir,
            vision_metrics=vision_metrics
        )
        
        self.enable_chat_parsing = enable_chat_parsing
        self.chat_parser = ChatParser(ocr_engine) if enable_chat_parsing else None
        self.event_fuser = EventFuser(
            time_window_seconds=5.0,
            confidence_threshold=0.7
        )
        
        self.prev_state: Optional[TableState] = None
    
    def parse(self, screenshot: np.ndarray) -> Optional[TableState]:
        """Parse table state from screenshot (without events).
        
        This method provides compatibility with the standard StateParser interface.
        Use parse_with_events() to get both state and fused events.
        
        Args:
            screenshot: Screenshot of poker table
            
        Returns:
            TableState or None if parsing failed
        """
        state, _ = self.parse_with_events(screenshot)
        return state
    
    def parse_with_events(
        self, 
        screenshot: np.ndarray
    ) -> Tuple[Optional[TableState], List[FusedEvent]]:
        """Parse table state and extract fused events.
        
        Args:
            screenshot: Screenshot of poker table
            
        Returns:
            Tuple of (TableState, List[FusedEvent])
        """
        # Parse vision state
        current_state = self.state_parser.parse(screenshot)
        
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
        
        # Extract chat events if enabled
        chat_events = []
        if self.enable_chat_parsing and self.profile.chat_region:
            chat_events = self._extract_chat_events(screenshot)
            if chat_events:
                logger.info(f"Extracted {len(chat_events)} events from chat")
        
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
