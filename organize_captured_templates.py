#!/usr/bin/env python
"""Tool to organize and label captured card templates."""

import argparse
import shutil
from pathlib import Path
from typing import Optional
import cv2
import numpy as np

from holdem.utils.logging import setup_logger

logger = setup_logger("organize_templates")


def show_card_and_get_label(image_path: Path) -> Optional[str]:
    """
    Display a card image and prompt user for its identity.
    
    Args:
        image_path: Path to card image
        
    Returns:
        Card label (e.g., "Ah", "Ks") or None to skip
    """
    # Load image
    img = cv2.imread(str(image_path))
    if img is None:
        logger.error(f"Could not load image: {image_path}")
        return None
    
    # Display image
    cv2.imshow("Card Template - What card is this?", img)
    
    print("\n" + "=" * 60)
    print(f"Image: {image_path.name}")
    print("=" * 60)
    print("Enter card identity (e.g., 'Ah' for Ace of Hearts)")
    print("Or press Enter to skip this card")
    print("")
    print("Ranks: 2, 3, 4, 5, 6, 7, 8, 9, T, J, Q, K, A")
    print("Suits: h (hearts), d (diamonds), c (clubs), s (spades)")
    print("Examples: Ah, Ks, 7d, Tc")
    print("")
    
    # Wait for keyboard input
    cv2.waitKey(100)  # Small delay to show image
    
    label = input("Card identity (or Enter to skip): ").strip()
    
    cv2.destroyAllWindows()
    
    if not label:
        return None
    
    # Validate label format
    if len(label) != 2:
        logger.warning(f"Invalid format: {label} (should be 2 characters)")
        return None
    
    rank = label[0].upper()
    suit = label[1].lower()
    
    valid_ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    valid_suits = ['h', 'd', 'c', 's']
    
    if rank not in valid_ranks:
        logger.warning(f"Invalid rank: {rank}")
        return None
    
    if suit not in valid_suits:
        logger.warning(f"Invalid suit: {suit}")
        return None
    
    return f"{rank}{suit}"


def organize_templates(
    input_dir: Path,
    output_dir: Path,
    interactive: bool = True,
    overwrite: bool = False
):
    """
    Organize captured templates by identifying and renaming them.
    
    Args:
        input_dir: Directory with captured templates
        output_dir: Directory to save organized templates
        interactive: If True, prompt user to identify each card
        overwrite: If True, overwrite existing templates
    """
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        return
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get list of images
    image_files = sorted(input_dir.glob("*.png"))
    
    if not image_files:
        logger.warning(f"No PNG images found in {input_dir}")
        return
    
    logger.info(f"Found {len(image_files)} images to process")
    
    # Track statistics
    processed = 0
    skipped = 0
    saved = 0
    
    # Process each image
    for i, image_path in enumerate(image_files, 1):
        logger.info(f"\nProcessing {i}/{len(image_files)}: {image_path.name}")
        
        if interactive:
            # Ask user to identify the card
            label = show_card_and_get_label(image_path)
            
            if label is None:
                logger.info("Skipped")
                skipped += 1
                continue
        else:
            # Non-interactive mode - copy with original name
            label = image_path.stem
        
        processed += 1
        
        # Determine output path
        output_path = output_dir / f"{label}.png"
        
        # Check if already exists
        if output_path.exists() and not overwrite:
            logger.info(f"Template for {label} already exists")
            choice = input("Overwrite? (y/n): ").strip().lower()
            if choice != 'y':
                logger.info("Kept existing template")
                continue
        
        # Copy/move the file
        shutil.copy2(image_path, output_path)
        logger.info(f"Saved: {output_path}")
        saved += 1
    
    # Show statistics
    logger.info("\n" + "=" * 60)
    logger.info("ORGANIZATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total images: {len(image_files)}")
    logger.info(f"Processed: {processed}")
    logger.info(f"Skipped: {skipped}")
    logger.info(f"Saved: {saved}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Organize and label captured card templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode - identify each card manually
  python organize_captured_templates.py \\
      --input assets/templates_captured/board \\
      --output assets/templates
  
  # Organize hero cards
  python organize_captured_templates.py \\
      --input assets/templates_captured/hero \\
      --output assets/hero_templates
  
  # Non-interactive mode (keep original filenames)
  python organize_captured_templates.py \\
      --input templates_captured/board \\
      --output templates \\
      --no-interactive

Workflow:
  1. Run capture_templates.py while playing poker
  2. Run this script to identify and organize the captures
  3. Review the organized templates in output directory
  4. Delete duplicates or low-quality templates
  5. Use the templates with CardRecognizer
        """
    )
    
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input directory with captured templates"
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for organized templates"
    )
    
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Don't prompt for card identification"
    )
    
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing templates without asking"
    )
    
    args = parser.parse_args()
    
    organize_templates(
        input_dir=args.input,
        output_dir=args.output,
        interactive=not args.no_interactive,
        overwrite=args.overwrite
    )


if __name__ == "__main__":
    main()
