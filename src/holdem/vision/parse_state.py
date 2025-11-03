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
    
    def _is_valid_region(self, x: int, y: int, w: int, h: int, img_shape: tuple) -> bool:
        """Check if region is within image bounds and has valid dimensions."""
        return (x >= 0 and y >= 0 and w > 0 and h > 0 and 
                y + h <= img_shape[0] and 
                x + w <= img_shape[1])
    
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
            logger.debug("No card regions defined in profile")
            return [None] * 5
        
        region = self.profile.card_regions[0]
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if self._is_valid_region(x, y, w, h, img.shape):
            card_region = img[y:y+h, x:x+w]
            cards = self.card_recognizer.recognize_cards(card_region, num_cards=5)
            
            # Log detected cards
            card_strs = [str(c) if c else "??" for c in cards]
            logger.debug(f"Board cards detected: {' '.join(card_strs)}")
            
            return cards
        else:
            logger.warning(f"Card region out of bounds: ({x},{y},{w},{h}) vs image {img.shape}")
        
        return [None] * 5
    
    def _parse_pot(self, img: np.ndarray) -> float:
        """Parse pot amount from image."""
        if not self.profile.pot_region:
            logger.debug("No pot region defined in profile")
            return 0.0
        
        region = self.profile.pot_region
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if self._is_valid_region(x, y, w, h, img.shape):
            pot_region = img[y:y+h, x:x+w]
            pot = self.ocr_engine.extract_number(pot_region)
            
            if pot is not None:
                logger.debug(f"Pot detected: {pot}")
            else:
                logger.debug("Pot OCR failed - no number detected")
            
            return pot if pot is not None else 0.0
        else:
            logger.warning(f"Pot region out of bounds: ({x},{y},{w},{h}) vs image {img.shape}")
        
        return 0.0
    
    def _parse_players(self, img: np.ndarray) -> list:
        """Parse player states from image."""
        players = []
        
        if not self.profile.player_regions:
            logger.debug("No player regions defined in profile")
            return players
        
        for i, player_region in enumerate(self.profile.player_regions):
            # Extract stack
            stack_reg = player_region.get('stack_region', {})
            x, y, w, h = stack_reg.get('x', 0), stack_reg.get('y', 0), \
                        stack_reg.get('width', 0), stack_reg.get('height', 0)
            
            stack = 1000.0  # Default
            if self._is_valid_region(x, y, w, h, img.shape):
                stack_img = img[y:y+h, x:x+w]
                parsed_stack = self.ocr_engine.extract_number(stack_img)
                if parsed_stack is not None:
                    stack = parsed_stack
                    logger.debug(f"Player {i} stack detected: {stack}")
                else:
                    logger.debug(f"Player {i} stack OCR failed")
            
            # Extract name
            name_reg = player_region.get('name_region', {})
            x, y, w, h = name_reg.get('x', 0), name_reg.get('y', 0), \
                        name_reg.get('width', 0), name_reg.get('height', 0)
            
            name = f"Player{i}"
            if self._is_valid_region(x, y, w, h, img.shape):
                name_img = img[y:y+h, x:x+w]
                parsed_name = self.ocr_engine.read_text(name_img)
                if parsed_name:
                    name = parsed_name
                    logger.debug(f"Player {i} name detected: {name}")
            
            # Extract player cards if region exists
            # Note: Cards are logged for debugging but not stored in PlayerState
            # as the current TableState design doesn't include player hole cards
            # (those would be tracked separately by the bot for the hero only)
            card_reg = player_region.get('card_region', {})
            x, y, w, h = card_reg.get('x', 0), card_reg.get('y', 0), \
                        card_reg.get('width', 0), card_reg.get('height', 0)
            
            if self._is_valid_region(x, y, w, h, img.shape):
                card_img = img[y:y+h, x:x+w]
                cards = self.card_recognizer.recognize_cards(card_img, num_cards=2)
                card_strs = [str(c) if c else "??" for c in cards]
                logger.debug(f"Player {i} cards: {' '.join(card_strs)}")
            
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
