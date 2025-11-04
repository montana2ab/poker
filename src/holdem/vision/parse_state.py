"""Parse complete game state from vision."""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, List
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
        ocr_engine: OCREngine,
        debug_dir: Optional[Path] = None
    ):
        self.profile = profile
        self.card_recognizer = card_recognizer
        self.ocr_engine = ocr_engine
        self.debug_dir = debug_dir
        self._debug_counter = 0
    
    def parse(self, screenshot: np.ndarray) -> Optional[TableState]:
        """Parse table state from screenshot."""
        try:
            # Increment debug counter for each parse call
            if self.debug_dir:
                self._debug_counter += 1
            
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
            logger.warning("No card regions defined in profile")
            return [None] * 5
        
        region = self.profile.card_regions[0]
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if y + h <= img.shape[0] and x + w <= img.shape[1]:
            card_region = img[y:y+h, x:x+w]
            logger.debug(f"Extracting board cards from region ({x},{y},{w},{h})")
            
            # Save debug image if debug mode is enabled
            if self.debug_dir:
                debug_path = self.debug_dir / f"board_region_{self._debug_counter:04d}.png"
                try:
                    success = cv2.imwrite(str(debug_path), card_region)
                    if success:
                        logger.debug(f"Saved board region to {debug_path}")
                    else:
                        logger.warning(f"Failed to save debug image to {debug_path}")
                except Exception as e:
                    logger.warning(f"Error saving debug image: {e}")
            
            cards = self.card_recognizer.recognize_cards(card_region, num_cards=5)
            
            # Log the result
            cards_str = ", ".join(str(c) for c in cards if c is not None)
            if cards_str:
                num_recognized = len([c for c in cards if c is not None])
                logger.info(f"Recognized {num_recognized} board card(s): {cards_str}")
            else:
                logger.warning("No board cards recognized - check card templates and region coordinates")
            
            return cards
        else:
            logger.error(f"Card region ({x},{y},{w},{h}) out of bounds for image shape {img.shape}")
        
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
            
            # Extract hole cards for hero player
            hole_cards = None
            if self.profile.hero_position is not None and i == self.profile.hero_position:
                logger.info(f"Parsing hero cards at position {i}")
                hole_cards = self._parse_player_cards(img, player_region)
            
            player = PlayerState(
                name=name,
                stack=stack,
                position=player_region.get('position', i),
                bet_this_round=0.0,
                folded=False,
                all_in=False,
                hole_cards=hole_cards
            )
            players.append(player)
        
        return players
    
    def _parse_player_cards(self, img: np.ndarray, player_region: dict) -> Optional[List[Card]]:
        """Parse hole cards for a specific player."""
        card_reg = player_region.get('card_region', {})
        x, y, w, h = card_reg.get('x', 0), card_reg.get('y', 0), \
                    card_reg.get('width', 0), card_reg.get('height', 0)
        
        player_pos = player_region.get('position', 'unknown')
        logger.debug(f"Extracting player cards for position {player_pos} from region ({x},{y},{w},{h})")
        
        if y + h <= img.shape[0] and x + w <= img.shape[1] and w > 0 and h > 0:
            card_region = img[y:y+h, x:x+w]
            
            # Save debug image if debug mode is enabled
            if self.debug_dir:
                debug_path = self.debug_dir / f"player_{player_pos}_cards_{self._debug_counter:04d}.png"
                try:
                    success = cv2.imwrite(str(debug_path), card_region)
                    if success:
                        logger.debug(f"Saved player {player_pos} card region to {debug_path}")
                    else:
                        logger.warning(f"Failed to save player {player_pos} debug image to {debug_path}")
                except Exception as e:
                    logger.warning(f"Error saving player {player_pos} debug image: {e}")
            
            # Hole cards are 2 cards - use hero templates
            cards = self.card_recognizer.recognize_cards(card_region, num_cards=2, use_hero_templates=True)
            
            # Filter out None values
            valid_cards = [c for c in cards if c is not None]
            
            # Log the result
            if len(valid_cards) > 0:
                cards_str = ", ".join(str(c) for c in valid_cards)
                logger.info(f"Recognized {len(valid_cards)} card(s) for player {player_pos}: {cards_str}")
                return valid_cards
            else:
                logger.warning(f"No cards recognized for player {player_pos} - check card templates and region coordinates")
        else:
            logger.error(f"Player {player_pos} card region ({x},{y},{w},{h}) out of bounds for image shape {img.shape}")
        
        return None
