# Card Templates Directory

This directory contains template images for card recognition.

Templates are automatically generated using the `create_mock_templates()` function
from `holdem.vision.cards` module.

For production use, replace these with actual high-quality card images extracted
from your poker table screenshots.

Each template should be named: `{rank}{suit}.png`
- Ranks: 2, 3, 4, 5, 6, 7, 8, 9, T, J, Q, K, A
- Suits: h (hearts), d (diamonds), c (clubs), s (spades)

Examples:
- `Ah.png` - Ace of hearts
- `Ts.png` - Ten of spades
- `7d.png` - Seven of diamonds

Total: 52 templates (13 ranks × 4 suits)
