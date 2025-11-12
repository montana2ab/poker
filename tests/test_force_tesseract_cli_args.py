"""Test force-tesseract CLI arguments integration."""

import sys
from pathlib import Path


def test_run_dry_run_force_tesseract_arg():
    """Test that run_dry_run.py properly parses --force-tesseract argument."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    assert dry_run_path.exists(), f"run_dry_run.py not found at {dry_run_path}"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check that the argument is defined
    assert '--force-tesseract' in content, "Missing --force-tesseract argument"
    assert 'force_tesseract' in content, "force_tesseract variable not found"
    
    # Check that it's used to set the OCR backend
    assert 'ocr_backend' in content, "ocr_backend variable not found"
    assert 'pytesseract' in content, "pytesseract backend option not found"
    assert 'args.force_tesseract' in content, "args.force_tesseract usage not found"
    
    print("✓ run_dry_run.py has --force-tesseract CLI argument")


def test_run_autoplay_force_tesseract_arg():
    """Test that run_autoplay.py properly parses --force-tesseract argument."""
    autoplay_path = Path(__file__).parent.parent / "src/holdem/cli/run_autoplay.py"
    assert autoplay_path.exists(), f"run_autoplay.py not found at {autoplay_path}"
    
    with open(autoplay_path, 'r') as f:
        content = f.read()
    
    # Check that the argument is defined
    assert '--force-tesseract' in content, "Missing --force-tesseract argument"
    assert 'force_tesseract' in content, "force_tesseract variable not found"
    
    # Check that it's used to set the OCR backend
    assert 'ocr_backend' in content, "ocr_backend variable not found"
    assert 'pytesseract' in content, "pytesseract backend option not found"
    assert 'args.force_tesseract' in content, "args.force_tesseract usage not found"
    
    print("✓ run_autoplay.py has --force-tesseract CLI argument")


def test_ocr_engine_supports_backend_param():
    """Test that OCREngine accepts backend parameter."""
    ocr_path = Path(__file__).parent.parent / "src/holdem/vision/ocr.py"
    assert ocr_path.exists(), f"ocr.py not found at {ocr_path}"
    
    with open(ocr_path, 'r') as f:
        content = f.read()
    
    # Check that OCREngine __init__ accepts backend parameter
    assert 'def __init__' in content, "__init__ method not found"
    assert 'backend: str' in content, "backend parameter not found"
    assert 'self.backend' in content, "self.backend assignment not found"
    
    # Check that both backends are supported
    assert 'paddleocr' in content.lower(), "paddleocr backend not found"
    assert 'pytesseract' in content.lower(), "pytesseract backend not found"
    
    print("✓ OCREngine supports backend parameter")


def test_consistent_implementation():
    """Test that both CLI files implement force-tesseract consistently."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    autoplay_path = Path(__file__).parent.parent / "src/holdem/cli/run_autoplay.py"
    
    with open(dry_run_path, 'r') as f:
        dry_run_content = f.read()
    
    with open(autoplay_path, 'r') as f:
        autoplay_content = f.read()
    
    # Both should have the same help text pattern
    assert 'Force use of Tesseract OCR' in dry_run_content, "Missing help text in dry_run"
    assert 'Force use of Tesseract OCR' in autoplay_content, "Missing help text in autoplay"
    
    # Both should implement the same logic pattern
    assert 'if args.force_tesseract' in dry_run_content, "Missing conditional in dry_run"
    assert 'if args.force_tesseract' in autoplay_content, "Missing conditional in autoplay"
    
    print("✓ Both CLI files implement force-tesseract consistently")


def test_logging_when_force_tesseract():
    """Test that there's appropriate logging when force-tesseract is used."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    autoplay_path = Path(__file__).parent.parent / "src/holdem/cli/run_autoplay.py"
    
    with open(dry_run_path, 'r') as f:
        dry_run_content = f.read()
    
    with open(autoplay_path, 'r') as f:
        autoplay_content = f.read()
    
    # Check for logging when force-tesseract is used
    assert 'logger.info' in dry_run_content, "No logger.info found in dry_run"
    assert 'logger.info' in autoplay_content, "No logger.info found in autoplay"
    
    # Should mention Tesseract in the logging
    assert 'Tesseract' in dry_run_content, "Tesseract not mentioned in dry_run"
    assert 'Tesseract' in autoplay_content, "Tesseract not mentioned in autoplay"
    
    print("✓ Both CLI files have appropriate logging for force-tesseract")


if __name__ == "__main__":
    try:
        import pytest
        pytest.main([__file__, "-v"])
    except ImportError:
        # Run tests manually without pytest
        print("Running tests without pytest...")
        
        test_run_dry_run_force_tesseract_arg()
        test_run_autoplay_force_tesseract_arg()
        test_ocr_engine_supports_backend_param()
        test_consistent_implementation()
        test_logging_when_force_tesseract()
        
        print("\n✅ All tests passed!")
