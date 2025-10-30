"""Parse complete game state from vision."""

import numpy as np
from typing import Optional
from holdem.types import TableState, PlayerState, Street, Card
from holdem.vision.calibrate import TableProfile
from holdem.vision.cards import CardRecognizer
from holdem.vision.ocr import OCREngine
from holdem.utils.logging import get_logger

logger = get_logger("vision.parse_state")


class StateParser:
    """Parse complete table state from screenshot."""
    
    def __init__(
        self, 
        profile: TableProfile,
        card_recognizer: CardRecognizer,
        ocr_engine: OCREngine
    ):
        self.profile = profile
        self.card_recognizer = card_recognizer
        self.ocr_engine = ocr_engine
    
    def parse(self, screenshot: np.ndarray) -> Optional[TableState]:
        """Parse table state from screenshot."""
        try:
            # Extract community cards
            board = self._parse_board(screenshot)
            
            # Determine street based on board cards
            num_board_cards = len([c for c in board if c is not None])
            if num_board_cards == 0:
                street = Street.PREFLOP
            elif num_board_cards == 3:
                street = Street.FLOP
            elif num_board_cards == 4:
                street = Street.TURN
            elif num_board_cards == 5:
                street = Street.RIVER
            else:
                street = Street.PREFLOP
            
            # Extract pot
            pot = self._parse_pot(screenshot)
            
            # Extract player states
            players = self._parse_players(screenshot)
            
            # Create table state
            state = TableState(
                street=street,
                pot=pot,
                board=[c for c in board if c is not None],
                players=players,
                current_bet=0.0,  # Would need to parse from UI
                small_blind=1.0,
                big_blind=2.0,
                button_position=0
            )
            
            logger.debug(f"Parsed state: {street.name}, pot={pot}, {len(players)} players")
            return state
            
        except Exception as e:
            logger.error(f"Error parsing state: {e}")
            return None
    
    def _parse_board(self, img: np.ndarray) -> list:
        """Parse community cards from image."""
        if not self.profile.card_regions:
            return [None] * 5
        
        region = self.profile.card_regions[0]
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if y + h <= img.shape[0] and x + w <= img.shape[1]:
            card_region = img[y:y+h, x:x+w]
            cards = self.card_recognizer.recognize_cards(card_region, num_cards=5)
            return cards
        
        return [None] * 5
    
    def _parse_pot(self, img: np.ndarray) -> float:
        """Parse pot amount from image."""
        if not self.profile.pot_region:
            return 0.0
        
        region = self.profile.pot_region
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if y + h <= img.shape[0] and x + w <= img.shape[1]:
            pot_region = img[y:y+h, x:x+w]
            pot = self.ocr_engine.extract_number(pot_region)
            return pot if pot is not None else 0.0
        
        return 0.0
    
    def _parse_players(self, img: np.ndarray) -> list:
        """Parse player states from image."""
        players = []
        
        for i, player_region in enumerate(self.profile.player_regions):
            # Extract stack
            stack_reg = player_region.get('stack_region', {})
            x, y, w, h = stack_reg.get('x', 0), stack_reg.get('y', 0), \
                        stack_reg.get('width', 0), stack_reg.get('height', 0)
            
            stack = 1000.0  # Default
            if y + h <= img.shape[0] and x + w <= img.shape[1]:
                stack_img = img[y:y+h, x:x+w]
                parsed_stack = self.ocr_engine.extract_number(stack_img)
                if parsed_stack is not None:
                    stack = parsed_stack
            
            # Extract name
            name_reg = player_region.get('name_region', {})
            x, y, w, h = name_reg.get('x', 0), name_reg.get('y', 0), \
                        name_reg.get('width', 0), name_reg.get('height', 0)
            
            name = f"Player{i}"
            if y + h <= img.shape[0] and x + w <= img.shape[1]:
                name_img = img[y:y+h, x:x+w]
                parsed_name = self.ocr_engine.read_text(name_img)
                if parsed_name:
                    name = parsed_name
            
            player = PlayerState(
                name=name,
                stack=stack,
                position=player_region.get('position', i),
                bet_this_round=0.0,
                folded=False,
                all_in=False
            )
            players.append(player)
        
        return players
