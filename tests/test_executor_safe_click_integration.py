"""Integration tests for ActionExecutor with safe click functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from holdem.types import ControlConfig, Action, ActionType, TableState, Street
from holdem.control.executor import ActionExecutor
from holdem.vision.calibrate import TableProfile


def create_light_button_image(width=60, height=30):
    """Create a mock image of a light-colored action button."""
    return np.ones((height, width, 3), dtype=np.uint8) * 180


def create_checkbox_image(width=60, height=30):
    """Create a mock image with checkbox UI elements."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 50
    checkbox_x = int(width * 0.25)
    checkbox_y = height // 2
    checkbox_size = 5
    for i in range(-checkbox_size, checkbox_size):
        for j in range(-checkbox_size, checkbox_size):
            x = checkbox_x + i
            y = checkbox_y + j
            if 0 <= x < width and 0 <= y < height:
                img[y, x] = [30, 30, 30]
    return img


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
        'half_pot_button_region': {'x': 250, 'y': 260, 'width': 60, 'height': 30},
        'pot_button_region': {'x': 320, 'y': 260, 'width': 60, 'height': 30},
        'bet_confirm_button_region': {'x': 328, 'y': 327, 'width': 100, 'height': 40}
    }
    return profile


@pytest.fixture
def safe_click_config():
    """Create config with safe click enabled."""
    return ControlConfig(
        dry_run=False,
        confirm_every_action=False,
        min_action_delay_ms=100,
        i_understand_the_tos=True,
        safe_click_enabled=True
    )


@pytest.fixture
def legacy_config():
    """Create config with safe click disabled."""
    return ControlConfig(
        dry_run=False,
        confirm_every_action=False,
        min_action_delay_ms=100,
        i_understand_the_tos=True,
        safe_click_enabled=False
    )


class TestExecutorSafeClickIntegration:
    """Integration tests for safe click in ActionExecutor."""
    
    def test_executor_initializes_with_safe_click_enabled(self, mock_profile, safe_click_config):
        """Test that executor initializes with safe click enabled by default."""
        executor = ActionExecutor(safe_click_config, mock_profile)
        assert executor.safe_click_enabled is True
    
    def test_executor_initializes_with_safe_click_disabled(self, mock_profile, legacy_config):
        """Test that executor can be initialized with safe click disabled."""
        executor = ActionExecutor(legacy_config, mock_profile)
        assert executor.safe_click_enabled is False
    
    def test_fold_action_with_safe_click_enabled(self, mock_profile, safe_click_config):
        """Test folding with safe click enabled and button visible."""
        executor = ActionExecutor(safe_click_config, mock_profile)
        
        with patch('holdem.control.safe_click.ScreenCapture') as mock_capture:
            mock_instance = mock_capture.return_value
            mock_instance.capture_region.return_value = create_light_button_image()
            
            with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
                mock_pyautogui = Mock()
                mock_get_pyautogui.return_value = mock_pyautogui
                
                action = Action(action_type=ActionType.FOLD)
                button_region = mock_profile.button_regions['fold']
                
                result = executor._click_button(button_region, action)
                assert result is True
    
    def test_fold_action_with_checkbox_visible(self, mock_profile, safe_click_config):
        """Test that folding is prevented when checkbox is visible."""
        executor = ActionExecutor(safe_click_config, mock_profile)
        
        with patch('holdem.control.safe_click.ScreenCapture') as mock_capture:
            mock_instance = mock_capture.return_value
            mock_instance.capture_region.return_value = create_checkbox_image()
            
            with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
                mock_pyautogui = Mock()
                mock_get_pyautogui.return_value = mock_pyautogui
                
                action = Action(action_type=ActionType.FOLD)
                button_region = mock_profile.button_regions['fold']
                
                result = executor._click_button(button_region, action)
                assert result is False
                mock_pyautogui.click.assert_not_called()
    
    def test_call_action_with_safe_click_enabled(self, mock_profile, safe_click_config):
        """Test calling with safe click enabled and button visible."""
        executor = ActionExecutor(safe_click_config, mock_profile)
        
        with patch('holdem.control.safe_click.ScreenCapture') as mock_capture:
            mock_instance = mock_capture.return_value
            mock_instance.capture_region.return_value = create_light_button_image()
            
            with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
                mock_pyautogui = Mock()
                mock_get_pyautogui.return_value = mock_pyautogui
                
                action = Action(action_type=ActionType.CALL, amount=100.0)
                button_region = mock_profile.button_regions['call']
                
                result = executor._click_button(button_region, action)
                assert result is True
    
    def test_call_action_with_checkbox_prevents_click(self, mock_profile, safe_click_config):
        """Test that calling is prevented when checkbox UI is detected."""
        executor = ActionExecutor(safe_click_config, mock_profile)
        
        with patch('holdem.control.safe_click.ScreenCapture') as mock_capture:
            mock_instance = mock_capture.return_value
            mock_instance.capture_region.return_value = create_checkbox_image()
            
            with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
                mock_pyautogui = Mock()
                mock_get_pyautogui.return_value = mock_pyautogui
                
                action = Action(action_type=ActionType.CALL, amount=100.0)
                button_region = mock_profile.button_regions['call']
                
                result = executor._click_button(button_region, action)
                assert result is False
                mock_pyautogui.click.assert_not_called()
    
    def test_legacy_mode_clicks_without_verification(self, mock_profile, legacy_config):
        """Test that legacy mode (safe click disabled) clicks without verification."""
        executor = ActionExecutor(legacy_config, mock_profile)
        
        # No need to mock screen capture since it won't be used
        with patch('holdem.control.executor._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            with patch('holdem.control.executor.time.sleep'):
                action = Action(action_type=ActionType.FOLD)
                button_region = mock_profile.button_regions['fold']
                
                result = executor._click_button(button_region, action)
                assert result is True
                mock_pyautogui.click.assert_called_once()
    
    def test_quick_bet_half_pot_with_safe_click(self, mock_profile, safe_click_config):
        """Test BET_HALF_POT with safe click enabled."""
        executor = ActionExecutor(safe_click_config, mock_profile)
        
        with patch('holdem.control.safe_click.ScreenCapture') as mock_capture:
            mock_instance = mock_capture.return_value
            mock_instance.capture_region.return_value = create_light_button_image()
            
            with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
                mock_pyautogui = Mock()
                mock_get_pyautogui.return_value = mock_pyautogui
                
                action = Action(action_type=ActionType.BET_HALF_POT)
                state = Mock(spec=TableState)
                
                result = executor._execute_quick_bet(action, state)
                assert result is True
    
    def test_quick_bet_pot_with_safe_click(self, mock_profile, safe_click_config):
        """Test BET_POT with safe click enabled."""
        executor = ActionExecutor(safe_click_config, mock_profile)
        
        with patch('holdem.control.safe_click.ScreenCapture') as mock_capture:
            mock_instance = mock_capture.return_value
            mock_instance.capture_region.return_value = create_light_button_image()
            
            with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
                mock_pyautogui = Mock()
                mock_get_pyautogui.return_value = mock_pyautogui
                
                action = Action(action_type=ActionType.BET_POT)
                state = Mock(spec=TableState)
                
                result = executor._execute_quick_bet(action, state)
                assert result is True
    
    def test_quick_bet_rejected_when_checkbox_visible(self, mock_profile, safe_click_config):
        """Test that quick bet is rejected when checkbox is visible."""
        executor = ActionExecutor(safe_click_config, mock_profile)
        
        with patch('holdem.control.safe_click.ScreenCapture') as mock_capture:
            mock_instance = mock_capture.return_value
            mock_instance.capture_region.return_value = create_checkbox_image()
            
            with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
                mock_pyautogui = Mock()
                mock_get_pyautogui.return_value = mock_pyautogui
                
                action = Action(action_type=ActionType.BET_HALF_POT)
                state = Mock(spec=TableState)
                
                result = executor._execute_quick_bet(action, state)
                assert result is False
                mock_pyautogui.click.assert_not_called()
    
    def test_multiple_actions_with_mixed_results(self, mock_profile, safe_click_config):
        """Test multiple actions where some succeed and some fail."""
        executor = ActionExecutor(safe_click_config, mock_profile)
        
        with patch('holdem.control.safe_click.ScreenCapture') as mock_capture:
            mock_instance = mock_capture.return_value
            
            with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
                mock_pyautogui = Mock()
                mock_get_pyautogui.return_value = mock_pyautogui
                
                # First action: checkbox visible (should fail)
                mock_instance.capture_region.return_value = create_checkbox_image()
                action1 = Action(action_type=ActionType.CALL, amount=100.0)
                button_region1 = mock_profile.button_regions['call']
                result1 = executor._click_button(button_region1, action1)
                assert result1 is False
                
                # Second action: button visible (should succeed)
                mock_instance.capture_region.return_value = create_light_button_image()
                action2 = Action(action_type=ActionType.CALL, amount=100.0)
                button_region2 = mock_profile.button_regions['call']
                result2 = executor._click_button(button_region2, action2)
                assert result2 is True
                
                # Should have clicked only once
                assert mock_pyautogui.click.call_count == 1


class TestExecutorDefaultBehavior:
    """Test executor default behavior with safe click."""
    
    def test_default_config_has_safe_click_enabled(self, mock_profile):
        """Test that default config has safe click enabled."""
        config = ControlConfig(
            dry_run=False,
            confirm_every_action=False,
            min_action_delay_ms=100,
            i_understand_the_tos=True
            # safe_click_enabled not explicitly set
        )
        
        executor = ActionExecutor(config, mock_profile)
        # Should use getattr default of True
        assert executor.safe_click_enabled is True
    
    def test_config_without_safe_click_field_defaults_to_true(self, mock_profile):
        """Test backward compatibility when safe_click_enabled is not in config."""
        config = ControlConfig(
            dry_run=False,
            confirm_every_action=False,
            min_action_delay_ms=100,
            i_understand_the_tos=True
        )
        # Remove safe_click_enabled attribute if it exists
        if hasattr(config, 'safe_click_enabled'):
            delattr(config, 'safe_click_enabled')
        
        executor = ActionExecutor(config, mock_profile)
        # Should default to True via getattr
        assert executor.safe_click_enabled is True
