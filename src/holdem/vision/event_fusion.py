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
        self._previous_stacks: Dict[int, float] = {}  # Track previous stack for each player
        self._previous_pot: float = 0.0  # Track previous pot
    
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
        """Create GameEvents from vision by comparing table states.
        
        This includes:
        - Street changes
        - Pot updates
        - Player actions (from bet_this_round changes)
        - Stack delta tracking (new: reconstruct actions from stack evolution)
        """
        events = []
        
        # Validate inputs
        if current_state is None:
            logger.warning("Current state is None, cannot create vision events")
            return events
        
        if not prev_state:
            # First observation, initialize stack tracking
            for i, player in enumerate(current_state.players):
                self._previous_stacks[i] = player.stack
            self._previous_pot = current_state.pot
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
            
            # Reset bet tracking on street change
            for i, player in enumerate(current_state.players):
                self._previous_stacks[i] = player.stack
        
        # Detect pot changes
        delta_pot = current_state.pot - self._previous_pot
        if abs(delta_pot) > 0.01:
            event = GameEvent(
                event_type="pot_update",
                pot_amount=current_state.pot,
                sources=[EventSource.VISION_POT],
                timestamp=datetime.now(),
                raw_data={'vision_pot': {
                    'prev_pot': self._previous_pot, 
                    'curr_pot': current_state.pot,
                    'delta_pot': delta_pot
                }}
            )
            events.append(event)
            self._previous_pot = current_state.pot
        
        # Track stack deltas for each player
        stack_changes = []
        for i, curr_player in enumerate(current_state.players):
            if i >= len(prev_state.players):
                continue
            
            prev_player = prev_state.players[i]
            prev_stack = self._previous_stacks.get(i, prev_player.stack)
            delta_stack = curr_player.stack - prev_stack
            
            if abs(delta_stack) > 0.01:
                stack_changes.append({
                    'player_pos': i,
                    'player_name': curr_player.name,
                    'prev_stack': prev_stack,
                    'curr_stack': curr_player.stack,
                    'delta_stack': delta_stack,
                    'prev_bet': prev_player.bet_this_round,
                    'curr_bet': curr_player.bet_this_round
                })
            
            # Update tracked stack
            self._previous_stacks[i] = curr_player.stack
        
        # Reconstruct actions from stack changes
        if stack_changes:
            logger.debug(f"Detected {len(stack_changes)} stack changes")
            
            for change in stack_changes:
                delta_stack = change['delta_stack']
                
                # Negative delta means player put money in
                if delta_stack < -0.01:
                    amount_put_in = abs(delta_stack)
                    player_pos = change['player_pos']
                    curr_player = current_state.players[player_pos]
                    
                    # Validate that the amount is reasonable
                    # Skip if amount seems invalid (too small or inconsistent with game state)
                    if not self._is_valid_action_amount(
                        amount_put_in, 
                        curr_player.bet_this_round,
                        current_state.pot,
                        prev_state.pot,
                        delta_pot
                    ):
                        logger.warning(
                            f"Skipping invalid stack delta for player {player_pos} "
                            f"({curr_player.name}): delta={delta_stack:.2f}, "
                            f"curr_bet={curr_player.bet_this_round:.2f}, pot_delta={delta_pot:.2f}"
                        )
                        continue
                    
                    # Determine action type based on context
                    action_type = self._infer_action_from_stack_delta(
                        amount_put_in=amount_put_in,
                        curr_bet=curr_player.bet_this_round,
                        prev_bet=change['prev_bet'],
                        current_state_bet=current_state.current_bet,
                        prev_state_bet=prev_state.current_bet,
                        player_stack=curr_player.stack
                    )
                    
                    # Only create event if we have a valid amount (never create BET 0.0)
                    event_amount = curr_player.bet_this_round
                    if event_amount < 0.01 and action_type not in [ActionType.CHECK, ActionType.FOLD]:
                        logger.warning(
                            f"Skipping action event with zero/invalid amount: "
                            f"player={curr_player.name}, action={action_type.value}, "
                            f"amount={event_amount:.2f}"
                        )
                        continue
                    
                    event = GameEvent(
                        event_type="action",
                        player=curr_player.name,
                        action=action_type,
                        amount=event_amount,
                        sources=[EventSource.VISION_STACK],
                        confidence=0.75,  # Medium confidence for stack-inferred actions
                        timestamp=datetime.now(),
                        raw_data={'vision_stack': change}
                    )
                    events.append(event)
                    logger.info(
                        f"Inferred action from stack delta: Player {player_pos} "
                        f"({curr_player.name}) - {action_type.value} "
                        f"(delta: {delta_stack:.2f}, bet_amount: {event_amount:.2f})"
                    )
                
                # Positive delta could be winning a pot or error
                elif delta_stack > 0.01:
                    logger.debug(
                        f"Player {change['player_pos']} ({change['player_name']}) "
                        f"stack increased by {delta_stack:.2f} - possible pot win or OCR error"
                    )
        
        # Detect player actions by comparing bet amounts (existing logic)
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
                        sources=[EventSource.VISION_BET_REGION],
                        timestamp=datetime.now(),
                        raw_data={'vision': {
                            'player_pos': i,
                            'prev_bet': prev_player.bet_this_round,
                            'curr_bet': curr_player.bet_this_round
                        }}
                    )
                    events.append(event)
        
        return events
    
    def _is_valid_action_amount(
        self,
        amount_put_in: float,
        curr_bet: float,
        curr_pot: float,
        prev_pot: float,
        delta_pot: float
    ) -> bool:
        """Validate that an action amount is reasonable.
        
        This prevents creating events with invalid amounts (like BET 0.0) due to:
        - OCR errors
        - Scale mismatches (e.g., 4.74 vs 4736)
        - Timing issues
        
        Args:
            amount_put_in: Amount inferred from stack delta
            curr_bet: Current bet amount for this player
            curr_pot: Current pot size
            prev_pot: Previous pot size
            delta_pot: Change in pot
            
        Returns:
            True if amount seems valid, False otherwise
        """
        # Amount must be positive and non-zero for betting actions
        if amount_put_in < 0.01:
            logger.debug(f"Invalid amount: too small ({amount_put_in:.2f})")
            return False
        
        # Check if stack delta is consistent with pot change
        # Allow some tolerance for rounding and multiple players acting
        if abs(delta_pot) > 0.01:
            # If pot changed significantly, at least one amount should be in similar range
            max_discrepancy = max(abs(delta_pot), abs(amount_put_in)) * 0.5
            if abs(abs(delta_pot) - abs(amount_put_in)) > max_discrepancy:
                # Possible scale mismatch (e.g., 4.74 vs 4736)
                logger.debug(
                    f"Possible scale mismatch: amount_put_in={amount_put_in:.2f}, "
                    f"delta_pot={delta_pot:.2f}"
                )
                # Don't reject, but flag for low confidence
        
        # If curr_bet is zero but we detected a stack change, something is off
        if curr_bet < 0.01 and amount_put_in > 0.01:
            logger.debug(
                f"Suspicious: stack delta suggests action ({amount_put_in:.2f}) "
                f"but curr_bet is zero"
            )
            # This might be a timing issue - OCR read stack before bet was updated
            # Allow it but it will have lower confidence
        
        return True
    
    def _infer_action_from_stack_delta(
        self,
        amount_put_in: float,
        curr_bet: float,
        prev_bet: float,
        current_state_bet: float,
        prev_state_bet: float,
        player_stack: float
    ) -> ActionType:
        """Infer action type from stack delta and context.
        
        Args:
            amount_put_in: Amount the player put into the pot (positive value)
            curr_bet: Player's current bet this round
            prev_bet: Player's previous bet this round
            current_state_bet: Current highest bet in the state
            prev_state_bet: Previous highest bet in the state
            player_stack: Player's remaining stack
            
        Returns:
            Inferred action type
        """
        # Check if all-in (stack is now 0 or very small)
        if player_stack < 0.01:
            return ActionType.ALLIN
        
        # If no one had bet before, this is a BET
        if prev_state_bet < 0.01:
            return ActionType.BET
        
        # If player's bet equals the previous highest bet, this is a CALL
        if abs(curr_bet - prev_state_bet) < 0.01:
            return ActionType.CALL
        
        # If player's bet is higher than previous highest bet, this is a RAISE
        if curr_bet > prev_state_bet + 0.01:
            return ActionType.RAISE
        
        # Default to BET if unclear
        return ActionType.BET
    
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
        
        # Collect unique source types
        unique_sources = set()
        for e in events:
            if e.sources:
                unique_sources.update(e.sources)
        
        # Base confidence on number and type of sources
        if len(unique_sources) >= 3:
            # Three or more different sources is very high confidence
            confidence = 0.98
        elif len(unique_sources) == 2:
            # Two sources is high confidence
            # Check if we have chat + vision, that's best
            if EventSource.CHAT in unique_sources:
                confidence = 0.95
            # Stack + bet region is also good
            elif (EventSource.VISION_STACK in unique_sources and 
                  EventSource.VISION_BET_REGION in unique_sources):
                confidence = 0.90
            # Stack + pot is decent
            elif (EventSource.VISION_STACK in unique_sources and 
                  EventSource.VISION_POT in unique_sources):
                confidence = 0.85
            else:
                confidence = 0.85
        else:
            # Single source - confidence depends on which one
            single_source = list(unique_sources)[0] if unique_sources else EventSource.VISION
            if single_source == EventSource.CHAT:
                confidence = 0.85  # Chat is pretty reliable
            elif single_source == EventSource.VISION_BET_REGION:
                confidence = 0.70  # Bet OCR can be noisy
            elif single_source == EventSource.VISION_STACK:
                confidence = 0.75  # Stack tracking is reasonably good
            elif single_source == EventSource.VISION_POT:
                confidence = 0.70  # Pot OCR can be noisy
            else:
                confidence = 0.65  # Generic vision
        
        # Adjust based on data consistency
        amounts = [e.amount for e in events if e.amount is not None]
        if len(amounts) > 1:
            avg_amount = sum(amounts) / len(amounts)
            max_diff = max(abs(a - avg_amount) for a in amounts)
            if avg_amount > 0.01:
                rel_diff = max_diff / avg_amount
                if rel_diff > 0.15:  # More than 15% difference
                    confidence *= 0.85
                elif rel_diff > 0.05:  # More than 5% difference
                    confidence *= 0.95
        
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
