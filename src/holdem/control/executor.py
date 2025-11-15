"""Action executor with safety features and action backmapping."""

import time
import platform
from typing import Optional
from holdem.types import ControlConfig, Action, ActionType, Street, TableState
from holdem.vision.calibrate import TableProfile
from holdem.abstraction.actions import AbstractAction
from holdem.abstraction.backmapping import ActionBackmapper
from holdem.control.actions import ClickAction, WaitAction
from holdem.control.safe_click import safe_click_action_button
from holdem.utils.logging import get_logger

logger = get_logger("control.executor")


def _get_pyautogui():
    """Lazy import of pyautogui to avoid import issues in tests."""
    import pyautogui
    return pyautogui


def _is_apple_silicon() -> bool:
    """Detect M1/M2/M3 processors."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _is_macos() -> bool:
    """Detect macOS (Intel or Apple Silicon)."""
    return platform.system() == "Darwin"


def _configure_pyautogui_once(executor):
    """Configure pyautogui settings once, on first use."""
    if not executor._pyautogui_configured:
        pyautogui = _get_pyautogui()
        pyautogui.PAUSE = executor._pyautogui_pause
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort
        executor._pyautogui_configured = True


class ActionExecutor:
    """Executes actions on the poker table with comprehensive backmapping support."""
    
    def __init__(self, config: ControlConfig, profile: TableProfile):
        self.config = config
        self.profile = profile
        self.paused = False
        self.stopped = False
        
        # Safe click configuration (enabled by default)
        # Can be disabled via config for testing or debugging
        self.safe_click_enabled = getattr(config, 'safe_click_enabled', True)
        if self.safe_click_enabled:
            logger.info("Safe click enabled for action buttons")
        else:
            logger.warning("Safe click disabled - action buttons will be clicked without verification")
        
        # Initialize backmapper for action validation and adjustment
        # Enable quick bet buttons if the button regions are configured in the profile
        has_quick_bet_buttons = (
            'half_pot_button_region' in profile.button_regions and
            'pot_button_region' in profile.button_regions and
            'bet_confirm_button_region' in profile.button_regions
        )
        
        self.backmapper = ActionBackmapper(
            big_blind=config.big_blind if hasattr(config, 'big_blind') else 2.0,
            min_chip_increment=config.min_chip if hasattr(config, 'min_chip') else 1.0,
            allow_fractional=config.allow_fractional if hasattr(config, 'allow_fractional') else False,
            use_quick_bet_buttons=has_quick_bet_buttons
        )
        
        if has_quick_bet_buttons:
            logger.info("Quick bet buttons enabled (BET_HALF_POT, BET_POT)")
        else:
            logger.debug("Quick bet buttons not configured, using standard bet sizing")
        
        # Detect platform for timing adjustments
        self.is_mac = _is_macos()
        self.is_apple_silicon = _is_apple_silicon()
        
        # Platform-specific timing adjustments
        # Mac M2 needs longer delays due to different scheduler behavior
        if self.is_apple_silicon:
            self.click_delay = 0.15  # 150ms for Apple Silicon
            self.input_delay = 0.15  # 150ms between actions
            self.type_interval = 0.08  # 80ms between keystrokes
            logger.info("Detected Apple Silicon (M1/M2/M3) - using optimized timing")
        elif self.is_mac:
            self.click_delay = 0.12  # 120ms for Intel Mac
            self.input_delay = 0.12
            self.type_interval = 0.06
            logger.info("Detected macOS (Intel) - using optimized timing")
        else:
            self.click_delay = 0.1  # 100ms for Linux/Windows
            self.input_delay = 0.1
            self.type_interval = 0.05
        
        # Configure pyautogui (lazy init - only when needed)
        self._pyautogui_configured = False
        self._pyautogui_pause = config.min_action_delay_ms / 1000.0
    
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
        
        # Get button region for action (not needed for quick bet actions)
        button_region = self._get_button_region_for_concrete(action)
        if not button_region and action.action_type not in [ActionType.BET_HALF_POT, ActionType.BET_POT]:
            logger.error(f"No button region found for action: {action.action_type.value}")
            return False
        
        # Confirm if needed
        if self.config.confirm_every_action:
            response = input(f"Execute {action}? (y/n): ")
            if response.lower() != 'y':
                logger.info("Action cancelled by user")
                return False
        else:
            # Auto-play mode: no confirmation needed
            logger.info(f"[AUTO-PLAY] Auto-confirming action: {action}")
        
        # Execute based on action type
        try:
            if action.action_type in [ActionType.FOLD, ActionType.CHECK, ActionType.CALL, ActionType.ALLIN]:
                # Simple click actions
                return self._click_button(button_region, action)
            
            elif action.action_type in [ActionType.BET, ActionType.RAISE]:
                # Bet/raise require amount input
                return self._execute_bet_or_raise(button_region, action, state)
            
            elif action.action_type in [ActionType.BET_HALF_POT, ActionType.BET_POT]:
                # Quick bet actions using predefined UI buttons
                return self._execute_quick_bet(action, state)
            
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
        # Quick bet actions don't use this method - they have special handling
        if action.action_type in [ActionType.BET_HALF_POT, ActionType.BET_POT]:
            return {}  # Return empty dict to indicate these are handled separately
        
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
        """Click a button region with safe click verification.
        
        Args:
            button_region: Region dict with x, y, width, height
            action: Action being executed (for logging)
            
        Returns:
            True if successful
        """
        x = button_region['x'] + button_region['width'] // 2
        y = button_region['y'] + button_region['height'] // 2
        width = button_region['width']
        height = button_region['height']
        
        # Use safe click if enabled
        if self.safe_click_enabled:
            logger.info(f"[AUTO-PLAY] Safe clicking {action.action_type.value} at screen position ({x}, {y})")
            
            success = safe_click_action_button(
                x=x,
                y=y,
                width=width,
                height=height,
                label=action.action_type.value,
                click_delay=self.click_delay
            )
            
            if not success:
                logger.info(f"[AUTOPLAY] Skip action click, UI not ready or checkbox detected (action={action.action_type.value})")
            
            return success
        else:
            # Legacy mode: direct click without verification
            logger.info(f"[AUTO-PLAY] Clicking {action.action_type.value} at screen position ({x}, {y})")
            _configure_pyautogui_once(self)
            pyautogui = _get_pyautogui()
            pyautogui.click(x, y)
            time.sleep(self.click_delay)
            return True
    
    def _execute_bet_or_raise(
        self, 
        button_region: dict, 
        action: Action, 
        state: TableState
    ) -> bool:
        """Execute a bet or raise with precise amount.
        
        Attempts to input the exact bet amount if a bet_input_box region
        is configured in the profile. Otherwise, clicks the bet/raise button
        with default amount.
        
        Args:
            button_region: Button region for bet/raise
            action: Bet or raise action with amount
            state: Current table state
            
        Returns:
            True if successful
        """
        logger.info(f"[AUTO-PLAY] Executing {action.action_type.value} of {action.amount}")
        
        # Check if profile has bet input box configured
        bet_input_box = self.profile.button_regions.get('bet_input_box')
        
        if bet_input_box and action.amount:
            # Use input box to enter precise amount
            try:
                _configure_pyautogui_once(self)
                pyautogui = _get_pyautogui()
                
                # Click in the bet input box
                input_x = bet_input_box['x'] + bet_input_box['width'] // 2
                input_y = bet_input_box['y'] + bet_input_box['height'] // 2
                
                logger.info(f"[AUTO-PLAY] Clicking bet input box at ({input_x}, {input_y})")
                pyautogui.click(input_x, input_y)
                time.sleep(self.input_delay)
                
                # Clear existing value - use Cmd on Mac, Ctrl on others
                if self.is_mac:
                    pyautogui.hotkey('command', 'a')
                    logger.debug("[AUTO-PLAY] Using Cmd+A to select all (macOS)")
                else:
                    pyautogui.hotkey('ctrl', 'a')
                    logger.debug("[AUTO-PLAY] Using Ctrl+A to select all")
                time.sleep(self.input_delay * 0.5)
                
                # Type the amount
                amount_str = str(int(action.amount)) if action.amount == int(action.amount) else f"{action.amount:.2f}"
                logger.info(f"[AUTO-PLAY] Typing bet amount: {amount_str}")
                pyautogui.typewrite(amount_str, interval=self.type_interval)
                time.sleep(self.input_delay)
                
                # Click the bet/raise button to confirm (with safe click)
                x = button_region['x'] + button_region['width'] // 2
                y = button_region['y'] + button_region['height'] // 2
                width = button_region['width']
                height = button_region['height']
                
                if self.safe_click_enabled:
                    logger.info(f"[AUTO-PLAY] Safe clicking {action.action_type.value} button at ({x}, {y})")
                    success = safe_click_action_button(
                        x=x,
                        y=y,
                        width=width,
                        height=height,
                        label=action.action_type.value,
                        click_delay=self.config.min_action_delay_ms / 1000.0
                    )
                    
                    if not success:
                        logger.info(f"[AUTOPLAY] Skip action click, UI not ready or checkbox detected (action={action.action_type.value})")
                        return False
                else:
                    logger.info(f"[AUTO-PLAY] Clicking {action.action_type.value} button at ({x}, {y})")
                    pyautogui.click(x, y)
                    time.sleep(self.config.min_action_delay_ms / 1000.0)
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to input bet amount: {e}, falling back to default bet")
                # Fall through to default behavior
        
        # Default: just click the button (uses client's default amount) with safe click
        x = button_region['x'] + button_region['width'] // 2
        y = button_region['y'] + button_region['height'] // 2
        width = button_region['width']
        height = button_region['height']
        
        if self.safe_click_enabled:
            logger.info(f"[AUTO-PLAY] Safe clicking {action.action_type.value} at screen position ({x}, {y})")
            success = safe_click_action_button(
                x=x,
                y=y,
                width=width,
                height=height,
                label=action.action_type.value,
                click_delay=self.config.min_action_delay_ms / 1000.0
            )
            
            if not success:
                logger.info(f"[AUTOPLAY] Skip action click, UI not ready or checkbox detected (action={action.action_type.value})")
                return False
        else:
            logger.info(f"[AUTO-PLAY] Clicking {action.action_type.value} at screen position ({x}, {y})")
            _configure_pyautogui_once(self)
            pyautogui = _get_pyautogui()
            pyautogui.click(x, y)
            time.sleep(self.config.min_action_delay_ms / 1000.0)
        
        if not bet_input_box:
            logger.warning(
                "Bet/raise executed without precise amount control. "
                "Add 'bet_input_box' region to profile for precise bet sizing."
            )
        
        return True
    
    def _execute_quick_bet(self, action: Action, state: TableState) -> bool:
        """Execute a quick bet action using predefined UI buttons.
        
        Quick bet actions use the poker client's preset sizing buttons (½ POT, POT)
        followed by the bet confirmation button. This provides a faster and more
        reliable way to bet specific sizes without using the slider or input box.
        
        Sequence:
        1. Click the sizing button (half_pot_button_region or pot_button_region)
        2. Click the bet confirmation button (bet_confirm_button_region)
        
        Args:
            action: Quick bet action (BET_HALF_POT or BET_POT)
            state: Current table state
            
        Returns:
            True if successful, False otherwise
        """
        # Determine which sizing button to click
        if action.action_type == ActionType.BET_HALF_POT:
            sizing_button_name = "half_pot_button_region"
            action_desc = "BET_HALF_POT"
        elif action.action_type == ActionType.BET_POT:
            sizing_button_name = "pot_button_region"
            action_desc = "BET_POT"
        else:
            logger.error(f"Invalid quick bet action type: {action.action_type}")
            return False
        
        # Get button regions from profile
        sizing_button = self.profile.button_regions.get(sizing_button_name)
        confirm_button = self.profile.button_regions.get("bet_confirm_button_region")
        
        # Validate button regions are configured
        if not sizing_button:
            logger.warning(
                f"[AUTOPLAY] {action_desc} requested but {sizing_button_name} is not configured. "
                f"Please add this region to your table profile. Falling back to NOOP."
            )
            return False
        
        if not confirm_button:
            logger.warning(
                "[AUTOPLAY] bet_confirm_button_region is not configured, cannot click Miser button. "
                "Please add this region to your table profile. Falling back to NOOP."
            )
            return False
        
        logger.info(f"[AUTOPLAY] Executing {action_desc} via {sizing_button_name} then bet_confirm_button_region")
        
        try:
            # Step 1: Click the sizing button (½ POT or POT) with safe click
            sizing_x = sizing_button['x'] + sizing_button['width'] // 2
            sizing_y = sizing_button['y'] + sizing_button['height'] // 2
            
            if self.safe_click_enabled:
                logger.info(f"[AUTOPLAY] Safe clicking {sizing_button_name} at ({sizing_x}, {sizing_y})")
                success = safe_click_action_button(
                    x=sizing_x,
                    y=sizing_y,
                    width=sizing_button['width'],
                    height=sizing_button['height'],
                    label=sizing_button_name,
                    click_delay=self.input_delay
                )
                
                if not success:
                    logger.info(f"[AUTOPLAY] Skip sizing button click, UI not ready (action={action_desc})")
                    return False
            else:
                logger.info(f"[AUTOPLAY] Clicking {sizing_button_name} at ({sizing_x}, {sizing_y})")
                _configure_pyautogui_once(self)
                pyautogui = _get_pyautogui()
                pyautogui.click(sizing_x, sizing_y)
                time.sleep(self.input_delay)
            
            # Step 2: Click the bet confirmation button with safe click
            confirm_x = confirm_button['x'] + confirm_button['width'] // 2
            confirm_y = confirm_button['y'] + confirm_button['height'] // 2
            
            if self.safe_click_enabled:
                logger.info(f"[AUTOPLAY] Safe clicking bet_confirm_button_region at ({confirm_x}, {confirm_y})")
                success = safe_click_action_button(
                    x=confirm_x,
                    y=confirm_y,
                    width=confirm_button['width'],
                    height=confirm_button['height'],
                    label="bet_confirm",
                    click_delay=self.config.min_action_delay_ms / 1000.0
                )
                
                if not success:
                    logger.info(f"[AUTOPLAY] Skip confirm button click, UI not ready (action={action_desc})")
                    return False
            else:
                logger.info(f"[AUTOPLAY] Clicking bet_confirm_button_region at ({confirm_x}, {confirm_y})")
                _configure_pyautogui_once(self)
                pyautogui = _get_pyautogui()
                pyautogui.click(confirm_x, confirm_y)
                time.sleep(self.config.min_action_delay_ms / 1000.0)
            
            logger.info(f"[AUTOPLAY] Successfully executed {action_desc}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute quick bet {action_desc}: {e}", exc_info=True)
            return False
    
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
        else:
            # Auto-play mode: no confirmation needed
            logger.info(f"[AUTO-PLAY] Auto-confirming action: {action.value}")
        
        # Click the button with safe click
        x = button_region['x'] + button_region['width'] // 2
        y = button_region['y'] + button_region['height'] // 2
        width = button_region['width']
        height = button_region['height']
        
        try:
            if self.safe_click_enabled:
                logger.info(f"[AUTO-PLAY] Safe clicking {action.value} at screen position ({x}, {y})")
                success = safe_click_action_button(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    label=action.value,
                    click_delay=self.click_delay
                )
                
                if not success:
                    logger.info(f"[AUTOPLAY] Skip action click, UI not ready or checkbox detected (action={action.value})")
                
                return success
            else:
                logger.info(f"[AUTO-PLAY] Clicking {action.value} at screen position ({x}, {y})")
                _configure_pyautogui_once(self)
                pyautogui = _get_pyautogui()
                pyautogui.click(x, y)
                time.sleep(self.click_delay)
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
