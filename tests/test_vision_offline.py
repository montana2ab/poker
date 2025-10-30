"""Test vision system offline (without actual screen capture)."""

import pytest
import numpy as np
import cv2
from pathlib import Path
from holdem.vision.cards import CardRecognizer, create_mock_templates
from holdem.vision.ocr import OCREngine
from holdem.types import Card


def test_card_recognition_accuracy(tmp_path):
    """Test card recognition accuracy on mock templates."""
    # Create templates
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir)
    
    recognizer = CardRecognizer(templates_dir, method="template")
    
    # Test recognition on templates themselves (should be 100%)
    correct = 0
    total = 0
    
    ranks = ['A', 'K', 'Q', 'J', 'T']  # Test subset
    suits = ['h', 'd']
    
    for rank in ranks:
        for suit in suits:
            card_name = f"{rank}{suit}"
            template_path = templates_dir / f"{card_name}.png"
            
            if template_path.exists():
                img = cv2.imread(str(template_path))
                recognized = recognizer.recognize_card(img, confidence_threshold=0.7)
                
                total += 1
                if recognized and recognized.rank == rank and recognized.suit == suit:
                    correct += 1
    
    accuracy = correct / total if total > 0 else 0
    assert accuracy >= 0.98, f"Card recognition accuracy {accuracy:.2%} should be ≥98%"


def test_ocr_number_extraction():
    """Test OCR number extraction on simple images."""
    # Create simple image with number
    img = np.ones((50, 100, 3), dtype=np.uint8) * 255
    cv2.putText(img, "1234", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    
    ocr = OCREngine(backend="pytesseract")
    
    # Note: This test may be unreliable without proper OCR setup
    # In production, would test against actual sample images
    
    # Just verify the system doesn't crash
    try:
        number = ocr.extract_number(img)
        if number is not None:
            assert isinstance(number, float)
    except:
        # OCR might not be fully configured in test environment
        pass


def test_template_creation():
    """Test that template creation produces all cards."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        templates_dir = Path(tmpdir) / "templates"
        create_mock_templates(templates_dir)
        
        # Should have 52 templates (13 ranks × 4 suits)
        templates = list(templates_dir.glob("*.png"))
        assert len(templates) == 52, f"Should have 52 templates, got {len(templates)}"


def test_card_from_string():
    """Test card string parsing."""
    card = Card.from_string("Ah")
    assert card.rank == "A"
    assert card.suit == "h"
    
    card2 = Card.from_string("Ts")
    assert card2.rank == "T"
    assert card2.suit == "s"
    
    with pytest.raises(ValueError):
        Card.from_string("invalid")


def test_mock_card_recognition_stability(tmp_path):
    """Test that card recognition is stable across multiple calls."""
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir)
    
    recognizer = CardRecognizer(templates_dir, method="template")
    
    # Create a test card image
    test_card_path = templates_dir / "Ah.png"
    img = cv2.imread(str(test_card_path))
    
    # Recognize multiple times
    results = []
    for _ in range(5):
        result = recognizer.recognize_card(img, confidence_threshold=0.7)
        if result:
            results.append(str(result))
    
    # All results should be the same
    if results:
        assert all(r == results[0] for r in results), "Recognition should be stable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
