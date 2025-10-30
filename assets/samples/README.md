# Sample Images Directory

This directory should contain sample poker table screenshots for testing the vision system.

Files to include:
- `sample_preflop.png` - Preflop state
- `sample_flop.png` - Flop state with 3 community cards
- `sample_turn.png` - Turn state with 4 community cards
- `sample_river.png` - River state with 5 community cards
- `sample_cards_close.png` - Close-up of cards for recognition testing
- `sample_pot.png` - Close-up of pot display for OCR testing
- `sample_stack.png` - Close-up of stack display for OCR testing

These samples are used by `test_vision_offline.py` to verify:
- Card recognition accuracy ≥ 98%
- OCR number extraction accuracy ≥ 97%
