"""Parse and extract information from poker table chat."""

import re
import cv2
import numpy as np
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from holdem.types import Card, ActionType
from holdem.vision.ocr import OCREngine
from holdem.utils.logging import get_logger

logger = get_logger("vision.chat_parser")


class EventSource(Enum):
    """Source of an event."""
    VISION = "vision"
    VISION_STACK = "vision_stack"  # Stack delta tracking
    VISION_BET_REGION = "vision_bet_region"  # OCR from bet region
    VISION_POT = "vision_pot"  # Pot changes
    CHAT = "chat"  # Legacy - same as CHAT_OCR
    CHAT_OCR = "chat_ocr"  # Chat extracted via OCR
    FUSED = "fused"


@dataclass
class ChatLine:
    """Represents a single line from the chat."""
    timestamp: Optional[datetime] = None
    text: str = ""
    raw_text: str = ""  # Original OCR text before cleaning


@dataclass
class GameEvent:
    """Represents a parsed game event with source traceability."""
    event_type: str  # "action", "card_deal", "pot_update", "street_change", "showdown"
    player: Optional[str] = None
    action: Optional[ActionType] = None
    amount: Optional[float] = None
    cards: List[Card] = field(default_factory=list)
    street: Optional[str] = None
    pot_amount: Optional[float] = None
    sources: List[EventSource] = field(default_factory=list)
    confidence: float = 1.0  # Confidence score (0.0-1.0)
    timestamp: Optional[datetime] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)  # Store raw source data
    
    def add_source(self, source: EventSource, data: Optional[Dict[str, Any]] = None):
        """Add a source to this event."""
        if source not in self.sources:
            self.sources.append(source)
        if data:
            self.raw_data[source.value] = data
    
    def is_confirmed(self) -> bool:
        """Check if event is confirmed by multiple sources."""
        return len(self.sources) > 1


class ChatParser:
    """Parse poker table chat and extract game events."""
    
    # Valid ranks and suits for card validation
    VALID_RANKS = 'A23456789TJQK'
    VALID_SUITS = 'shdc'
    
    # Rank correction table - only for first character (rank position)
    RANK_FIX = {
        'B': '8',  # B -> 8
        '&': '8',  # & -> 8
        'O': 'Q',  # O -> Q (Queen more likely than zero in poker)
        'o': 'Q',  # o -> Q
        '0': 'T',  # 0 -> T (Ten)
        'I': 'T',  # I -> T (Ten, not 1 for poker ranks)
        'l': '1',  # l -> 1 (but 1 is not a valid rank, will fail validation)
        'L': 'A',  # L -> A (Ace)
        '1': 'T',  # 1 -> T (Ten)
    }
    
    # Suit correction table - only for second character (suit position)
    SUIT_FIX = {
        '5': 's',  # 5 -> s (spades)
        '$': 's',  # $ -> s (spades)
        'S': 's',  # S -> s (spades)
        'D': 'd',  # D -> d (diamonds)
        '0': 'd',  # 0 -> d (diamonds)
        'O': 'd',  # O -> d (diamonds)
        'o': 'd',  # o -> d (diamonds)
        'b': 'h',  # b -> h (hearts)
        'H': 'h',  # H -> h (hearts)
        'n': 'h',  # n -> h (hearts)
        'C': 'c',  # C -> c (clubs)
        'e': 'c',  # e -> c (clubs)
    }
    
    def __init__(self, ocr_engine: OCREngine):
        self.ocr_engine = ocr_engine
        self._chat_history: List[ChatLine] = []
    
    def _fix_rank(self, char: str) -> Optional[str]:
        """Fix rank character (position 0 of card).
        
        Args:
            char: Original character from rank position
            
        Returns:
            Valid rank if char is valid or can be corrected, None otherwise
        """
        # If already valid, return as-is
        if char in self.VALID_RANKS:
            return char
        
        # Try to correct using RANK_FIX
        corrected = self.RANK_FIX.get(char)
        if corrected and corrected in self.VALID_RANKS:
            return corrected
        
        # Cannot be corrected to valid rank
        return None
    
    def _fix_suit(self, char: str) -> Optional[str]:
        """Fix suit character (position 1 of card).
        
        Args:
            char: Original character from suit position
            
        Returns:
            Valid suit if char is valid or can be corrected, None otherwise
        """
        # If already valid, return as-is (CRITICAL: never transform valid suits)
        if char in self.VALID_SUITS:
            return char
        
        # Try to correct using SUIT_FIX
        corrected = self.SUIT_FIX.get(char)
        if corrected and corrected in self.VALID_SUITS:
            return corrected
        
        # Cannot be corrected to valid suit
        return None
    
    def fix_card(self, raw: str) -> Optional[str]:
        """Fix and validate a card string from OCR output.
        
        This function:
        1. Cleans the input (removes brackets, parentheses, commas, spaces)
        2. Validates it's exactly 2 characters after cleaning
        3. Fixes the rank (position 0) using _fix_rank
        4. Fixes the suit (position 1) using _fix_suit
        5. Returns the corrected card or None if invalid
        
        Args:
            raw: Raw card string from OCR (e.g., "8s", "[Bd]", "3d")
            
        Returns:
            Corrected card string (e.g., "8s", "8d", "3d") or None if invalid
        """
        if not raw:
            return None
        
        # Clean the string - remove brackets, parentheses, commas, spaces
        cleaned = raw.strip()
        for char in '[](),\t ':
            cleaned = cleaned.replace(char, '')
        
        # Must be exactly 2 characters after cleaning
        if len(cleaned) != 2:
            return None
        
        # Extract and fix rank (position 0)
        rank_char = cleaned[0].upper()  # Ranks are uppercase
        fixed_rank = self._fix_rank(rank_char)
        if fixed_rank is None:
            return None
        
        # Extract and fix suit (position 1)
        suit_char = cleaned[1].lower()  # Suits are lowercase
        fixed_suit = self._fix_suit(suit_char)
        if fixed_suit is None:
            return None
        
        # Both rank and suit are valid
        return fixed_rank + fixed_suit
    
    # Regex patterns for common poker chat messages
    PATTERNS = {
        # Actions: "Player folds", "Player calls $10", "Player raises to $50"
        'fold': re.compile(r'^(.+?)\s+folds?', re.IGNORECASE),
        'check': re.compile(r'^(.+?)\s+checks?', re.IGNORECASE),
        'call': re.compile(r'^(.+?)\s+calls?\s+\$?([\d,\.]+)', re.IGNORECASE),
        'bet': re.compile(r'^(.+?)\s+bets?\s+\$?([\d,\.]+)', re.IGNORECASE),
        'raise': re.compile(r'^(.+?)\s+raises?\s+(?:to\s+)?\$?([\d,\.]+)', re.IGNORECASE),
        'allin': re.compile(r'^(.+?)\s+(?:is\s+)?all[- ]in', re.IGNORECASE),
        'leave': re.compile(r'^(.+?)\s+leaves?\s+(?:the\s+)?table', re.IGNORECASE),
        
        # Blinds and antes - for button detection
        'post_sb': re.compile(r'^(.+?):\s+posts?\s+small\s+blind\s+\$?([\d,\.]+)', re.IGNORECASE),
        'post_bb': re.compile(r'^(.+?):\s+posts?\s+(?:big\s+)?blind\s+\$?([\d,\.]+)', re.IGNORECASE),
        'post_ante': re.compile(r'^(.+?):\s+posts?\s+(?:the\s+)?ante\s+\$?([\d,\.]+)', re.IGNORECASE),
        
        # Street changes
        'flop': re.compile(r'\*\*\*\s*flop\s*\*\*\*\s*\[([^\]]+)\]', re.IGNORECASE),
        'turn': re.compile(r'\*\*\*\s*turn\s*\*\*\*\s*\[([^\]]+)\]', re.IGNORECASE),
        'river': re.compile(r'\*\*\*\s*river\s*\*\*\*\s*\[([^\]]+)\]', re.IGNORECASE),
        
        # Card deals - Board dealing (to be filtered from action events)
        'dealing_flop': re.compile(r'dealing\s+flop:\s*\[([^\]]+)\]', re.IGNORECASE),
        'dealing_turn': re.compile(r'dealing\s+turn:\s*\[([^\]]+)\]', re.IGNORECASE),
        'dealing_river': re.compile(r'dealing\s+river:\s*\[([^\]]+)\]', re.IGNORECASE),
        
        # Card deals - Player cards
        'hole_cards': re.compile(r'dealt\s+to\s+(.+?)\s+\[([^\]]+)\]', re.IGNORECASE),
        
        # Showdown
        'shows': re.compile(r'^(.+?)\s+shows?\s+\[([^\]]+)\]', re.IGNORECASE),
        
        # Pot
        'pot': re.compile(r'pot\s+(?:is\s+)?\$?([\d,\.]+)', re.IGNORECASE),
        'wins': re.compile(r'^(.+?)\s+wins?\s+\$?([\d,\.]+)', re.IGNORECASE),
    }
    
    def __init__(self, ocr_engine: OCREngine):
        self.ocr_engine = ocr_engine
        self._chat_history: List[ChatLine] = []
    
    def extract_chat_lines(self, chat_region: np.ndarray) -> List[ChatLine]:
        """Extract chat lines from a chat region image using OCR."""
        try:
            # Use OCR to extract text
            logger.debug("[CHAT OCR] Running OCR on chat region")
            text = self.ocr_engine.read_text(chat_region)
            if not text:
                logger.debug("[CHAT OCR] No text extracted from chat region")
                return []
            
            # Log raw OCR output
            logger.debug(f"[CHAT OCR] Raw text: {repr(text[:200])}")  # First 200 chars
            
            # Split into lines and create ChatLine objects
            lines = []
            for line_text in text.split('\n'):
                line_text = line_text.strip()
                if line_text:
                    chat_line = ChatLine(
                        text=line_text,
                        raw_text=line_text,
                        timestamp=datetime.now()
                    )
                    lines.append(chat_line)
                    logger.debug(f"[CHAT OCR] Line: {line_text}")
            
            logger.info(f"[CHAT OCR] Extracted {len(lines)} chat lines")
            return lines
            
        except Exception as e:
            logger.error(f"[CHAT OCR] Error extracting chat lines: {e}")
            return []
    
    def parse_chat_line(self, chat_line: ChatLine) -> Optional[GameEvent]:
        """Parse a single chat line and extract game event if present.
        
        DEPRECATED: Use parse_chat_line_multi() for better multi-action support.
        This method is kept for backward compatibility and returns only the first event.
        """
        events = self.parse_chat_line_multi(chat_line)
        return events[0] if events else None
    
    def parse_chat_line_multi(self, chat_line: ChatLine) -> List[GameEvent]:
        """Parse a single chat line and extract multiple game events if present.
        
        This method can extract multiple actions from a single line, e.g.:
        "Dealer: Rapyxa bets 850 Dealer: daly43 calls 850 Dealer: palianica folds"
        will return 3 events.
        
        Args:
            chat_line: The chat line to parse
            
        Returns:
            List of GameEvent objects extracted from the line
        """
        text = chat_line.text.strip()
        
        if not text:
            return []
        
        events = []
        
        # Check if line contains "Dealer:" delimiter (multi-action format) - case insensitive
        text_lower = text.lower()
        if "dealer:" in text_lower:
            # Split by "Dealer:" to get individual segments
            segments = re.split(r'Dealer:\s*', text, flags=re.IGNORECASE)
            
            # Parse each non-empty segment
            for segment in segments:
                segment = segment.strip()
                if not segment:
                    continue
                
                # Skip board dealing segments
                if self._is_board_dealing(segment):
                    logger.debug(f"Skipping board dealing segment: '{segment}'")
                    continue
                
                # Try to parse action from segment
                event = self._parse_segment(segment, chat_line)
                if event:
                    events.append(event)
        else:
            # Single action format - use existing pattern matching
            # Prioritize board dealing patterns first to avoid conflicts
            board_patterns = ['dealing_flop', 'dealing_turn', 'dealing_river', 'flop', 'turn', 'river']
            for action_name in board_patterns:
                pattern = self.PATTERNS.get(action_name)
                if pattern:
                    match = pattern.search(text)
                    if match:
                        event = self._create_event_from_match(action_name, match, chat_line)
                        if event:
                            events.append(event)
                        return events  # Return immediately for board events
            
            # Then check other patterns
            for action_name, pattern in self.PATTERNS.items():
                if action_name not in board_patterns:
                    match = pattern.search(text)
                    if match:
                        event = self._create_event_from_match(action_name, match, chat_line)
                        if event:
                            events.append(event)
                        break  # Only return first match for non-Dealer format
        
        if events:
            logger.debug(f"Extracted {len(events)} events from chat line: '{text}'")
        
        return events
    
    def _is_board_dealing(self, segment: str) -> bool:
        """Check if a segment is a board dealing announcement.
        
        Args:
            segment: Text segment to check
            
        Returns:
            True if segment is a board dealing announcement, False otherwise
        """
        segment_lower = segment.lower()
        # Check for common board dealing patterns
        return ('dealing flop' in segment_lower or 
                'dealing turn' in segment_lower or 
                'dealing river' in segment_lower)
    
    def _is_informational_message(self, segment: str) -> bool:
        """Check if a segment is an informational message (not a player action).
        
        Informational messages should not be converted into CHECK actions.
        
        Args:
            segment: Text segment to check
            
        Returns:
            True if segment is informational, False otherwise
        """
        segment_lower = segment.lower()
        # Common informational patterns that should NOT become actions
        informational_patterns = [
            "it's your turn",
            "your turn",
            "waiting for",
            "please make a decision",
            "time bank",
            "has timed out",
            "disconnected",
            "reconnected",
            "sitting out",
            "back",
        ]
        return any(pattern in segment_lower for pattern in informational_patterns)
    
    def _parse_segment(self, segment: str, chat_line: ChatLine) -> Optional[GameEvent]:
        """Parse a single segment and extract game event if present.
        
        Args:
            segment: Text segment to parse
            chat_line: Original chat line for metadata
            
        Returns:
            GameEvent if pattern matches, None otherwise
        """
        segment = segment.strip()
        
        if not segment:
            return None
        
        # Filter out informational messages - they should NOT become actions
        if self._is_informational_message(segment):
            logger.debug(f"Skipping informational message: '{segment}'")
            return None
        
        # Try to match action patterns (prioritize action patterns)
        action_patterns = ['fold', 'check', 'call', 'bet', 'raise', 'allin', 'leave']
        
        for action_name in action_patterns:
            pattern = self.PATTERNS.get(action_name)
            if pattern:
                match = pattern.search(segment)
                if match:
                    return self._create_event_from_match(action_name, match, chat_line)
        
        # Try other patterns
        for action_name, pattern in self.PATTERNS.items():
            if action_name not in action_patterns:
                match = pattern.search(segment)
                if match:
                    return self._create_event_from_match(action_name, match, chat_line)
        
        return None
    
    def _create_event_from_match(
        self, 
        pattern_name: str, 
        match: re.Match, 
        chat_line: ChatLine
    ) -> Optional[GameEvent]:
        """Create a GameEvent from a regex match."""
        try:
            # Action events
            if pattern_name == 'fold':
                return GameEvent(
                    event_type="action",
                    player=match.group(1).strip(),
                    action=ActionType.FOLD,
                    sources=[EventSource.CHAT_OCR],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            elif pattern_name == 'check':
                return GameEvent(
                    event_type="action",
                    player=match.group(1).strip(),
                    action=ActionType.CHECK,
                    sources=[EventSource.CHAT_OCR],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            elif pattern_name == 'call':
                amount = self._parse_amount(match.group(2))
                return GameEvent(
                    event_type="action",
                    player=match.group(1).strip(),
                    action=ActionType.CALL,
                    amount=amount,
                    sources=[EventSource.CHAT_OCR],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            elif pattern_name == 'bet':
                amount = self._parse_amount(match.group(2))
                return GameEvent(
                    event_type="action",
                    player=match.group(1).strip(),
                    action=ActionType.BET,
                    amount=amount,
                    sources=[EventSource.CHAT_OCR],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            elif pattern_name == 'raise':
                amount = self._parse_amount(match.group(2))
                return GameEvent(
                    event_type="action",
                    player=match.group(1).strip(),
                    action=ActionType.RAISE,
                    amount=amount,
                    sources=[EventSource.CHAT_OCR],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            elif pattern_name == 'allin':
                return GameEvent(
                    event_type="action",
                    player=match.group(1).strip(),
                    action=ActionType.ALLIN,
                    sources=[EventSource.CHAT_OCR],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            elif pattern_name == 'leave':
                return GameEvent(
                    event_type="action",
                    player=match.group(1).strip(),
                    action=ActionType.FOLD,  # Treat leave as fold for action tracking
                    sources=[EventSource.CHAT_OCR],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text, 'original_action': 'leave'}
                )
            
            # Blind and ante events - for button detection
            elif pattern_name == 'post_sb':
                player = match.group(1).strip()
                amount = self._parse_amount(match.group(2))
                return GameEvent(
                    event_type="post_small_blind",
                    player=player,
                    amount=amount,
                    sources=[EventSource.CHAT_OCR],
                    confidence=0.95,
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            elif pattern_name == 'post_bb':
                player = match.group(1).strip()
                amount = self._parse_amount(match.group(2))
                return GameEvent(
                    event_type="post_big_blind",
                    player=player,
                    amount=amount,
                    sources=[EventSource.CHAT_OCR],
                    confidence=0.95,
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            elif pattern_name == 'post_ante':
                player = match.group(1).strip()
                amount = self._parse_amount(match.group(2))
                return GameEvent(
                    event_type="post_ante",
                    player=player,
                    amount=amount,
                    sources=[EventSource.CHAT_OCR],
                    confidence=0.95,
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            # Street change events (*** FLOP *** format)
            elif pattern_name in ['flop', 'turn', 'river']:
                cards_str = match.group(1).strip()
                cards = self._parse_cards(cards_str)
                logger.info(
                    f"[CHAT BOARD] Detected {pattern_name.upper()} from chat: "
                    f"{[str(c) for c in cards]} (confidence=0.90)"
                )
                return GameEvent(
                    event_type="board_update",
                    street=pattern_name.upper(),
                    cards=cards,
                    sources=[EventSource.CHAT_OCR],
                    confidence=0.9,  # High confidence for chat board
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text, 'format': 'street_marker'}
                )
            
            # Board dealing events (Dealing Flop/Turn/River format)
            elif pattern_name in ['dealing_flop', 'dealing_turn', 'dealing_river']:
                cards_str = match.group(1).strip()
                cards = self._parse_cards(cards_str)
                street_name = pattern_name.replace('dealing_', '').upper()
                logger.info(
                    f"[CHAT BOARD] Detected {street_name} from chat: "
                    f"{[str(c) for c in cards]} (confidence=0.90)"
                )
                return GameEvent(
                    event_type="board_update",
                    street=street_name,
                    cards=cards,
                    sources=[EventSource.CHAT_OCR],
                    confidence=0.9,  # High confidence for chat board
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text, 'format': 'dealing'}
                )
            
            # Card deal events
            elif pattern_name == 'hole_cards':
                player = match.group(1).strip()
                cards_str = match.group(2).strip()
                cards = self._parse_cards(cards_str)
                return GameEvent(
                    event_type="card_deal",
                    player=player,
                    cards=cards,
                    sources=[EventSource.CHAT_OCR],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            # Showdown events
            elif pattern_name == 'shows':
                player = match.group(1).strip()
                cards_str = match.group(2).strip()
                cards = self._parse_cards(cards_str)
                return GameEvent(
                    event_type="showdown",
                    player=player,
                    cards=cards,
                    sources=[EventSource.CHAT_OCR],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            # Pot events
            elif pattern_name == 'pot':
                amount = self._parse_amount(match.group(1))
                return GameEvent(
                    event_type="pot_update",
                    pot_amount=amount,
                    sources=[EventSource.CHAT_OCR],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            elif pattern_name == 'wins':
                player = match.group(1).strip()
                amount = self._parse_amount(match.group(2))
                return GameEvent(
                    event_type="pot_win",
                    player=player,
                    pot_amount=amount,
                    sources=[EventSource.CHAT_OCR],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
        except Exception as e:
            logger.error(f"Error creating event from match: {e}")
            return None
        
        return None
    
    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse amount from string, handling various formats."""
        if not amount_str:
            return None
        
        # Remove currency symbols and whitespace
        amount_str = re.sub(r'[$€£¥]', '', amount_str).strip()
        
        # Remove thousands separators (commas)
        amount_str = amount_str.replace(',', '')
        
        try:
            amount = float(amount_str)
            # Validate that amount is non-negative
            if amount < 0:
                logger.warning(f"Negative amount rejected: {amount_str}")
                return None
            return amount
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse amount: {amount_str}")
            return None
    
    def _parse_cards(self, cards_str: str) -> List[Card]:
        """Parse cards from string like 'Ah Kd' or 'Ah, Kd, Qs'.
        
        Uses the new fix_card() function for OCR error correction with separate
        rank and suit correction tables. Never transforms already valid suits.
        """
        cards = []
        
        # Remove brackets and split by space or comma
        cards_str = cards_str.replace('[', '').replace(']', '')
        card_tokens = re.split(r'[,\s]+', cards_str.strip())
        
        for token in card_tokens:
            token = token.strip()
            if not token:
                continue
            
            try:
                # Use the new fix_card function for correction
                fixed = self.fix_card(token)
                
                if fixed:
                    # Extract rank and suit from the fixed card
                    rank = fixed[0]
                    suit = fixed[1]
                    cards.append(Card(rank=rank, suit=suit))
                    
                    # Log if correction was applied
                    if token != fixed:
                        logger.info(f"[CHAT CARD FIX] Accepted corrected card '{fixed}' (original: '{token}')")
                else:
                    # Card could not be corrected
                    logger.warning(f"[CHAT CARD FIX] Invalid card after correction: '{token}'")
                    
            except Exception as e:
                logger.warning(f"Failed to parse card '{token}': {e}")
        
        return cards
    
    def parse_chat_region(self, chat_region: np.ndarray) -> List[GameEvent]:
        """Extract and parse all events from a chat region."""
        chat_lines = self.extract_chat_lines(chat_region)
        events = []
        
        for line in chat_lines:
            # Use multi-event parsing to extract multiple actions per line
            line_events = self.parse_chat_line_multi(line)
            if line_events:
                events.extend(line_events)
                for event in line_events:
                    # Log each event with details
                    logger.info(
                        f"[CHAT OCR] Event created: type={event.event_type}, "
                        f"player={event.player}, action={event.action}, "
                        f"amount={event.amount}, source=chat_ocr"
                    )
        
        if events:
            logger.info(f"[CHAT OCR] Total events extracted: {len(events)}")
        else:
            logger.debug("[CHAT OCR] No events extracted from chat")
        
        # Update chat history
        self._chat_history.extend(chat_lines)
        
        return events
    
    def get_recent_events(self, max_lines: int = 10) -> List[GameEvent]:
        """Get events from recent chat history."""
        recent_lines = self._chat_history[-max_lines:] if self._chat_history else []
        events = []
        
        for line in recent_lines:
            # Use multi-event parsing to extract multiple actions per line
            line_events = self.parse_chat_line_multi(line)
            if line_events:
                events.extend(line_events)
        
        return events
