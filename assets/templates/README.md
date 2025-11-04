# Card Templates Directory

This directory contains template images for card recognition.

## Directory Structure

- **templates/** - Board card templates (community cards shown in the center)
- **hero_templates/** - Hero card templates (hole cards shown at player position)

Templates can be automatically generated using the `create_mock_templates()` function
from `holdem.vision.cards` module.

For production use, replace these with actual high-quality card images extracted
from your poker table screenshots.

## Why Separate Templates?

Board cards and hero cards often have different visual characteristics in poker clients:
- **Size**: Hero cards may be smaller or larger
- **Lighting/Brightness**: Different areas of the table may have different lighting
- **Style**: Some clients render cards differently based on their position
- **Viewing Angle**: Hero cards might have a slightly different perspective

Using separate templates for board and hero cards significantly improves recognition accuracy.

## Template Naming

Each template should be named: `{rank}{suit}.png`
- Ranks: 2, 3, 4, 5, 6, 7, 8, 9, T, J, Q, K, A
- Suits: h (hearts), d (diamonds), c (clubs), s (spades)

Examples:
- `Ah.png` - Ace of hearts
- `Ts.png` - Ten of spades
- `7d.png` - Seven of diamonds

Total: 52 templates per directory (13 ranks × 4 suits)

## Creating Templates

### Automatic (for testing):
```python
from pathlib import Path
from holdem.vision.cards import create_mock_templates

# Create board templates
create_mock_templates(Path("assets/templates"), for_hero=False)

# Create hero templates
create_mock_templates(Path("assets/hero_templates"), for_hero=True)
```

### Manual (for production):
1. Take a screenshot of your poker table with all cards visible
2. Crop each card individually
3. Save with the appropriate naming convention
4. Place board cards in `templates/` and hero cards in `hero_templates/`
