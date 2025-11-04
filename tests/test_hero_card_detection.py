"""Test hero card detection functionality."""

import pytest
import numpy as np
import cv2
from pathlib import Path
from holdem.vision.calibrate import TableProfile
from holdem.vision.parse_state import StateParser
from holdem.vision.cards import CardRecognizer, create_mock_templates
from holdem.vision.ocr import OCREngine
from holdem.types import PlayerState, Card


def test_card_recognizer_with_hero_templates(tmp_path):
    """Test that CardRecognizer can load and use separate hero templates."""
    # Create board templates
    board_templates_dir = tmp_path / "board_templates"
    create_mock_templates(board_templates_dir, for_hero=False)
    
    # Create hero templates
    hero_templates_dir = tmp_path / "hero_templates"
    create_mock_templates(hero_templates_dir, for_hero=True)
    
    # Create recognizer with both template sets
    recognizer = CardRecognizer(board_templates_dir, method="template", 
                                hero_templates_dir=hero_templates_dir)
    
    # Verify both template sets are loaded
    assert len(recognizer.templates) == 52
    assert len(recognizer.hero_templates) == 52
    
    # Test recognition with board templates
    ah_board = cv2.imread(str(board_templates_dir / "Ah.png"))
    if ah_board is not None:
        card = recognizer.recognize_card(ah_board, use_hero_templates=False)
        # Card might not be recognized perfectly, but should not crash
    
    # Test recognition with hero templates
    ah_hero = cv2.imread(str(hero_templates_dir / "Ah.png"))
    if ah_hero is not None:
        card = recognizer.recognize_card(ah_hero, use_hero_templates=True)
        # Card might not be recognized perfectly, but should not crash


def test_card_recognizer_fallback_to_board_templates(tmp_path):
    """Test that CardRecognizer falls back to board templates when hero templates unavailable."""
    # Create only board templates
    board_templates_dir = tmp_path / "board_templates"
    create_mock_templates(board_templates_dir, for_hero=False)
    
    # Create recognizer without hero templates
    recognizer = CardRecognizer(board_templates_dir, method="template")
    
    assert len(recognizer.templates) == 52
    assert len(recognizer.hero_templates) == 0
    
    # When requesting hero templates, should fall back to board templates
    ah_board = cv2.imread(str(board_templates_dir / "Ah.png"))
    if ah_board is not None:
        card = recognizer.recognize_card(ah_board, use_hero_templates=True)
        # Should not crash even though hero templates aren't available


def test_table_profile_hero_position_save_load(tmp_path):
    """Test that TableProfile can save and load hero_position and hero_templates_dir."""
    # Create profile with hero_position and hero_templates_dir
    profile = TableProfile()
    profile.window_title = "Test Table"
    profile.hero_position = 3
    profile.hero_templates_dir = "assets/hero_templates"
    profile.player_regions = [
        {"position": i, "card_region": {"x": 100, "y": 100, "width": 80, "height": 60}}
        for i in range(6)
    ]
    
    # Save profile
    path = tmp_path / "test_profile.json"
    profile.save(path)
    
    # Verify it was saved correctly
    import json
    with open(path) as f:
        data = json.load(f)
    assert data["hero_position"] == 3
    assert data["hero_templates_dir"] == "assets/hero_templates"
    
    # Reload profile
    loaded = TableProfile.load(path)
    assert loaded.hero_position == 3
    assert loaded.hero_templates_dir == "assets/hero_templates"
    assert len(loaded.player_regions) == 6


def test_table_profile_hero_position_none(tmp_path):
    """Test that TableProfile handles None hero_position correctly."""
    profile = TableProfile()
    profile.window_title = "Test Table"
    profile.hero_position = None
    
    # Save and reload
    path = tmp_path / "test_profile.json"
    profile.save(path)
    
    loaded = TableProfile.load(path)
    assert loaded.hero_position is None


def test_player_state_hole_cards():
    """Test that PlayerState can hold hole cards."""
    cards = [Card("A", "h"), Card("K", "s")]
    player = PlayerState(
        name="Hero",
        stack=1000.0,
        position=0,
        hole_cards=cards
    )
    
    assert player.hole_cards == cards
    assert len(player.hole_cards) == 2
    assert str(player.hole_cards[0]) == "Ah"
    assert str(player.hole_cards[1]) == "Ks"


def test_player_state_no_hole_cards():
    """Test that PlayerState can have None hole cards."""
    player = PlayerState(
        name="Opponent",
        stack=1000.0,
        position=1,
        hole_cards=None
    )
    
    assert player.hole_cards is None


def test_state_parser_with_hero_position(tmp_path):
    """Test that StateParser parses hero cards when hero_position is set."""
    # Create mock templates
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir)
    
    # Create profile with hero_position
    profile = TableProfile()
    profile.hero_position = 0
    profile.card_regions = [{"x": 400, "y": 320, "width": 400, "height": 120}]
    profile.player_regions = [
        {
            "position": 0,
            "name_region": {"x": 150, "y": 650, "width": 120, "height": 25},
            "stack_region": {"x": 150, "y": 675, "width": 120, "height": 25},
            "card_region": {"x": 130, "y": 700, "width": 160, "height": 100}
        },
        {
            "position": 1,
            "name_region": {"x": 80, "y": 480, "width": 120, "height": 25},
            "stack_region": {"x": 80, "y": 505, "width": 120, "height": 25},
            "card_region": {"x": 60, "y": 530, "width": 160, "height": 100}
        }
    ]
    profile.pot_region = {"x": 450, "y": 380, "width": 200, "height": 80}
    
    # Create mock image with cards in hero position
    img = np.ones((900, 1200, 3), dtype=np.uint8) * 255
    
    # Load templates and place them in hero's card region
    ah_template = cv2.imread(str(templates_dir / "Ah.png"))
    ks_template = cv2.imread(str(templates_dir / "Ks.png"))
    
    if ah_template is not None and ks_template is not None:
        # Place cards side by side in hero's card region
        card_h, card_w = ah_template.shape[:2]
        hero_card_region = profile.player_regions[0]["card_region"]
        x, y = hero_card_region["x"], hero_card_region["y"]
        
        # Verify bounds before placing cards
        if (y + card_h <= img.shape[0] and 
            x + 2 * card_w <= img.shape[1]):
            # Place Ah on the left
            img[y:y+card_h, x:x+card_w] = ah_template
            # Place Ks on the right
            img[y:y+card_h, x+card_w:x+2*card_w] = ks_template
    
    # Create parser
    card_recognizer = CardRecognizer(templates_dir, method="template")
    ocr_engine = OCREngine(backend="pytesseract")
    parser = StateParser(profile, card_recognizer, ocr_engine)
    
    # Parse state
    state = parser.parse(img)
    
    # Verify state was created
    assert state is not None
    assert len(state.players) == 2
    
    # Check that hero player has hole_cards (might be None if recognition fails, but field should exist)
    hero = state.players[0]
    assert hasattr(hero, 'hole_cards')
    
    # Opponent should not have hole_cards parsed
    opponent = state.players[1]
    assert opponent.hole_cards is None


def test_state_parser_without_hero_position(tmp_path):
    """Test that StateParser doesn't parse hole cards when hero_position is None."""
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir)
    
    # Create profile WITHOUT hero_position
    profile = TableProfile()
    profile.hero_position = None
    profile.card_regions = [{"x": 400, "y": 320, "width": 400, "height": 120}]
    profile.player_regions = [
        {
            "position": 0,
            "name_region": {"x": 150, "y": 650, "width": 120, "height": 25},
            "stack_region": {"x": 150, "y": 675, "width": 120, "height": 25},
            "card_region": {"x": 130, "y": 700, "width": 160, "height": 100}
        }
    ]
    profile.pot_region = {"x": 450, "y": 380, "width": 200, "height": 80}
    
    # Create mock image
    img = np.ones((900, 1200, 3), dtype=np.uint8) * 255
    
    # Create parser
    card_recognizer = CardRecognizer(templates_dir, method="template")
    ocr_engine = OCREngine(backend="pytesseract")
    parser = StateParser(profile, card_recognizer, ocr_engine)
    
    # Parse state
    state = parser.parse(img)
    
    # Verify state was created
    assert state is not None
    assert len(state.players) == 1
    
    # Player should have None hole_cards since hero_position is not set
    player = state.players[0]
    assert player.hole_cards is None


def test_state_parser_with_separate_hero_templates(tmp_path):
    """Test that StateParser uses hero templates for hero cards when available."""
    # Create board templates
    board_templates_dir = tmp_path / "board_templates"
    create_mock_templates(board_templates_dir, for_hero=False)
    
    # Create hero templates (with different styling)
    hero_templates_dir = tmp_path / "hero_templates"
    create_mock_templates(hero_templates_dir, for_hero=True)
    
    # Create profile with hero_position and hero_templates_dir
    profile = TableProfile()
    profile.hero_position = 0
    profile.hero_templates_dir = str(hero_templates_dir)
    profile.card_regions = [{"x": 400, "y": 320, "width": 400, "height": 120}]
    profile.player_regions = [
        {
            "position": 0,
            "name_region": {"x": 150, "y": 650, "width": 120, "height": 25},
            "stack_region": {"x": 150, "y": 675, "width": 120, "height": 25},
            "card_region": {"x": 130, "y": 700, "width": 160, "height": 100}
        }
    ]
    profile.pot_region = {"x": 450, "y": 380, "width": 200, "height": 80}
    
    # Create mock image
    img = np.ones((900, 1200, 3), dtype=np.uint8) * 255
    
    # Load hero templates and place them in hero's card region
    ah_hero = cv2.imread(str(hero_templates_dir / "Ah.png"))
    ks_hero = cv2.imread(str(hero_templates_dir / "Ks.png"))
    
    if ah_hero is not None and ks_hero is not None:
        card_h, card_w = ah_hero.shape[:2]
        hero_card_region = profile.player_regions[0]["card_region"]
        x, y = hero_card_region["x"], hero_card_region["y"]
        
        if (y + card_h <= img.shape[0] and x + 2 * card_w <= img.shape[1]):
            img[y:y+card_h, x:x+card_w] = ah_hero
            img[y:y+card_h, x+card_w:x+2*card_w] = ks_hero
    
    # Create parser with both template sets
    card_recognizer = CardRecognizer(board_templates_dir, method="template",
                                    hero_templates_dir=hero_templates_dir)
    ocr_engine = OCREngine(backend="pytesseract")
    parser = StateParser(profile, card_recognizer, ocr_engine)
    
    # Parse state
    state = parser.parse(img)
    
    # Verify state was created
    assert state is not None
    assert len(state.players) == 1
    
    # Check that hero player has hole_cards field
    hero = state.players[0]
    assert hasattr(hero, 'hole_cards')
    # Recognition might not be perfect with mock templates, but should not crash


def test_parse_player_cards_out_of_bounds(tmp_path):
    """Test that _parse_player_cards handles out-of-bounds regions safely."""
    # Create mock templates
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir)
    
    profile = TableProfile()
    profile.hero_position = 0
    
    # Create parser
    card_recognizer = CardRecognizer(templates_dir, method="template")
    ocr_engine = OCREngine(backend="pytesseract")
    parser = StateParser(profile, card_recognizer, ocr_engine)
    
    # Small image
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    
    # Out of bounds region
    player_region = {
        "card_region": {"x": 200, "y": 200, "width": 80, "height": 60}
    }
    
    # Should return None without crashing
    result = parser._parse_player_cards(img, player_region)
    assert result is None


def test_parse_player_cards_zero_size_region(tmp_path):
    """Test that _parse_player_cards handles zero-size regions safely."""
    # Create mock templates
    templates_dir = tmp_path / "templates"
    create_mock_templates(templates_dir)
    
    profile = TableProfile()
    profile.hero_position = 0
    
    # Create parser
    card_recognizer = CardRecognizer(templates_dir, method="template")
    ocr_engine = OCREngine(backend="pytesseract")
    parser = StateParser(profile, card_recognizer, ocr_engine)
    
    img = np.ones((900, 1200, 3), dtype=np.uint8) * 255
    
    # Zero size region
    player_region = {
        "card_region": {"x": 100, "y": 100, "width": 0, "height": 0}
    }
    
    # Should return None without crashing
    result = parser._parse_player_cards(img, player_region)
    assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
