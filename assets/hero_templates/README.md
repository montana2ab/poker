# Hero Card Templates Directory

This directory contains template images specifically for recognizing hero (player) cards.

Hero cards are the hole cards dealt to the player and typically appear:
- At the bottom of the screen (in the player's position)
- Smaller or larger than board cards
- With different lighting or styling than community cards
- From a different viewing angle

## Why Separate Hero Templates?

Hero cards often have visual differences from board cards in poker clients:
- **Position-specific rendering**: Cards at player positions may use different graphics
- **Size differences**: Hero cards might be displayed at a different scale
- **Background differences**: The background behind hero cards differs from the felt
- **Visual effects**: Some clients add effects like glow or shadows to hero cards

Using dedicated templates for hero cards improves recognition accuracy significantly.

## Creating Hero Templates

1. Start a poker game and get dealt cards
2. Take a screenshot when your hole cards are visible
3. Crop each of your two cards carefully
4. Save additional examples of the same cards from different hands
5. Use these real images as templates (or create them programmatically)

You can also use the `create_mock_templates()` function with `for_hero=True`:

```python
from pathlib import Path
from holdem.vision.cards import create_mock_templates

create_mock_templates(Path("assets/hero_templates"), for_hero=True)
```

## Template Naming

Same convention as board templates:
- Format: `{rank}{suit}.png`
- Example: `Ah.png`, `Ks.png`, `7d.png`
- Total: 52 templates (13 ranks × 4 suits)
