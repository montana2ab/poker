"""Fuse events from multiple sources (vision, chat) for more reliable game state."""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from holdem.types import TableState, PlayerState, ActionType, Street, Card
from holdem.vision.chat_parser import GameEvent, EventSource
from holdem.utils.logging import get_logger

logger = get_logger("vision.event_fusion")


@dataclass
class FusedEvent:
    """Event fused from multiple sources with confidence scoring."""
    event_type: str
    player: Optional[str] = None
    action: Optional[ActionType] = None
    amount: Optional[float] = None
    cards: List[Card] = field(default_factory=list)
    street: Optional[str] = None
    pot_amount: Optional[float] = None
    confidence: float = 1.0
    sources: List[EventSource] = field(default_factory=list)
    source_events: List[GameEvent] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    
    def is_multi_source(self) -> bool:
        """Check if this event was confirmed by multiple sources."""
        return len(set(self.sources)) > 1


class EventFuser:
    """Fuse game events from vision and chat sources."""
    
    def __init__(
        self, 
        time_window_seconds: float = 5.0,
        confidence_threshold: float = 0.5
    ):
        """Initialize event fuser.
        
        Args:
            time_window_seconds: Time window for matching events from different sources
            confidence_threshold: Minimum confidence for accepting single-source events
        """
        self.time_window = timedelta(seconds=time_window_seconds)
        self.confidence_threshold = confidence_threshold
        self._event_buffer: List[GameEvent] = []
    
    def add_events(self, events: List[GameEvent]):
        """Add events to the buffer for fusion."""
        self._event_buffer.extend(events)
        # Keep buffer size manageable
        if len(self._event_buffer) > 100:
            self._event_buffer = self._event_buffer[-50:]
    
    def create_vision_events_from_state(
        self, 
        prev_state: Optional[TableState], 
        current_state: TableState
    ) -> List[GameEvent]:
        """Create GameEvents from vision by comparing table states."""
        events = []
        
        if not prev_state:
            # First observation, just record current state
            return events
        
        # Detect street changes
        if prev_state.street != current_state.street:
            # Extract new cards for this street
            new_cards = []
            if current_state.street == Street.FLOP and len(current_state.board) >= 3:
                new_cards = current_state.board[:3]
            elif current_state.street == Street.TURN and len(current_state.board) >= 4:
                new_cards = [current_state.board[3]]
            elif current_state.street == Street.RIVER and len(current_state.board) >= 5:
                new_cards = [current_state.board[4]]
            
            event = GameEvent(
                event_type="street_change",
                street=current_state.street.name,
                cards=new_cards,
                sources=[EventSource.VISION],
                timestamp=datetime.now(),
                raw_data={'vision': {'prev_street': prev_state.street.name, 
                                    'curr_street': current_state.street.name}}
            )
            events.append(event)
        
        # Detect pot changes
        if abs(current_state.pot - prev_state.pot) > 0.01:
            event = GameEvent(
                event_type="pot_update",
                pot_amount=current_state.pot,
                sources=[EventSource.VISION],
                timestamp=datetime.now(),
                raw_data={'vision': {'prev_pot': prev_state.pot, 
                                    'curr_pot': current_state.pot}}
            )
            events.append(event)
        
        # Detect player actions by comparing bet amounts and folded status
        for i, curr_player in enumerate(current_state.players):
            if i >= len(prev_state.players):
                continue
            
            prev_player = prev_state.players[i]
            
            # Detect fold
            if not prev_player.folded and curr_player.folded:
                event = GameEvent(
                    event_type="action",
                    player=curr_player.name,
                    action=ActionType.FOLD,
                    sources=[EventSource.VISION],
                    timestamp=datetime.now(),
                    raw_data={'vision': {'player_pos': i}}
                )
                events.append(event)
            
            # Detect bet/raise/call by comparing bet amounts
            if not curr_player.folded:
                bet_diff = curr_player.bet_this_round - prev_player.bet_this_round
                
                if bet_diff > 0.01:  # Significant bet increase
                    # Determine action type based on context
                    if prev_state.current_bet < 0.01:
                        action = ActionType.BET
                    elif bet_diff >= prev_state.current_bet:
                        action = ActionType.RAISE
                    else:
                        action = ActionType.CALL
                    
                    event = GameEvent(
                        event_type="action",
                        player=curr_player.name,
                        action=action,
                        amount=curr_player.bet_this_round,
                        sources=[EventSource.VISION],
                        timestamp=datetime.now(),
                        raw_data={'vision': {
                            'player_pos': i,
                            'prev_bet': prev_player.bet_this_round,
                            'curr_bet': curr_player.bet_this_round
                        }}
                    )
                    events.append(event)
        
        return events
    
    def fuse_events(
        self, 
        chat_events: List[GameEvent], 
        vision_events: List[GameEvent]
    ) -> List[FusedEvent]:
        """Fuse events from chat and vision sources."""
        all_events = chat_events + vision_events
        
        if not all_events:
            return []
        
        # Group events by type and player
        fused_events = []
        processed = set()
        
        for i, event in enumerate(all_events):
            if i in processed:
                continue
            
            # Find matching events
            matches = [event]
            for j, other_event in enumerate(all_events):
                if j <= i or j in processed:
                    continue
                
                if self._events_match(event, other_event):
                    matches.append(other_event)
                    processed.add(j)
            
            # Create fused event
            fused = self._create_fused_event(matches)
            if fused:
                fused_events.append(fused)
            
            processed.add(i)
        
        return fused_events
    
    def _events_match(self, event1: GameEvent, event2: GameEvent) -> bool:
        """Check if two events represent the same game event."""
        # Must be same event type
        if event1.event_type != event2.event_type:
            return False
        
        # Must be within time window (if timestamps available)
        if event1.timestamp and event2.timestamp:
            time_diff = abs(event1.timestamp - event2.timestamp)
            if time_diff > self.time_window:
                return False
        
        # Type-specific matching
        if event1.event_type == "action":
            # Must be same player and action type
            return (event1.player == event2.player and 
                   event1.action == event2.action)
        
        elif event1.event_type == "street_change":
            # Must be same street
            return event1.street == event2.street
        
        elif event1.event_type == "pot_update":
            # Must be similar pot amounts (within 5%)
            if event1.pot_amount and event2.pot_amount:
                diff = abs(event1.pot_amount - event2.pot_amount)
                avg = (event1.pot_amount + event2.pot_amount) / 2
                return (diff / max(avg, 0.01)) < 0.05
            return False
        
        elif event1.event_type in ["card_deal", "showdown"]:
            # Must be same player
            return event1.player == event2.player
        
        elif event1.event_type == "pot_win":
            # Must be same player
            return event1.player == event2.player
        
        return False
    
    def _create_fused_event(self, events: List[GameEvent]) -> Optional[FusedEvent]:
        """Create a fused event from matching events."""
        if not events:
            return None
        
        # Use first event as base
        base = events[0]
        
        # Collect all sources
        sources = []
        for event in events:
            sources.extend(event.sources)
        
        # Calculate confidence based on number of sources and consistency
        confidence = self._calculate_confidence(events)
        
        # Merge data from all events
        merged_amount = self._merge_amounts(events)
        merged_cards = self._merge_cards(events)
        merged_pot = self._merge_pot_amounts(events)
        
        return FusedEvent(
            event_type=base.event_type,
            player=base.player,
            action=base.action,
            amount=merged_amount,
            cards=merged_cards,
            street=base.street,
            pot_amount=merged_pot,
            confidence=confidence,
            sources=sources,
            source_events=events,
            timestamp=base.timestamp
        )
    
    def _calculate_confidence(self, events: List[GameEvent]) -> float:
        """Calculate confidence score for fused event."""
        if not events:
            return 0.0
        
        # Base confidence on number of sources
        unique_sources = len(set(e.sources[0] if e.sources else EventSource.VISION 
                                for e in events))
        
        if unique_sources >= 2:
            # Multi-source confirmation gives high confidence
            confidence = 0.95
        else:
            # Single source
            confidence = 0.7
        
        # Adjust based on data consistency
        amounts = [e.amount for e in events if e.amount is not None]
        if len(amounts) > 1:
            avg_amount = sum(amounts) / len(amounts)
            max_diff = max(abs(a - avg_amount) for a in amounts)
            if max_diff / max(avg_amount, 1.0) > 0.1:  # More than 10% difference
                confidence *= 0.9
        
        return min(confidence, 1.0)
    
    def _merge_amounts(self, events: List[GameEvent]) -> Optional[float]:
        """Merge amount values from multiple events."""
        amounts = [e.amount for e in events if e.amount is not None]
        
        if not amounts:
            return None
        
        # If we have chat and vision, prefer chat (more precise)
        chat_amounts = [e.amount for e in events 
                       if e.amount is not None and EventSource.CHAT in e.sources]
        if chat_amounts:
            return chat_amounts[0]
        
        # Otherwise use average
        return sum(amounts) / len(amounts)
    
    def _merge_cards(self, events: List[GameEvent]) -> List[Card]:
        """Merge card lists from multiple events."""
        # Prefer chat cards (more reliable), fallback to vision
        for event in events:
            if event.cards and EventSource.CHAT in event.sources:
                return event.cards
        
        # Use vision cards if no chat cards
        for event in events:
            if event.cards and EventSource.VISION in event.sources:
                return event.cards
        
        return []
    
    def _merge_pot_amounts(self, events: List[GameEvent]) -> Optional[float]:
        """Merge pot amounts from multiple events."""
        pot_amounts = [e.pot_amount for e in events if e.pot_amount is not None]
        
        if not pot_amounts:
            return None
        
        # Prefer chat pot (more precise)
        chat_pots = [e.pot_amount for e in events 
                    if e.pot_amount is not None and EventSource.CHAT in e.sources]
        if chat_pots:
            return chat_pots[0]
        
        # Otherwise use average
        return sum(pot_amounts) / len(pot_amounts)
    
    def get_reliable_events(
        self, 
        fused_events: List[FusedEvent]
    ) -> List[FusedEvent]:
        """Filter fused events to keep only reliable ones."""
        return [
            event for event in fused_events 
            if event.confidence >= self.confidence_threshold
        ]
