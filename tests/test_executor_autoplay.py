"""Test auto-play mode for ActionExecutor."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from holdem.types import ControlConfig, Action, ActionType, TableState, Street
from holdem.control.executor import ActionExecutor
from holdem.vision.calibrate import TableProfile
from holdem.abstraction.actions import AbstractAction


@pytest.fixture
def mock_profile():
    """Create a mock table profile with button regions."""
    profile = Mock(spec=TableProfile)
    profile.button_regions = {
        'fold': {'x': 100, 'y': 300, 'width': 80, 'height': 40},
        'check': {'x': 200, 'y': 300, 'width': 80, 'height': 40},
        'call': {'x': 200, 'y': 300, 'width': 80, 'height': 40},
        'bet': {'x': 300, 'y': 300, 'width': 80, 'height': 40},
        'raise': {'x': 300, 'y': 300, 'width': 80, 'height': 40},
        'allin': {'x': 400, 'y': 300, 'width': 80, 'height': 40},
        'bet_input_box': {'x': 350, 'y': 250, 'width': 100, 'height': 30},
    }
    return profile


@pytest.fixture
def autoplay_config():
    """Create config for auto-play mode (no confirmation)."""
    return ControlConfig(
        dry_run=False,
        confirm_every_action=False,  # Auto-play mode
        min_action_delay_ms=100,
        i_understand_the_tos=True
    )


@pytest.fixture
def manual_config():
    """Create config for manual mode (with confirmation)."""
    return ControlConfig(
        dry_run=False,
        confirm_every_action=True,  # Manual mode
        min_action_delay_ms=100,
        i_understand_the_tos=True
    )


@pytest.fixture
def mock_state():
    """Create a mock table state."""
    state = Mock(spec=TableState)
    state.pot = 100.0
    state.current_bet = 20.0
    state.street = Street.FLOP
    state.hero_position = 0
    
    hero = Mock()
    hero.stack = 500.0
    hero.bet_this_round = 0.0
    
    state.players = [hero]
    return state


class TestAutoPlayMode:
    """Test auto-play mode functionality."""
    
    @patch('holdem.control.executor.pyautogui')
    def test_autoplay_no_confirmation_simple_action(self, mock_pyautogui, mock_profile, autoplay_config, mock_state):
        """Test that auto-play mode doesn't ask for confirmation on simple actions."""
        executor = ActionExecutor(autoplay_config, mock_profile)
        
        # Create a concrete action
        action = Action(action_type=ActionType.CHECK)
        
        # Execute should not call input() and should succeed
        result = executor._execute_concrete_action(action, mock_state)
        
        assert result is True
        # Verify pyautogui.click was called
        mock_pyautogui.click.assert_called_once()
        # Verify it clicked the check button region
        call_args = mock_pyautogui.click.call_args[0]
        assert call_args[0] == 240  # x = 200 + 80/2
        assert call_args[1] == 320  # y = 300 + 40/2
    
    @patch('holdem.control.executor.pyautogui')
    def test_autoplay_fold_action(self, mock_pyautogui, mock_profile, autoplay_config, mock_state):
        """Test fold action in auto-play mode."""
        executor = ActionExecutor(autoplay_config, mock_profile)
        action = Action(action_type=ActionType.FOLD)
        
        result = executor._execute_concrete_action(action, mock_state)
        
        assert result is True
        mock_pyautogui.click.assert_called_once()
        call_args = mock_pyautogui.click.call_args[0]
        assert call_args[0] == 140  # x = 100 + 80/2
        assert call_args[1] == 320  # y = 300 + 40/2
    
    @patch('holdem.control.executor.pyautogui')
    def test_autoplay_call_action(self, mock_pyautogui, mock_profile, autoplay_config, mock_state):
        """Test call action in auto-play mode."""
        executor = ActionExecutor(autoplay_config, mock_profile)
        action = Action(action_type=ActionType.CALL, amount=20.0)
        
        result = executor._execute_concrete_action(action, mock_state)
        
        assert result is True
        mock_pyautogui.click.assert_called_once()
    
    @patch('holdem.control.executor.pyautogui')
    @patch('holdem.control.executor.time.sleep')
    def test_autoplay_bet_with_input_box(self, mock_sleep, mock_pyautogui, mock_profile, autoplay_config, mock_state):
        """Test bet action uses input box when available."""
        executor = ActionExecutor(autoplay_config, mock_profile)
        action = Action(action_type=ActionType.BET, amount=50.0)
        
        result = executor._execute_concrete_action(action, mock_state)
        
        assert result is True
        # Should click input box, then the bet button
        assert mock_pyautogui.click.call_count == 2
        # Should call hotkey to select all
        mock_pyautogui.hotkey.assert_called_with('ctrl', 'a')
        # Should type the amount
        mock_pyautogui.typewrite.assert_called_once_with('50', interval=0.05)
    
    @patch('holdem.control.executor.pyautogui')
    def test_autoplay_bet_without_input_box(self, mock_pyautogui, autoplay_config, mock_state):
        """Test bet action without input box falls back to default."""
        # Profile without bet_input_box
        profile = Mock(spec=TableProfile)
        profile.button_regions = {
            'bet': {'x': 300, 'y': 300, 'width': 80, 'height': 40},
        }
        
        executor = ActionExecutor(autoplay_config, profile)
        action = Action(action_type=ActionType.BET, amount=50.0)
        
        result = executor._execute_concrete_action(action, mock_state)
        
        assert result is True
        # Should click bet button once (no input box)
        mock_pyautogui.click.assert_called_once()
        # Should not try to type
        mock_pyautogui.typewrite.assert_not_called()
    
    @patch('holdem.control.executor.input')
    @patch('holdem.control.executor.pyautogui')
    def test_manual_mode_requires_confirmation(self, mock_pyautogui, mock_input, mock_profile, manual_config, mock_state):
        """Test manual mode asks for confirmation."""
        mock_input.return_value = 'y'
        
        executor = ActionExecutor(manual_config, mock_profile)
        action = Action(action_type=ActionType.CHECK)
        
        result = executor._execute_concrete_action(action, mock_state)
        
        assert result is True
        # Should have asked for input
        mock_input.assert_called_once()
        # Should have clicked after confirmation
        mock_pyautogui.click.assert_called_once()
    
    @patch('holdem.control.executor.input')
    @patch('holdem.control.executor.pyautogui')
    def test_manual_mode_can_cancel(self, mock_pyautogui, mock_input, mock_profile, manual_config, mock_state):
        """Test manual mode can cancel action."""
        mock_input.return_value = 'n'
        
        executor = ActionExecutor(manual_config, mock_profile)
        action = Action(action_type=ActionType.CHECK)
        
        result = executor._execute_concrete_action(action, mock_state)
        
        assert result is False
        # Should have asked for input
        mock_input.assert_called_once()
        # Should NOT have clicked after cancellation
        mock_pyautogui.click.assert_not_called()
    
    @patch('holdem.control.executor.pyautogui')
    def test_abstract_action_execution_autoplay(self, mock_pyautogui, mock_profile, autoplay_config):
        """Test abstract action execution in auto-play mode."""
        executor = ActionExecutor(autoplay_config, mock_profile)
        action = AbstractAction.CHECK_CALL
        
        result = executor.execute_action(action)
        
        assert result is True
        mock_pyautogui.click.assert_called_once()
    
    def test_dry_run_mode_no_clicks(self, mock_profile):
        """Test dry-run mode doesn't execute clicks."""
        config = ControlConfig(
            dry_run=True,
            confirm_every_action=False,
            i_understand_the_tos=True
        )
        executor = ActionExecutor(config, mock_profile)
        action = AbstractAction.CHECK_CALL
        
        with patch('holdem.control.executor.pyautogui') as mock_pyautogui:
            result = executor.execute_action(action)
            
            assert result is True
            # Should not click in dry-run mode
            mock_pyautogui.click.assert_not_called()


class TestExecutorSafety:
    """Test safety features of executor."""
    
    def test_requires_tos_agreement(self, mock_profile, mock_state):
        """Test executor requires TOS agreement."""
        config = ControlConfig(
            dry_run=False,
            confirm_every_action=False,
            i_understand_the_tos=False  # Not agreed
        )
        executor = ActionExecutor(config, mock_profile)
        action = Action(action_type=ActionType.CHECK)
        
        result = executor._execute_concrete_action(action, mock_state)
        
        assert result is False
    
    @patch('holdem.control.executor.pyautogui')
    def test_stopped_executor_no_action(self, mock_pyautogui, mock_profile, autoplay_config, mock_state):
        """Test stopped executor doesn't execute actions."""
        executor = ActionExecutor(autoplay_config, mock_profile)
        executor.stop()
        
        action = Action(action_type=ActionType.CHECK)
        result = executor._execute_concrete_action(action, mock_state)
        
        assert result is False
        mock_pyautogui.click.assert_not_called()
    
    @patch('holdem.control.executor.pyautogui')
    def test_missing_button_region(self, mock_pyautogui, autoplay_config, mock_state):
        """Test handling of missing button region."""
        # Profile without the required button
        profile = Mock(spec=TableProfile)
        profile.button_regions = {}
        
        executor = ActionExecutor(autoplay_config, profile)
        action = Action(action_type=ActionType.CHECK)
        
        result = executor._execute_concrete_action(action, mock_state)
        
        assert result is False
        mock_pyautogui.click.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
