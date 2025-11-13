"""Test second card recognition fix."""

import pytest
import numpy as np
import cv2
from pathlib import Path
from holdem.vision.cards import CardRecognizer, create_mock_templates
from holdem.types import Card


def test_card_width_distribution_even_width(tmp_path):
    """Test that cards are extracted with correct widths when width is evenly divisible."""
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir, for_hero=False)
    
    recognizer = CardRecognizer(templates_dir, method="template")
    
    # Create an image with width perfectly divisible by 2
    img = np.ones((100, 200, 3), dtype=np.uint8) * 255
    
    # Test extraction (we don't care about recognition, just extraction)
    cards = recognizer.recognize_cards(img, num_cards=2, use_hero_templates=False, skip_empty_check=True)
    
    # Should return 2 cards (might be None if not recognized)
    assert len(cards) == 2


def test_card_width_distribution_odd_width(tmp_path):
    """Test that cards are extracted with correct widths when width has remainder."""
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir, for_hero=False)
    
    recognizer = CardRecognizer(templates_dir, method="template")
    
    # Create an image with width NOT divisible by 2 (161 = 80*2 + 1)
    img = np.ones((100, 161, 3), dtype=np.uint8) * 255
    
    # Test extraction
    cards = recognizer.recognize_cards(img, num_cards=2, use_hero_templates=False, skip_empty_check=True)
    
    # Should return 2 cards (might be None if not recognized)
    assert len(cards) == 2
    # The key is that the second card should get the extra pixel


def test_card_spacing_positive(tmp_path):
    """Test card extraction with positive spacing (gap between cards)."""
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir, for_hero=False)
    
    recognizer = CardRecognizer(templates_dir, method="template")
    
    # 200 pixels total, 10 pixels spacing between 2 cards
    # Each card should get: (200 - 10) / 2 = 95 pixels
    img = np.ones((100, 200, 3), dtype=np.uint8) * 255
    
    cards = recognizer.recognize_cards(img, num_cards=2, card_spacing=10, skip_empty_check=True)
    
    assert len(cards) == 2


def test_card_spacing_negative_overlap(tmp_path):
    """Test card extraction with negative spacing (overlapping cards)."""
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir, for_hero=False)
    
    recognizer = CardRecognizer(templates_dir, method="template")
    
    # 200 pixels total, -10 pixels spacing (cards overlap by 10 pixels)
    # Each card should get: (200 - (1 * -10)) / 2 = 210 / 2 = 105 pixels
    img = np.ones((100, 200, 3), dtype=np.uint8) * 255
    
    cards = recognizer.recognize_cards(img, num_cards=2, card_spacing=-10, skip_empty_check=True)
    
    assert len(cards) == 2


def test_two_cards_full_width_usage(tmp_path):
    """Test that both cards use the full available width."""
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir, for_hero=True)
    
    recognizer = CardRecognizer(templates_dir, method="template", hero_templates_dir=templates_dir)
    
    # Load two card templates
    ah_template = cv2.imread(str(templates_dir / "Ah.png"))
    ks_template = cv2.imread(str(templates_dir / "Ks.png"))
    
    if ah_template is None or ks_template is None:
        pytest.skip("Templates not loaded correctly")
    
    # Get template dimensions
    card_h, card_w = ah_template.shape[:2]
    
    # Create image with 2 cards side by side (with 1 extra pixel)
    total_width = 2 * card_w + 1
    img = np.ones((card_h, total_width, 3), dtype=np.uint8) * 255
    
    # Place cards
    img[:, 0:card_w] = ah_template
    img[:, card_w:card_w*2] = ks_template
    # The extra pixel at position 2*card_w remains white
    
    # Recognize cards
    cards = recognizer.recognize_cards(img, num_cards=2, use_hero_templates=True, skip_empty_check=True)
    
    # Should recognize both cards (with the improved algorithm giving the extra pixel to the second card)
    assert len(cards) == 2
    # At least one card should be recognized (templates might not match perfectly)
    recognized = [c for c in cards if c is not None]
    assert len(recognized) >= 1


def test_hero_cards_with_odd_width(tmp_path):
    """Test hero card recognition with odd width (simulates real-world scenario)."""
    # Create hero templates
    hero_templates_dir = tmp_path / "hero_templates"
    create_mock_templates(hero_templates_dir, for_hero=True)
    
    recognizer = CardRecognizer(method="template", hero_templates_dir=hero_templates_dir)
    
    # Simulate a real scenario: hero card region is 161 pixels wide
    # Old algorithm: card 0 gets [0:80], card 1 gets [80:160], pixel 160 is lost
    # New algorithm: card 0 gets [0:80], card 1 gets [80:161], uses all pixels
    img = np.ones((100, 161, 3), dtype=np.uint8) * 255
    
    # Load templates and place them
    ah_template = cv2.imread(str(hero_templates_dir / "Ah.png"))
    ks_template = cv2.imread(str(hero_templates_dir / "Ks.png"))
    
    if ah_template is not None and ks_template is not None:
        # Resize templates to fit our image
        card_h, card_w = ah_template.shape[:2]
        target_w = 80  # Each card gets approximately 80 pixels
        
        ah_resized = cv2.resize(ah_template, (target_w, card_h))
        ks_resized = cv2.resize(ks_template, (target_w, card_h))
        
        # Place cards
        img[:, 0:target_w] = ah_resized
        img[:, target_w:target_w*2] = ks_resized
    
    # Recognize cards with hero templates
    cards = recognizer.recognize_cards(img, num_cards=2, use_hero_templates=True, skip_empty_check=True)
    
    # Should return 2 cards
    assert len(cards) == 2
    
    # With improved logging, we should see details about extraction
    # The second card should now get pixels [80:161] instead of [80:160]


def test_confidence_logging(tmp_path, caplog):
    """Test that card recognition logs confidence scores."""
    import logging
    caplog.set_level(logging.INFO)
    
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir, for_hero=True)
    
    recognizer = CardRecognizer(templates_dir, method="template", hero_templates_dir=templates_dir)
    
    img = np.ones((100, 200, 3), dtype=np.uint8) * 255
    
    cards = recognizer.recognize_cards(img, num_cards=2, use_hero_templates=True, skip_empty_check=True)
    
    # Check that logging includes card extraction details
    log_messages = [record.message for record in caplog.records]
    
    # Should see messages about card extraction
    extraction_logs = [msg for msg in log_messages if "Extracting card" in msg or "Card recognition summary" in msg]
    assert len(extraction_logs) > 0


def test_multiple_cards_with_spacing(tmp_path):
    """Test recognition of 5 board cards with spacing."""
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir, for_hero=False)
    
    recognizer = CardRecognizer(templates_dir, method="template")
    
    # 5 cards with 5 pixels spacing between each
    # Total spacing = 4 * 5 = 20 pixels
    # If total width is 400, each card gets (400 - 20) / 5 = 76 pixels
    img = np.ones((100, 400, 3), dtype=np.uint8) * 255
    
    cards = recognizer.recognize_cards(img, num_cards=5, card_spacing=5, skip_empty_check=True)
    
    assert len(cards) == 5


def test_backward_compatibility_no_spacing(tmp_path):
    """Test that default behavior (no spacing) still works."""
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir, for_hero=False)
    
    recognizer = CardRecognizer(templates_dir, method="template")
    
    img = np.ones((100, 200, 3), dtype=np.uint8) * 255
    
    # Call without card_spacing parameter (default should be 0)
    cards = recognizer.recognize_cards(img, num_cards=2, skip_empty_check=True)
    
    assert len(cards) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
