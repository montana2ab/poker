"""Test debug image saving for player/hero cards."""

import sys
from pathlib import Path
import numpy as np
import cv2
from tempfile import TemporaryDirectory

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from holdem.vision.calibrate import TableProfile
from holdem.vision.parse_state import StateParser
from holdem.vision.cards import CardRecognizer, create_mock_templates
from holdem.vision.ocr import OCREngine


def test_player_card_debug_images_saved():
    """Test that debug images are saved for player cards when debug_dir is provided."""
    with TemporaryDirectory() as tmpdir:
        # Create mock templates
        templates_dir = Path(tmpdir) / "templates"
        create_mock_templates(templates_dir)
        
        # Create hero templates
        hero_templates_dir = Path(tmpdir) / "hero_templates"
        create_mock_templates(hero_templates_dir, for_hero=True)
        
        # Create debug directory
        debug_dir = Path(tmpdir) / "debug"
        debug_dir.mkdir()
        
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
        
        # Create mock image
        img = np.ones((900, 1200, 3), dtype=np.uint8) * 255
        
        # Create parser WITH debug directory
        card_recognizer = CardRecognizer(templates_dir, method="template", 
                                        hero_templates_dir=hero_templates_dir)
        ocr_engine = OCREngine(backend="pytesseract")
        parser = StateParser(profile, card_recognizer, ocr_engine, debug_dir=debug_dir)
        
        # Parse state (should save debug images for both board and hero cards)
        state = parser.parse(img)
        
        # Verify state was created
        assert state is not None
        
        # Verify board debug image was saved
        board_debug_files = list(debug_dir.glob("board_region_*.png"))
        assert len(board_debug_files) == 1, f"Expected 1 board debug file, found {len(board_debug_files)}"
        
        # Verify player card debug image was saved for hero (position 0)
        player_debug_files = list(debug_dir.glob("player_0_cards_*.png"))
        assert len(player_debug_files) == 1, f"Expected 1 player debug file for hero, found {len(player_debug_files)}"
        
        # Verify the player debug image is valid
        player_debug_img = cv2.imread(str(player_debug_files[0]))
        assert player_debug_img is not None, "Player debug image should be valid"
        assert player_debug_img.shape[0] == 100, "Player debug image height should match card region"
        assert player_debug_img.shape[1] == 160, "Player debug image width should match card region"
        
        # Verify no debug image for non-hero player (position 1)
        player1_debug_files = list(debug_dir.glob("player_1_cards_*.png"))
        assert len(player1_debug_files) == 0, f"Expected 0 debug files for non-hero player, found {len(player1_debug_files)}"


def test_player_card_debug_images_multiple_parses():
    """Test that multiple parses create sequentially numbered debug images for player cards."""
    with TemporaryDirectory() as tmpdir:
        # Create mock templates
        templates_dir = Path(tmpdir) / "templates"
        create_mock_templates(templates_dir)
        
        hero_templates_dir = Path(tmpdir) / "hero_templates"
        create_mock_templates(hero_templates_dir, for_hero=True)
        
        # Create debug directory
        debug_dir = Path(tmpdir) / "debug"
        debug_dir.mkdir()
        
        # Create profile with hero_position
        profile = TableProfile()
        profile.hero_position = 2
        profile.card_regions = [{"x": 400, "y": 320, "width": 400, "height": 120}]
        profile.player_regions = [
            {
                "position": 2,
                "name_region": {"x": 150, "y": 650, "width": 120, "height": 25},
                "stack_region": {"x": 150, "y": 675, "width": 120, "height": 25},
                "card_region": {"x": 130, "y": 700, "width": 160, "height": 100}
            }
        ]
        profile.pot_region = {"x": 450, "y": 380, "width": 200, "height": 80}
        
        # Create mock image
        img = np.ones((900, 1200, 3), dtype=np.uint8) * 255
        
        # Create parser with debug directory
        card_recognizer = CardRecognizer(templates_dir, method="template",
                                        hero_templates_dir=hero_templates_dir)
        ocr_engine = OCREngine(backend="pytesseract")
        parser = StateParser(profile, card_recognizer, ocr_engine, debug_dir=debug_dir)
        
        # Parse state 3 times
        for i in range(3):
            state = parser.parse(img)
            assert state is not None
        
        # Verify 3 board debug images were saved
        board_debug_files = sorted(debug_dir.glob("board_region_*.png"))
        assert len(board_debug_files) == 3, f"Expected 3 board debug files, found {len(board_debug_files)}"
        
        # Verify 3 player debug images were saved for hero
        player_debug_files = sorted(debug_dir.glob("player_2_cards_*.png"))
        assert len(player_debug_files) == 3, f"Expected 3 player debug files, found {len(player_debug_files)}"
        
        # Verify they are numbered sequentially
        assert player_debug_files[0].name == "player_2_cards_0001.png"
        assert player_debug_files[1].name == "player_2_cards_0002.png"
        assert player_debug_files[2].name == "player_2_cards_0003.png"


def test_no_player_card_debug_images_without_debug_dir():
    """Test that no player card debug images are saved when debug_dir is None."""
    with TemporaryDirectory() as tmpdir:
        # Create mock templates
        templates_dir = Path(tmpdir) / "templates"
        create_mock_templates(templates_dir)
        
        hero_templates_dir = Path(tmpdir) / "hero_templates"
        create_mock_templates(hero_templates_dir, for_hero=True)
        
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
            }
        ]
        profile.pot_region = {"x": 450, "y": 380, "width": 200, "height": 80}
        
        # Create mock image
        img = np.ones((900, 1200, 3), dtype=np.uint8) * 255
        
        # Create parser WITHOUT debug directory
        card_recognizer = CardRecognizer(templates_dir, method="template",
                                        hero_templates_dir=hero_templates_dir)
        ocr_engine = OCREngine(backend="pytesseract")
        parser = StateParser(profile, card_recognizer, ocr_engine, debug_dir=None)
        
        # Parse state (should NOT save debug images)
        state = parser.parse(img)
        
        # Verify state was created
        assert state is not None
        
        # Verify no debug images were created anywhere in tmpdir
        debug_files = list(Path(tmpdir).rglob("player_*_cards_*.png"))
        assert len(debug_files) == 0, f"Expected 0 player debug files, found {len(debug_files)}"


if __name__ == "__main__":
    # Run tests manually
    print("Testing player card debug images saved when enabled...")
    test_player_card_debug_images_saved()
    print("✓ test_player_card_debug_images_saved passed")
    
    print("\nTesting multiple player card debug images numbered sequentially...")
    test_player_card_debug_images_multiple_parses()
    print("✓ test_player_card_debug_images_multiple_parses passed")
    
    print("\nTesting no player card debug images without debug_dir...")
    test_no_player_card_debug_images_without_debug_dir()
    print("✓ test_no_player_card_debug_images_without_debug_dir passed")
    
    print("\nAll tests passed!")
