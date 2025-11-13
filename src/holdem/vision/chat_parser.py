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
    CHAT = "chat"
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
    
    # Regex patterns for common poker chat messages
    PATTERNS = {
        # Actions: "Player folds", "Player calls $10", "Player raises to $50"
        'fold': re.compile(r'^(.+?)\s+folds?', re.IGNORECASE),
        'check': re.compile(r'^(.+?)\s+checks?', re.IGNORECASE),
        'call': re.compile(r'^(.+?)\s+calls?\s+\$?([\d,\.]+)', re.IGNORECASE),
        'bet': re.compile(r'^(.+?)\s+bets?\s+\$?([\d,\.]+)', re.IGNORECASE),
        'raise': re.compile(r'^(.+?)\s+raises?\s+(?:to\s+)?\$?([\d,\.]+)', re.IGNORECASE),
        'allin': re.compile(r'^(.+?)\s+(?:is\s+)?all[- ]in', re.IGNORECASE),
        
        # Street changes
        'flop': re.compile(r'\*\*\*\s*flop\s*\*\*\*\s*\[([^\]]+)\]', re.IGNORECASE),
        'turn': re.compile(r'\*\*\*\s*turn\s*\*\*\*\s*\[([^\]]+)\]', re.IGNORECASE),
        'river': re.compile(r'\*\*\*\s*river\s*\*\*\*\s*\[([^\]]+)\]', re.IGNORECASE),
        
        # Card deals
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
            text = self.ocr_engine.read_text(chat_region)
            if not text:
                return []
            
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
            
            logger.debug(f"Extracted {len(lines)} chat lines")
            return lines
            
        except Exception as e:
            logger.error(f"Error extracting chat lines: {e}")
            return []
    
    def parse_chat_line(self, chat_line: ChatLine) -> Optional[GameEvent]:
        """Parse a single chat line and extract game event if present."""
        text = chat_line.text.strip()
        
        if not text:
            return None
        
        # Try to match action patterns
        for action_name, pattern in self.PATTERNS.items():
            match = pattern.search(text)
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
                    sources=[EventSource.CHAT],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            elif pattern_name == 'check':
                return GameEvent(
                    event_type="action",
                    player=match.group(1).strip(),
                    action=ActionType.CHECK,
                    sources=[EventSource.CHAT],
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
                    sources=[EventSource.CHAT],
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
                    sources=[EventSource.CHAT],
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
                    sources=[EventSource.CHAT],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            elif pattern_name == 'allin':
                return GameEvent(
                    event_type="action",
                    player=match.group(1).strip(),
                    action=ActionType.ALLIN,
                    sources=[EventSource.CHAT],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            # Street change events
            elif pattern_name in ['flop', 'turn', 'river']:
                cards_str = match.group(1).strip()
                cards = self._parse_cards(cards_str)
                return GameEvent(
                    event_type="street_change",
                    street=pattern_name.upper(),
                    cards=cards,
                    sources=[EventSource.CHAT],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
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
                    sources=[EventSource.CHAT],
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
                    sources=[EventSource.CHAT],
                    timestamp=chat_line.timestamp,
                    raw_data={'chat': chat_line.text}
                )
            
            # Pot events
            elif pattern_name == 'pot':
                amount = self._parse_amount(match.group(1))
                return GameEvent(
                    event_type="pot_update",
                    pot_amount=amount,
                    sources=[EventSource.CHAT],
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
                    sources=[EventSource.CHAT],
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
        """Parse cards from string like 'Ah Kd' or 'Ah, Kd, Qs'."""
        cards = []
        
        # Remove brackets and split by space or comma
        cards_str = cards_str.replace('[', '').replace(']', '')
        card_tokens = re.split(r'[,\s]+', cards_str.strip())
        
        for token in card_tokens:
            token = token.strip()
            if len(token) >= 2:
                try:
                    # Extract rank and suit (normalize rank to uppercase and suit to lowercase to match Card.from_string() format)
                    rank = token[0].upper()
                    suit = token[1].lower()
                    
                    # Validate rank and suit
                    if rank in '23456789TJQKA' and suit in 'hdcs':
                        cards.append(Card(rank=rank, suit=suit))
                except Exception as e:
                    logger.warning(f"Failed to parse card '{token}': {e}")
        
        return cards
    
    def parse_chat_region(self, chat_region: np.ndarray) -> List[GameEvent]:
        """Extract and parse all events from a chat region."""
        chat_lines = self.extract_chat_lines(chat_region)
        events = []
        
        for line in chat_lines:
            event = self.parse_chat_line(line)
            if event:
                events.append(event)
                logger.debug(f"Parsed event: {event.event_type} from '{line.text}'")
        
        # Update chat history
        self._chat_history.extend(chat_lines)
        
        return events
    
    def get_recent_events(self, max_lines: int = 10) -> List[GameEvent]:
        """Get events from recent chat history."""
        recent_lines = self._chat_history[-max_lines:] if self._chat_history else []
        events = []
        
        for line in recent_lines:
            event = self.parse_chat_line(line)
            if event:
                events.append(event)
        
        return events
