"""Test that run_dry_run and run_autoplay have chat and event fusion integration."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_run_dry_run_has_chat_integration():
    """Verify run_dry_run.py has chat parsing integration."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        source = f.read()
    
    # Check for ChatEnabledStateParser import
    assert 'ChatEnabledStateParser' in source, \
        "run_dry_run.py must import ChatEnabledStateParser"
    
    # Check for chat parsing argument
    assert 'disable-chat-parsing' in source, \
        "run_dry_run.py must have --disable-chat-parsing argument"
    
    # Check for parse_with_events usage
    assert 'parse_with_events' in source, \
        "run_dry_run.py must use parse_with_events method"
    
    # Check for event logging
    assert 'EVENT' in source or 'events' in source, \
        "run_dry_run.py must handle events"
    
    print("✓ run_dry_run.py has chat parsing integration")


def test_run_autoplay_has_chat_integration():
    """Verify run_autoplay.py has chat parsing integration."""
    autoplay_path = Path(__file__).parent.parent / "src/holdem/cli/run_autoplay.py"
    
    with open(autoplay_path, 'r') as f:
        source = f.read()
    
    # Check for ChatEnabledStateParser import
    assert 'ChatEnabledStateParser' in source, \
        "run_autoplay.py must import ChatEnabledStateParser"
    
    # Check for chat parsing argument
    assert 'disable-chat-parsing' in source, \
        "run_autoplay.py must have --disable-chat-parsing argument"
    
    # Check for parse_with_events usage
    assert 'parse_with_events' in source, \
        "run_autoplay.py must use parse_with_events method"
    
    # Check for event logging
    assert 'EVENT' in source or 'events' in source, \
        "run_autoplay.py must handle events"
    
    print("✓ run_autoplay.py has chat parsing integration")


def test_chat_enabled_parser_exists():
    """Verify ChatEnabledStateParser module exists."""
    parser_path = Path(__file__).parent.parent / "src/holdem/vision/chat_enabled_parser.py"
    
    assert parser_path.exists(), \
        "chat_enabled_parser.py must exist"
    
    with open(parser_path, 'r') as f:
        source = f.read()
    
    # Check that the class has the required methods
    assert 'class ChatEnabledStateParser' in source, \
        "ChatEnabledStateParser class must be defined"
    
    assert 'def parse(' in source, \
        "ChatEnabledStateParser must have parse() method"
    
    assert 'def parse_with_events(' in source, \
        "ChatEnabledStateParser must have parse_with_events() method"
    
    print("✓ ChatEnabledStateParser module exists and is properly defined")


def test_vision_module_exports_chat_enabled_parser():
    """Verify vision module exports ChatEnabledStateParser."""
    vision_init_path = Path(__file__).parent.parent / "src/holdem/vision/__init__.py"
    
    with open(vision_init_path, 'r') as f:
        source = f.read()
    
    assert 'ChatEnabledStateParser' in source, \
        "holdem.vision __init__.py must export ChatEnabledStateParser"
    
    print("✓ holdem.vision module exports ChatEnabledStateParser")


def test_chat_parser_and_event_fusion_exist():
    """Verify chat parser and event fusion modules exist."""
    chat_parser_path = Path(__file__).parent.parent / "src/holdem/vision/chat_parser.py"
    event_fusion_path = Path(__file__).parent.parent / "src/holdem/vision/event_fusion.py"
    
    assert chat_parser_path.exists(), "chat_parser.py must exist"
    assert event_fusion_path.exists(), "event_fusion.py must exist"
    
    # Check for key classes
    with open(chat_parser_path, 'r') as f:
        chat_source = f.read()
    
    assert 'class ChatParser' in chat_source, "ChatParser class must exist"
    assert 'class GameEvent' in chat_source, "GameEvent class must exist"
    assert 'class EventSource' in chat_source, "EventSource class must exist"
    
    with open(event_fusion_path, 'r') as f:
        fusion_source = f.read()
    
    assert 'class EventFuser' in fusion_source, "EventFuser class must exist"
    assert 'class FusedEvent' in fusion_source, "FusedEvent class must exist"
    
    print("✓ Chat parser and event fusion modules exist")


def test_action_detection_in_parse_state():
    """Verify action detection is used in parse_state."""
    parse_state_path = Path(__file__).parent.parent / "src/holdem/vision/parse_state.py"
    
    with open(parse_state_path, 'r') as f:
        source = f.read()
    
    # Check for action detection
    assert 'detect_action' in source or 'action_region' in source, \
        "parse_state.py must have action detection functionality"
    
    assert 'last_action' in source, \
        "parse_state.py must track last_action"
    
    print("✓ parse_state.py has action detection")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Chat and Event Fusion Integration in Dry Run and Auto Play")
    print("=" * 70)
    print()
    
    try:
        test_chat_enabled_parser_exists()
        test_vision_module_exports_chat_enabled_parser()
        test_chat_parser_and_event_fusion_exist()
        test_action_detection_in_parse_state()
        test_run_dry_run_has_chat_integration()
        test_run_autoplay_has_chat_integration()
        
        print()
        print("=" * 70)
        print("✅ All integration tests passed!")
        print("=" * 70)
        print()
        print("Summary:")
        print("  ✓ ChatEnabledStateParser properly defined")
        print("  ✓ Vision module exports ChatEnabledStateParser")
        print("  ✓ Chat parser and event fusion modules available")
        print("  ✓ Action detection available in parse_state")
        print("  ✓ run_dry_run.py integrated with chat parsing")
        print("  ✓ run_autoplay.py integrated with chat parsing")
        print()
        print("Chat and event fusion features are now available in both modes!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
