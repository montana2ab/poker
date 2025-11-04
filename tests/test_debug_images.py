"""Test debug image saving functionality."""

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


def test_debug_images_saved_when_enabled():
    """Test that debug images are saved when debug_dir is provided."""
    with TemporaryDirectory() as tmpdir:
        # Create mock templates
        templates_dir = Path(tmpdir) / "templates"
        create_mock_templates(templates_dir)
        
        # Create debug directory
        debug_dir = Path(tmpdir) / "debug"
        debug_dir.mkdir()
        
        # Create profile with card region
        profile = TableProfile()
        profile.card_regions = [{"x": 100, "y": 100, "width": 350, "height": 100}]
        profile.pot_region = {"x": 200, "y": 50, "width": 100, "height": 30}
        profile.player_regions = []
        
        # Create mock image
        img = np.ones((400, 600, 3), dtype=np.uint8) * 255
        
        # Create parser WITH debug directory
        card_recognizer = CardRecognizer(templates_dir, method="template")
        ocr_engine = OCREngine(backend="pytesseract")
        parser = StateParser(profile, card_recognizer, ocr_engine, debug_dir=debug_dir)
        
        # Parse state (should save debug image)
        state = parser.parse(img)
        
        # Verify state was created
        assert state is not None
        
        # Verify debug image was saved
        debug_files = list(debug_dir.glob("board_region_*.png"))
        assert len(debug_files) == 1, f"Expected 1 debug file, found {len(debug_files)}"
        
        # Verify the file is a valid image
        debug_img = cv2.imread(str(debug_files[0]))
        assert debug_img is not None, "Debug image should be valid"
        assert debug_img.shape[0] == 100, "Debug image height should match card region"
        assert debug_img.shape[1] == 350, "Debug image width should match card region"


def test_no_debug_images_without_debug_dir():
    """Test that no debug images are saved when debug_dir is None."""
    with TemporaryDirectory() as tmpdir:
        # Create mock templates
        templates_dir = Path(tmpdir) / "templates"
        create_mock_templates(templates_dir)
        
        # Create profile with card region
        profile = TableProfile()
        profile.card_regions = [{"x": 100, "y": 100, "width": 350, "height": 100}]
        profile.pot_region = {"x": 200, "y": 50, "width": 100, "height": 30}
        profile.player_regions = []
        
        # Create mock image
        img = np.ones((400, 600, 3), dtype=np.uint8) * 255
        
        # Create parser WITHOUT debug directory
        card_recognizer = CardRecognizer(templates_dir, method="template")
        ocr_engine = OCREngine(backend="pytesseract")
        parser = StateParser(profile, card_recognizer, ocr_engine, debug_dir=None)
        
        # Parse state (should NOT save debug image)
        state = parser.parse(img)
        
        # Verify state was created
        assert state is not None
        
        # Verify no debug images were created anywhere in tmpdir
        debug_files = list(Path(tmpdir).rglob("board_region_*.png"))
        assert len(debug_files) == 0, f"Expected 0 debug files, found {len(debug_files)}"


def test_multiple_debug_images_numbered_sequentially():
    """Test that multiple parses create sequentially numbered debug images."""
    with TemporaryDirectory() as tmpdir:
        # Create mock templates
        templates_dir = Path(tmpdir) / "templates"
        create_mock_templates(templates_dir)
        
        # Create debug directory
        debug_dir = Path(tmpdir) / "debug"
        debug_dir.mkdir()
        
        # Create profile with card region
        profile = TableProfile()
        profile.card_regions = [{"x": 100, "y": 100, "width": 350, "height": 100}]
        profile.pot_region = {"x": 200, "y": 50, "width": 100, "height": 30}
        profile.player_regions = []
        
        # Create mock image
        img = np.ones((400, 600, 3), dtype=np.uint8) * 255
        
        # Create parser with debug directory
        card_recognizer = CardRecognizer(templates_dir, method="template")
        ocr_engine = OCREngine(backend="pytesseract")
        parser = StateParser(profile, card_recognizer, ocr_engine, debug_dir=debug_dir)
        
        # Parse state 3 times
        for i in range(3):
            state = parser.parse(img)
            assert state is not None
        
        # Verify 3 debug images were saved
        debug_files = sorted(debug_dir.glob("board_region_*.png"))
        assert len(debug_files) == 3, f"Expected 3 debug files, found {len(debug_files)}"
        
        # Verify they are numbered sequentially
        assert debug_files[0].name == "board_region_0001.png"
        assert debug_files[1].name == "board_region_0002.png"
        assert debug_files[2].name == "board_region_0003.png"


if __name__ == "__main__":
    # Run tests manually
    print("Testing debug images saved when enabled...")
    test_debug_images_saved_when_enabled()
    print("✓ test_debug_images_saved_when_enabled passed")
    
    print("\nTesting no debug images without debug_dir...")
    test_no_debug_images_without_debug_dir()
    print("✓ test_no_debug_images_without_debug_dir passed")
    
    print("\nTesting multiple debug images numbered sequentially...")
    test_multiple_debug_images_numbered_sequentially()
    print("✓ test_multiple_debug_images_numbered_sequentially passed")
    
    print("\nAll tests passed!")
