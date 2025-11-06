"""Action executor with safety features."""

import time
import pyautogui
from typing import Optional
from holdem.types import ControlConfig
from holdem.vision.calibrate import TableProfile
from holdem.abstraction.actions import AbstractAction
from holdem.control.actions import ClickAction, WaitAction
from holdem.utils.logging import get_logger

logger = get_logger("control.executor")


class ActionExecutor:
    """Executes actions on the poker table."""
    
    def __init__(self, config: ControlConfig, profile: TableProfile):
        self.config = config
        self.profile = profile
        self.paused = False
        self.stopped = False
        
        # Configure pyautogui
        pyautogui.PAUSE = config.min_action_delay_ms / 1000.0
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    
    def execute(self, action: AbstractAction, state) -> bool:
        """Execute an action (convenience method)."""
        return self.execute_action(action)
    
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
            AbstractAction.BET_ONE_HALF_POT: "raise",
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
