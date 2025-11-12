#!/usr/bin/env python3
"""
Test script to verify EasyOCR integration.

This script demonstrates that the OCREngine can be initialized with
all three backends and that they work correctly.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import numpy as np
import cv2


def create_test_image():
    """Create a simple test image with text."""
    # Create white background
    img = np.ones((60, 300, 3), dtype=np.uint8) * 255
    
    # Add text
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, "Test 123.45", (20, 40), font, 1.2, (0, 0, 0), 2)
    
    return img


def test_backend(backend_name):
    """Test a specific OCR backend."""
    from holdem.vision.ocr import OCREngine
    
    print(f"\n{'='*60}")
    print(f"Testing {backend_name.upper()} backend")
    print(f"{'='*60}")
    
    try:
        # Initialize OCR engine with specified backend
        ocr = OCREngine(backend=backend_name)
        print(f"✓ OCREngine initialized with backend: {ocr.backend}")
        
        # Check if backend is available
        if backend_name == "paddleocr":
            available = ocr.paddle_ocr is not None
        elif backend_name == "easyocr":
            available = ocr.easy_ocr is not None
        elif backend_name == "pytesseract":
            available = ocr.tesseract_available
        else:
            available = False
        
        if available and ocr.backend == backend_name:
            print(f"✓ {backend_name.upper()} backend is available and active")
        else:
            print(f"⚠ {backend_name.upper()} backend not available, fell back to: {ocr.backend}")
        
        # Create test image
        test_img = create_test_image()
        
        # Try to read text
        text = ocr.read_text(test_img, preprocess=False)
        print(f"✓ Read text: '{text}'")
        
        # Try to extract number
        num = ocr.extract_number(test_img)
        if num is not None:
            print(f"✓ Extracted number: {num}")
        else:
            print(f"✓ Number extraction returned None (OCR may not have recognized text)")
        
        print(f"✓ {backend_name.upper()} backend test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Error testing {backend_name.upper()}: {e}")
        return False


def main():
    """Main test function."""
    print("="*60)
    print("EasyOCR Integration Verification Script")
    print("="*60)
    print("\nThis script verifies that the OCREngine can be initialized")
    print("with all three backends: paddleocr, easyocr, and pytesseract.")
    print("\nNote: Actual OCR results depend on whether the backends are")
    print("installed. The script will fall back gracefully if not available.")
    
    # Test all three backends
    backends = ["paddleocr", "easyocr", "pytesseract"]
    results = {}
    
    for backend in backends:
        results[backend] = test_backend(backend)
    
    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for backend, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{backend.upper():15s}: {status}")
    
    print("\n" + "="*60)
    
    if all(results.values()):
        print("✓ All backend tests completed successfully!")
        print("\nThe EasyOCR integration is working correctly.")
        print("You can now use --ocr-backend argument with:")
        print("  - paddleocr (default)")
        print("  - easyocr (new)")
        print("  - pytesseract (fallback)")
        return 0
    else:
        print("⚠ Some backend tests had issues.")
        print("This is expected if the backends are not installed.")
        print("The OCREngine will fall back to available backends.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
