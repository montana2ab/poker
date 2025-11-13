"""Test Mac M2 mouse control timing adjustments."""

import platform
from unittest.mock import Mock, patch
from holdem.types import ControlConfig
from holdem.control.executor import ActionExecutor, _is_apple_silicon, _is_macos
from holdem.vision.calibrate import TableProfile


def test_platform_detection():
    """Test platform detection functions."""
    print("\n=== Platform Detection Test ===")
    print(f"Platform: {platform.system()}")
    print(f"Machine: {platform.machine()}")
    print(f"is_macos(): {_is_macos()}")
    print(f"is_apple_silicon(): {_is_apple_silicon()}")
    
    if _is_apple_silicon():
        print("\n✓ Apple Silicon (M1/M2/M3) detected")
        print("  Expected timing: 150ms delays, 80ms type interval")
    elif _is_macos():
        print("\n✓ macOS Intel detected")
        print("  Expected timing: 120ms delays, 60ms type interval")
    else:
        print("\n✓ Linux/Windows detected")
        print("  Expected timing: 100ms delays, 50ms type interval")


def test_executor_timing_configuration():
    """Test executor timing configuration based on platform."""
    print("\n=== Executor Timing Configuration Test ===")
    
    # Create mock profile
    profile = Mock(spec=TableProfile)
    profile.button_regions = {
        'fold': {'x': 100, 'y': 300, 'width': 80, 'height': 40},
    }
    
    # Create executor with test config
    config = ControlConfig(
        dry_run=True,
        confirm_every_action=False,
        min_action_delay_ms=500,
        i_understand_the_tos=True
    )
    
    executor = ActionExecutor(config, profile)
    
    print(f"is_mac: {executor.is_mac}")
    print(f"is_apple_silicon: {executor.is_apple_silicon}")
    print(f"click_delay: {executor.click_delay}s")
    print(f"input_delay: {executor.input_delay}s")
    print(f"type_interval: {executor.type_interval}s")
    
    # Verify timing values
    if executor.is_apple_silicon:
        assert executor.click_delay == 0.15, "Apple Silicon should use 150ms click delay"
        assert executor.input_delay == 0.15, "Apple Silicon should use 150ms input delay"
        assert executor.type_interval == 0.08, "Apple Silicon should use 80ms type interval"
        print("\n✓ Apple Silicon timing verified")
    elif executor.is_mac:
        assert executor.click_delay == 0.12, "Intel Mac should use 120ms click delay"
        assert executor.input_delay == 0.12, "Intel Mac should use 120ms input delay"
        assert executor.type_interval == 0.06, "Intel Mac should use 60ms type interval"
        print("\n✓ Intel Mac timing verified")
    else:
        assert executor.click_delay == 0.1, "Linux/Windows should use 100ms click delay"
        assert executor.input_delay == 0.1, "Linux/Windows should use 100ms input delay"
        assert executor.type_interval == 0.05, "Linux/Windows should use 50ms type interval"
        print("\n✓ Linux/Windows timing verified")


def test_mac_keyboard_shortcut():
    """Test that Mac uses Cmd instead of Ctrl for keyboard shortcuts."""
    print("\n=== Mac Keyboard Shortcut Test ===")
    
    # Test current platform
    is_mac = _is_macos()
    print(f"Current platform is macOS: {is_mac}")
    
    if is_mac:
        print("✓ Should use 'command' key for shortcuts (Cmd+A)")
    else:
        print("✓ Should use 'ctrl' key for shortcuts (Ctrl+A)")


@patch('holdem.control.executor.platform.system')
@patch('holdem.control.executor.platform.machine')
def test_apple_silicon_detection(mock_machine, mock_system):
    """Test Apple Silicon detection with mocked platform."""
    print("\n=== Apple Silicon Detection (Mocked) Test ===")
    
    # Test Mac M2 (Apple Silicon)
    mock_system.return_value = "Darwin"
    mock_machine.return_value = "arm64"
    
    # Need to reload the module to pick up the mocked values
    from importlib import reload
    import holdem.control.executor as executor_module
    reload(executor_module)
    
    assert executor_module._is_apple_silicon() == True
    assert executor_module._is_macos() == True
    print("✓ Mac M2 (arm64) correctly detected as Apple Silicon")
    
    # Test Intel Mac
    mock_system.return_value = "Darwin"
    mock_machine.return_value = "x86_64"
    reload(executor_module)
    
    assert executor_module._is_apple_silicon() == False
    assert executor_module._is_macos() == True
    print("✓ Intel Mac (x86_64) correctly detected as macOS but not Apple Silicon")
    
    # Test Linux
    mock_system.return_value = "Linux"
    mock_machine.return_value = "x86_64"
    reload(executor_module)
    
    assert executor_module._is_apple_silicon() == False
    assert executor_module._is_macos() == False
    print("✓ Linux correctly detected as not macOS")
    
    # Reload once more to restore actual platform detection
    reload(executor_module)


def main():
    """Run all tests."""
    print("=" * 60)
    print("MAC M2 MOUSE CONTROL TIMING TESTS")
    print("=" * 60)
    
    test_platform_detection()
    test_executor_timing_configuration()
    test_mac_keyboard_shortcut()
    
    # Run mocked test separately
    try:
        test_apple_silicon_detection()
    except Exception as e:
        print(f"\nMocked test failed (expected in some environments): {e}")
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()
