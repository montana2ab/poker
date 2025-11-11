"""Action executor with safety features and action backmapping."""

import time
import pyautogui
from typing import Optional
from holdem.types import ControlConfig, Action, ActionType, Street, TableState
from holdem.vision.calibrate import TableProfile
from holdem.abstraction.actions import AbstractAction
from holdem.abstraction.backmapping import ActionBackmapper
from holdem.control.actions import ClickAction, WaitAction
from holdem.utils.logging import get_logger

logger = get_logger("control.executor")


class ActionExecutor:
    """Executes actions on the poker table with comprehensive backmapping support."""
    
    def __init__(self, config: ControlConfig, profile: TableProfile):
        self.config = config
        self.profile = profile
        self.paused = False
        self.stopped = False
        
        # Initialize backmapper for action validation and adjustment
        self.backmapper = ActionBackmapper(
            big_blind=config.big_blind if hasattr(config, 'big_blind') else 2.0,
            min_chip_increment=config.min_chip if hasattr(config, 'min_chip') else 1.0,
            allow_fractional=config.allow_fractional if hasattr(config, 'allow_fractional') else False
        )
        
        # Configure pyautogui
        pyautogui.PAUSE = config.min_action_delay_ms / 1000.0
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    
    def execute(self, action: AbstractAction, state: Optional[TableState] = None) -> bool:
        """Execute an action with state-aware backmapping.
        
        Args:
            action: Abstract action to execute
            state: Optional table state for context-aware backmapping
            
        Returns:
            True if action executed successfully, False otherwise
        """
        if state:
            # Use backmapper to convert abstract to concrete action with validation
            concrete_action = self._backmap_with_state(action, state)
            if not concrete_action:
                logger.error(f"Failed to backmap action {action.value}")
                return False
            
            # Validate the concrete action
            valid, error = self._validate_concrete_action(concrete_action, state)
            if not valid:
                logger.error(f"Invalid action after backmapping: {error}")
                return False
            
            logger.info(f"Backmapped {action.value} to {concrete_action}")
            return self._execute_concrete_action(concrete_action, state)
        else:
            # Fallback to simple abstract action execution (backward compatibility)
            return self.execute_action(action)
    
    def _backmap_with_state(self, action: AbstractAction, state: TableState) -> Optional[Action]:
        """Convert abstract action to concrete action using state information.
        
        Args:
            action: Abstract action
            state: Current table state
            
        Returns:
            Concrete Action or None if backmapping fails
        """
        try:
            # Get hero (current player) information
            if state.hero_position is None:
                logger.error("Hero position not set in state")
                return None
            
            hero = state.players[state.hero_position]
            
            # Calculate action parameters
            pot = state.pot
            stack = hero.stack
            current_bet = state.current_bet
            player_bet = hero.bet_this_round
            can_check = (current_bet == player_bet)
            
            # Backmap the action
            concrete = self.backmapper.backmap_action(
                abstract_action=action,
                pot=pot,
                stack=stack,
                current_bet=current_bet,
                player_bet=player_bet,
                can_check=can_check,
                last_raise_amount=None,  # Could track this in state
                street=state.street
            )
            
            return concrete
            
        except Exception as e:
            logger.error(f"Error during backmapping: {e}", exc_info=True)
            return None
    
    def _validate_concrete_action(
        self, 
        action: Action, 
        state: TableState
    ) -> tuple[bool, Optional[str]]:
        """Validate a concrete action against current state.
        
        Args:
            action: Concrete action to validate
            state: Current table state
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if state.hero_position is None:
            return False, "Hero position not set"
        
        hero = state.players[state.hero_position]
        
        return self.backmapper.validate_action(
            action=action,
            pot=state.pot,
            stack=hero.stack,
            current_bet=state.current_bet,
            player_bet=hero.bet_this_round,
            can_check=(state.current_bet == hero.bet_this_round),
            last_raise_amount=None
        )
    
    def _execute_concrete_action(
        self, 
        action: Action, 
        state: TableState
    ) -> bool:
        """Execute a concrete action on the poker client.
        
        This handles the actual interaction with the poker client UI,
        including bet sizing via sliders or input fields.
        
        Args:
            action: Concrete action to execute
            state: Current table state
            
        Returns:
            True if successful, False otherwise
        """
        if self.stopped:
            logger.warning("Executor stopped, not executing action")
            return False
        
        if self.paused:
            logger.info("Executor paused, waiting...")
            while self.paused and not self.stopped:
                time.sleep(0.1)
        
        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would execute: {action}")
            return True
        
        if not self.config.i_understand_the_tos:
            logger.error("Auto-play requires --i-understand-the-tos flag")
            return False
        
        # Get button region for action
        button_region = self._get_button_region_for_concrete(action)
        if not button_region:
            logger.error(f"No button region found for action: {action.action_type.value}")
            return False
        
        # Confirm if needed
        if self.config.confirm_every_action:
            response = input(f"Execute {action}? (y/n): ")
            if response.lower() != 'y':
                logger.info("Action cancelled by user")
                return False
        
        # Execute based on action type
        try:
            if action.action_type in [ActionType.FOLD, ActionType.CHECK, ActionType.CALL, ActionType.ALLIN]:
                # Simple click actions
                return self._click_button(button_region, action)
            
            elif action.action_type in [ActionType.BET, ActionType.RAISE]:
                # Bet/raise require amount input
                return self._execute_bet_or_raise(button_region, action, state)
            
            else:
                logger.error(f"Unknown action type: {action.action_type}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to execute action: {e}", exc_info=True)
            return False
    
    def _get_button_region_for_concrete(self, action: Action) -> Optional[dict]:
        """Get button region for a concrete action.
        
        Args:
            action: Concrete action
            
        Returns:
            Button region dict or None
        """
        action_to_button = {
            ActionType.FOLD: "fold",
            ActionType.CHECK: "check",
            ActionType.CALL: "call",
            ActionType.BET: "bet",
            ActionType.RAISE: "raise",
            ActionType.ALLIN: "allin"
        }
        
        button_name = action_to_button.get(action.action_type)
        if not button_name:
            return None
        
        return self.profile.button_regions.get(button_name)
    
    def _click_button(self, button_region: dict, action: Action) -> bool:
        """Click a button region.
        
        Args:
            button_region: Region dict with x, y, width, height
            action: Action being executed (for logging)
            
        Returns:
            True if successful
        """
        x = button_region['x'] + button_region['width'] // 2
        y = button_region['y'] + button_region['height'] // 2
        
        logger.info(f"Executing {action.action_type.value} at ({x}, {y})")
        
        pyautogui.click(x, y)
        time.sleep(self.config.min_action_delay_ms / 1000.0)
        return True
    
    def _execute_bet_or_raise(
        self, 
        button_region: dict, 
        action: Action, 
        state: TableState
    ) -> bool:
        """Execute a bet or raise with precise amount.
        
        This is a placeholder implementation. Different poker clients handle
        bet sizing differently (sliders, input fields, preset buttons).
        Customize this method for your specific poker client.
        
        Args:
            button_region: Button region for bet/raise
            action: Bet or raise action with amount
            state: Current table state
            
        Returns:
            True if successful
        """
        # TODO: Implement client-specific bet sizing
        # Options:
        # 1. Use bet slider (requires slider detection and positioning)
        # 2. Use input field (requires field detection and typing)
        # 3. Use preset bet buttons (25%, 50%, 75%, pot, etc.)
        
        logger.info(f"Executing {action.action_type.value} of {action.amount}")
        
        # For now, just click the button (assumes client has reasonable defaults)
        # In production, this should be enhanced with amount-specific logic
        x = button_region['x'] + button_region['width'] // 2
        y = button_region['y'] + button_region['height'] // 2
        
        pyautogui.click(x, y)
        time.sleep(self.config.min_action_delay_ms / 1000.0)
        
        logger.warning(
            "Bet/raise executed without precise amount control. "
            "Implement client-specific bet sizing for production use."
        )
        
        return True
    
    def execute_action(self, action: AbstractAction) -> bool:
        """Execute an abstract action."""
        if self.stopped:
            logger.warning("Executor stopped, not executing action")
            return False
        
        if self.paused:
            logger.info("Executor paused, waiting...")
            while self.paused and not self.stopped:
                time.sleep(0.1)
        
        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would execute: {action.value}")
            return True
        
        if not self.config.i_understand_the_tos:
            logger.error("Auto-play requires --i-understand-the-tos flag")
            return False
        
        # Get button region for action
        button_region = self._get_button_region(action)
        if not button_region:
            logger.error(f"No button region found for action: {action.value}")
            return False
        
        # Confirm if needed
        if self.config.confirm_every_action:
            response = input(f"Execute {action.value}? (y/n): ")
            if response.lower() != 'y':
                logger.info("Action cancelled by user")
                return False
        
        # Click the button
        x = button_region['x'] + button_region['width'] // 2
        y = button_region['y'] + button_region['height'] // 2
        
        logger.info(f"Executing action: {action.value} at ({x}, {y})")
        
        try:
            pyautogui.click(x, y)
            time.sleep(self.config.min_action_delay_ms / 1000.0)
            return True
        except Exception as e:
            logger.error(f"Failed to execute action: {e}")
            return False
    
    def _get_button_region(self, action: AbstractAction) -> Optional[dict]:
        """Get button region for action."""
        action_to_button = {
            AbstractAction.FOLD: "fold",
            AbstractAction.CHECK_CALL: "check",  # Or "call"
            AbstractAction.BET_QUARTER_POT: "bet",
            AbstractAction.BET_THIRD_POT: "bet",
            AbstractAction.BET_HALF_POT: "bet",
            AbstractAction.BET_TWO_THIRDS_POT: "bet",
            AbstractAction.BET_THREE_QUARTERS_POT: "bet",
            AbstractAction.BET_POT: "bet",
            AbstractAction.BET_OVERBET_150: "raise",
            AbstractAction.BET_DOUBLE_POT: "raise",
            AbstractAction.ALL_IN: "allin",
        }
        
        button_name = action_to_button.get(action)
        if not button_name:
            return None
        
        return self.profile.button_regions.get(button_name)
    
    def pause(self):
        """Pause execution."""
        self.paused = True
        logger.info("Executor paused")
    
    def resume(self):
        """Resume execution."""
        self.paused = False
        logger.info("Executor resumed")
    
    def stop(self):
        """Stop execution permanently."""
        self.stopped = True
        logger.info("Executor stopped")
