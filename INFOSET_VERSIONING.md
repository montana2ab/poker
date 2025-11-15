# Infoset Versioning and Action Sequence Encoding

## Overview

This document describes the implementation of standardized action sequence encoding in infoset strings with versioning support (Issue 2.2).

## Motivation

Previously, infosets used an unversioned format with verbose action histories:
```
FLOP:12:check_call.bet_0.75p.check_call
```

This had several limitations:
1. No versioning system to track format changes
2. Verbose action representation
3. No checkpoint compatibility validation
4. Difficult to distinguish between similar game situations

## Solution

### New Infoset Format (v2)

The new format includes:
1. **Version prefix**: Enables format evolution and validation
2. **Abbreviated actions**: Compact, standardized representation
3. **Position encoding**: Implicit in action sequence order

Format: `v2:STREET:bucket:action_sequence`

Example: `v2:FLOP:12:C-B75-C`

### Action Abbreviations

| Action | Abbreviation | Example |
|--------|-------------|---------|
| Fold | F | `F` |
| Check/Call | C | `C` |
| Bet 33% pot | B33 | `B33` |
| Bet 50% pot | B50 | `B50` |
| Bet 66% pot | B66 | `B66` |
| Bet 75% pot | B75 | `B75` |
| Bet 100% pot | B100 | `B100` |
| Bet 150% pot (1.5x) | B150 | `B150` |
| Bet 200% pot (2x) | B200 | `B200` |
| All-in | A | `A` |

### Street-Based Action History (Pluribus-style)

For enhanced Pluribus parity, actions can be encoded with explicit street separators:

Format: `v2:STREET:bucket:PREFLOP:actions|FLOP:actions|TURN:actions|RIVER:actions`

Example: `v2:TURN:42:PREFLOP:C-B50-C|FLOP:C-B75-C|TURN:B100`

This format provides:
- **Street clarity**: Actions are explicitly tagged by street
- **Better infoset differentiation**: Same action sequence on different streets produces different keys
- **Pluribus alignment**: Matches the action encoding style described in Pluribus paper

## API Reference

### StateEncoder.encode_action_history_by_street()

**NEW**: Converts a dictionary mapping streets to action lists into a compact, street-separated format.

```python
from holdem.abstraction.state_encode import StateEncoder
from holdem.types import Street

encoder = StateEncoder(bucketing)
actions = {
    Street.PREFLOP: ["check_call", "bet_0.5p", "call"],
    Street.FLOP: ["check", "bet_0.75p", "call"],
    Street.TURN: ["bet_1.0p"]
}
encoded = encoder.encode_action_history_by_street(actions)
# Result: "PREFLOP:C-B50-C|FLOP:C-B75-C|TURN:B100"
```

**Parameters:**
- `actions_by_street` (Dict[Street, List[str]]): Dictionary mapping Street enum to action lists

**Returns:**
- str: Street-separated action sequence with format "STREET1:actions|STREET2:actions|..."

**Notes:**
- Streets are always encoded in order: PREFLOP, FLOP, TURN, RIVER
- Empty street action lists are skipped
- Returns empty string if no actions provided

### StateEncoder.encode_action_history()

Converts a list of action strings to abbreviated format.

```python
from holdem.abstraction.state_encode import StateEncoder

encoder = StateEncoder(bucketing)
actions = ["check_call", "bet_0.75p", "check_call"]
encoded = encoder.encode_action_history(actions)
# Result: "C-B75-C"
```

**Parameters:**
- `actions` (List[str]): List of action strings

**Returns:**
- str: Abbreviated action sequence joined with "-"

### StateEncoder.encode_infoset()

Creates a versioned infoset key.

```python
infoset, street = encoder.encode_infoset(
    hole_cards=hole_cards,
    board=board,
    street=Street.FLOP,
    betting_history="C-B75-C",
    use_versioning=True  # Default: True
)
# Result: "v2:FLOP:12:C-B75-C"
```

**Parameters:**
- `hole_cards` (List[Card]): Player's hole cards
- `board` (List[Card]): Community cards
- `street` (Street): Current street
- `betting_history` (str): Encoded betting history
- `pot` (float): Current pot size (default: 100.0)
- `stack` (float): Player's stack (default: 200.0)
- `is_in_position` (bool): Whether player is in position (default: True)
- `use_versioning` (bool): Include version prefix (default: True)

**Returns:**
- Tuple[str, Street]: (infoset_key, street)

### parse_infoset_key()

Parses both versioned and legacy infoset formats.

```python
from holdem.abstraction.state_encode import parse_infoset_key

# New format
street, bucket, history = parse_infoset_key("v2:FLOP:12:C-B75-C")
# Result: ("FLOP", 12, "C-B75-C")

# Legacy format
street, bucket, history = parse_infoset_key("FLOP:12:check_call.bet_0.75p")
# Result: ("FLOP", 12, "check_call.bet_0.75p")
```

**Parameters:**
- `infoset` (str): Infoset string

**Returns:**
- Tuple[str, int, str]: (street_name, bucket, history)

**Raises:**
- ValueError: If infoset format is invalid

### get_infoset_version()

Extracts version from infoset string.

```python
from holdem.abstraction.state_encode import get_infoset_version

version = get_infoset_version("v2:FLOP:12:C-B75-C")
# Result: "v2"

version = get_infoset_version("FLOP:12:check_call")
# Result: None (legacy format)
```

**Parameters:**
- `infoset` (str): Infoset string

**Returns:**
- Optional[str]: Version string or None for legacy format

## Checkpoint Versioning

### Metadata

Checkpoints now include an `infoset_version` field in their metadata:

```json
{
  "iteration": 1000000,
  "infoset_version": "v2",
  "bucket_metadata": {...},
  ...
}
```

### Version Validation

When loading a checkpoint, the system validates version compatibility:

```python
solver.load_checkpoint(checkpoint_path)
```

**Behavior:**
1. **No version (legacy)**: Warns but attempts to load
2. **Matching version**: Loads successfully
3. **Version mismatch**: Raises ValueError with clear error message

**Error Example:**
```
ValueError: Infoset version mismatch!
Current version: v2
Checkpoint version: v1
Cannot safely resume training with incompatible infoset encoding.
Please retrain from scratch with the current version.
```

## Backward Compatibility

The system maintains full backward compatibility:

1. **Parsing**: `parse_infoset_key()` handles both formats
2. **Legacy mode**: Set `use_versioning=False` in `encode_infoset()`
3. **Old checkpoints**: Warns but doesn't block loading (use with caution)

## Migration Guide

### For Existing Codebases

If you have existing code using the old format:

**Option 1: Use new format (recommended)**
```python
# Old code
infoset = encoder.encode_infoset(
    hole_cards, board, street,
    encoder.encode_history(history)
)

# New code
action_sequence = encoder.encode_action_history(history)
infoset = encoder.encode_infoset(
    hole_cards, board, street,
    action_sequence,
    use_versioning=True
)
```

**Option 2: Keep legacy format**
```python
infoset = encoder.encode_infoset(
    hole_cards, board, street,
    encoder.encode_history(history),
    use_versioning=False  # Legacy mode
)
```

### For Existing Checkpoints

**Warning**: Mixing old and new formats will cause issues!

**Options:**
1. **Retrain from scratch** (recommended): Ensures consistent format
2. **Continue with legacy format**: Set `use_versioning=False` everywhere
3. **Accept incompatibility**: Load warning, but regrets/strategies may mismatch

### Using Street-Based Encoding

To use the new street-based encoding in your MCCFR training:

```python
from holdem.types import MCCFRConfig, Street
from holdem.abstraction.state_encode import StateEncoder

# Enable in config (default: True)
config = MCCFRConfig(include_action_history_in_infoset=True)

# When encoding actions, use street-based format
actions_by_street = {
    Street.PREFLOP: ["check_call", "bet_0.5p", "call"],
    Street.FLOP: ["check", "bet_0.75p", "call"]
}

# Encode with street separation
history = encoder.encode_action_history_by_street(actions_by_street)
# Result: "PREFLOP:C-B50-C|FLOP:C-B75-C"

# Use in infoset encoding
infoset, _ = encoder.encode_infoset(
    hole_cards=hole_cards,
    board=board,
    street=current_street,
    betting_history=history
)
```

**Benefits:**
- More accurate game state representation
- Better alignment with Pluribus paper
- Improved infoset differentiation
- Clearer debugging and analysis

## Implementation Details

### Modified Files

1. **src/holdem/types.py**
   - Added `include_action_history_in_infoset` to MCCFRConfig

2. **src/holdem/abstraction/state_encode.py**
   - Added `INFOSET_VERSION` constant
   - Added `encode_action_history()` method
   - **NEW**: Added `encode_action_history_by_street()` method for street-separated encoding
   - Updated `encode_infoset()` with versioning support
   - Updated `parse_infoset_key()` for backward compatibility
   - Added `get_infoset_version()` helper

3. **src/holdem/mccfr/solver.py**
   - Added `infoset_version` to checkpoint metadata
   - Added version validation in `load_checkpoint()`

4. **src/holdem/mccfr/mccfr_os.py**
   - Updated to use `encode_action_history()`
   - Explicitly uses versioned format

5. **src/holdem/mccfr/external_sampling.py**
   - Updated to use `encode_action_history()`
   - Explicitly uses versioned format

6. **src/holdem/realtime/search_controller.py**
   - Updated to use `encode_action_history()`
   - Explicitly uses versioned format

### Testing

Comprehensive test suite in `tests/test_infoset_versioning.py`:
- Action history encoding
- Versioned format creation
- Legacy format parsing
- Version detection
- Edge cases

**NEW**: Street-based encoding tests in `tests/test_street_based_action_encoding.py`:
- Street-separated action encoding
- Multiple street sequences
- Deterministic encoding
- Different sequences produce different keys
- Long sequences handling
- Backward compatibility
- Configuration option validation

Run tests:
```bash
python tests/test_infoset_versioning.py
python tests/test_street_based_action_encoding.py
```

### Demo

Try the interactive demo:
```bash
python demo_infoset_versioning.py
```

## Benefits

1. **Compactness**: "C-B75-C" vs "check_call.bet_0.75p.check_call"
2. **Versioning**: Track format evolution, validate checkpoints
3. **Street Separation** (NEW): "PREFLOP:C-B50-C|FLOP:C-B75-C" provides explicit street boundaries
4. **Pluribus Alignment**: Street-based encoding matches Pluribus paper description
3. **Clarity**: Standardized abbreviations
4. **Safety**: Prevents loading incompatible checkpoints
5. **Flexibility**: Backward compatible, supports both formats

## Future Work

Potential enhancements:
1. **Position encoding**: Add explicit IP/OOP marker if needed
2. **Street transitions**: Encode street changes in history
3. **Migration script**: Auto-convert old checkpoints to v2
4. **Version v3**: Future format improvements

## References

- Issue: 2.2 - ACTION SEQUENCE DANS INFOSETS
- Related: HandHistory class in types.py
- Files: state_encode.py, solver.py, mccfr_os.py, external_sampling.py, search_controller.py
