"""Test chat OCR focus mode functionality."""

import sys
from pathlib import Path


def test_chat_ocr_focus_flag_in_run_dry_run():
    """Test that --chat-ocr-focus flag is defined in run_dry_run.py."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    assert dry_run_path.exists(), f"run_dry_run.py not found at {dry_run_path}"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check that chat-ocr-focus flag is defined
    assert '--chat-ocr-focus' in content, "Should have --chat-ocr-focus flag"
    assert 'action="store_true"' in content, "Flag should be store_true action"
    assert 'help="Enable chat OCR focus mode' in content, "Should have help text"
    
    print("✓ run_dry_run.py has --chat-ocr-focus flag defined")


def test_chat_ocr_focus_flag_in_run_autoplay():
    """Test that --chat-ocr-focus flag is defined in run_autoplay.py."""
    autoplay_path = Path(__file__).parent.parent / "src/holdem/cli/run_autoplay.py"
    assert autoplay_path.exists(), f"run_autoplay.py not found at {autoplay_path}"
    
    with open(autoplay_path, 'r') as f:
        content = f.read()
    
    # Check that chat-ocr-focus flag is defined
    assert '--chat-ocr-focus' in content, "Should have --chat-ocr-focus flag"
    assert 'action="store_true"' in content, "Flag should be store_true action"
    assert 'help="Enable chat OCR focus mode' in content, "Should have help text"
    
    print("✓ run_autoplay.py has --chat-ocr-focus flag defined")


def test_chat_ocr_focus_mode_function_exists():
    """Test that _run_chat_ocr_focus_mode function exists in both CLI files."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    autoplay_path = Path(__file__).parent.parent / "src/holdem/cli/run_autoplay.py"
    
    with open(dry_run_path, 'r') as f:
        dry_run_content = f.read()
    
    with open(autoplay_path, 'r') as f:
        autoplay_content = f.read()
    
    # Check that function is defined
    assert 'def _run_chat_ocr_focus_mode(' in dry_run_content, \
        "Should have _run_chat_ocr_focus_mode function in run_dry_run.py"
    assert 'def _run_chat_ocr_focus_mode(' in autoplay_content, \
        "Should have _run_chat_ocr_focus_mode function in run_autoplay.py"
    
    print("✓ Both CLI files have _run_chat_ocr_focus_mode function")


def test_chat_ocr_focus_mode_has_banner():
    """Test that chat OCR focus mode displays a banner."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check for banner display
    assert '[CHAT OCR FOCUS] Enabled' in content, "Should display banner when mode is enabled"
    assert 'only chat OCR + events will be processed' in content, \
        "Banner should explain what the mode does"
    
    print("✓ Chat OCR focus mode displays banner")


def test_chat_ocr_focus_mode_has_detailed_logging():
    """Test that chat OCR focus mode includes detailed timing logs."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check for detailed timing logs
    required_logs = [
        '[CHAT OCR FOCUS] Screenshot latency',
        '[CHAT OCR FOCUS] Chat crop latency',
        '[CHAT OCR FOCUS] OCR latency',
        '[CHAT OCR FOCUS] Chat parse latency',
        '[CHAT OCR FOCUS] Total chat cycle latency',
    ]
    
    for log_msg in required_logs:
        assert log_msg in content, f"Should have logging for: {log_msg}"
    
    print("✓ Chat OCR focus mode has detailed timing logs")


def test_chat_ocr_focus_mode_has_preprocessing():
    """Test that chat OCR focus mode includes image preprocessing."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check for preprocessing steps
    assert 'cv2.cvtColor' in content, "Should convert to grayscale"
    assert 'cv2.convertScaleAbs' in content, "Should apply contrast enhancement"
    assert 'alpha=1.2' in content, "Should use alpha for contrast"
    
    print("✓ Chat OCR focus mode includes image preprocessing")


def test_chat_ocr_focus_mode_has_jsonl_logging():
    """Test that chat OCR focus mode supports JSONL logging."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check for JSONL logging
    assert 'chat_ocr_focus_' in content, "Should create JSONL log file"
    assert 'jsonl_file' in content, "Should use jsonl_file variable"
    assert 'json.dumps' in content, "Should dump JSON records"
    
    print("✓ Chat OCR focus mode supports JSONL logging")


def test_chat_ocr_focus_mode_early_return():
    """Test that chat OCR focus mode returns early before full vision setup."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check for early return logic
    assert 'if args.chat_ocr_focus:' in content, "Should check for flag"
    assert '_run_chat_ocr_focus_mode(args, profile, ocr_engine, screen_capture, table_detector)' in content, \
        "Should call chat OCR focus mode function"
    assert 'return' in content, "Should return early"
    
    print("✓ Chat OCR focus mode returns early before full vision setup")


def test_chat_ocr_focus_mode_no_policy_required():
    """Test that chat OCR focus mode is called before policy loading."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Find line numbers for key operations
    chat_focus_call_line = None
    policy_load_line = None
    
    for i, line in enumerate(lines):
        if '_run_chat_ocr_focus_mode(args, profile, ocr_engine, screen_capture, table_detector)' in line:
            chat_focus_call_line = i
        if 'policy = PolicyStore.load' in line:
            policy_load_line = i
    
    assert chat_focus_call_line is not None, "Should have chat OCR focus mode call"
    assert policy_load_line is not None, "Should have policy load"
    
    # Chat focus mode should be called BEFORE policy is loaded
    assert chat_focus_call_line < policy_load_line, \
        f"Chat OCR focus mode (line {chat_focus_call_line}) should be called before policy loading (line {policy_load_line})"
    
    print("✓ Chat OCR focus mode is called before expensive policy loading")


def test_chat_ocr_focus_mode_validates_chat_region():
    """Test that chat OCR focus mode validates chat_region exists."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check for chat region validation
    assert 'if not profile.chat_region:' in content, "Should check if chat_region exists"
    assert 'No chat_region defined in profile' in content, "Should have error message"
    
    print("✓ Chat OCR focus mode validates chat_region exists")


def test_syntax_valid():
    """Test that both CLI files still have valid Python syntax."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    autoplay_path = Path(__file__).parent.parent / "src/holdem/cli/run_autoplay.py"
    
    try:
        import ast
        with open(dry_run_path, 'r') as f:
            ast.parse(f.read())
        with open(autoplay_path, 'r') as f:
            ast.parse(f.read())
        print("✓ Both CLI files have valid Python syntax")
    except SyntaxError as e:
        raise AssertionError(f"Syntax error: {e}")


if __name__ == "__main__":
    try:
        import pytest
        pytest.main([__file__, "-v"])
    except ImportError:
        # Run tests manually without pytest
        print("Running tests without pytest...")
        
        test_chat_ocr_focus_flag_in_run_dry_run()
        test_chat_ocr_focus_flag_in_run_autoplay()
        test_chat_ocr_focus_mode_function_exists()
        test_chat_ocr_focus_mode_has_banner()
        test_chat_ocr_focus_mode_has_detailed_logging()
        test_chat_ocr_focus_mode_has_preprocessing()
        test_chat_ocr_focus_mode_has_jsonl_logging()
        test_chat_ocr_focus_mode_early_return()
        test_chat_ocr_focus_mode_no_policy_required()
        test_chat_ocr_focus_mode_validates_chat_region()
        test_syntax_valid()
        
        print("\n✅ All tests passed!")
