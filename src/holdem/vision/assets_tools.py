"""Asset management utilities for vision system."""

from pathlib import Path
import shutil
from holdem.vision.cards import create_mock_templates
from holdem.utils.logging import get_logger

logger = get_logger("vision.assets_tools")


def setup_vision_assets(base_dir: Path):
    """Setup default vision assets."""
    templates_dir = base_dir / "templates"
    samples_dir = base_dir / "samples"
    
    # Create directories
    templates_dir.mkdir(parents=True, exist_ok=True)
    samples_dir.mkdir(parents=True, exist_ok=True)
    
    # Create mock templates if they don't exist
    if not any(templates_dir.glob("*.png")):
        logger.info("Creating mock card templates...")
        create_mock_templates(templates_dir)
    
    logger.info(f"Vision assets setup in {base_dir}")


def verify_assets(base_dir: Path) -> bool:
    """Verify that required assets exist."""
    templates_dir = base_dir / "templates"
    
    if not templates_dir.exists():
        logger.error(f"Templates directory not found: {templates_dir}")
        return False
    
    # Check for card templates
    num_templates = len(list(templates_dir.glob("*.png")))
    if num_templates < 52:
        logger.warning(f"Only {num_templates}/52 card templates found")
        return False
    
    logger.info(f"Assets verified: {num_templates} templates")
    return True
