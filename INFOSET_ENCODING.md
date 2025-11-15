# Infoset Encoding - Complete Reference

## Overview

This document describes how game states are encoded into information sets (infosets) for MCCFR training. The encoding follows the approach described in the Pluribus paper, with enhancements for better state representation.

## What is an Infoset?

An **information set** represents everything a player knows at a given decision point:
- Their own hole cards
- The community cards (board)
- The current street (preflop/flop/turn/river)
- The complete action history up to this point
- Position information (implicitly encoded in action sequence)

Players with identical infosets face the same decision problem and should use the same strategy.

## Infoset Format

### Current Format (v2)

```
v2:STREET:bucket:action_history
```

**Components:**
1. **Version** (`v2`): Format version for compatibility checking
2. **Street** (`PREFLOP`, `FLOP`, `TURN`, `RIVER`): Current game round
3. **Bucket** (integer): Hand strength abstraction bucket
4. **Action history**: Encoded sequence of actions

### Examples

**Simple format (no street separation):**
```
v2:FLOP:12:C-B75-C
```
- Version: v2
- Street: FLOP
- Bucket: 12
- Actions: Check, Bet 75% pot, Call

**Street-separated format (Pluribus-style):**
```
v2:TURN:42:PREFLOP:C-B50-C|FLOP:C-B75-C|TURN:B100
```
- Version: v2
- Street: TURN (current street)
- Bucket: 42
- Actions:
  - PREFLOP: Check, Bet 50% pot, Call
  - FLOP: Check, Bet 75% pot, Call
  - TURN: Bet 100% pot

## Action Encoding

### Abbreviations

Actions are encoded using short abbreviations to keep infoset strings compact:

| Full Action | Encoding | Example |
|-------------|----------|---------|
| Fold | `F` | `F` |
| Check | `C` | `C` |
| Call | `C` | `C` |
| Bet/Raise 25% pot | `B25` | `B25` |
| Bet/Raise 33% pot | `B33` | `B33` |
| Bet/Raise 50% pot | `B50` | `B50` |
| Bet/Raise 66% pot | `B66` | `B66` |
| Bet/Raise 75% pot | `B75` | `B75` |
| Bet/Raise 100% pot | `B100` | `B100` |
| Bet/Raise 150% pot | `B150` | `B150` |
| Bet/Raise 200% pot | `B200` | `B200` |
| All-in | `A` | `A` |

**Notes:**
- Check and Call both use `C` since they're equivalent passive actions
- Bet and Raise use the same encoding (context determines which)
- Percentages are relative to pot size
- All-in uses `A` regardless of amount

### Street Separation

Street-separated encoding provides better game state representation:

```
STREET1:actions|STREET2:actions|STREET3:actions
```

**Benefits:**
1. **Clarity**: Explicitly shows which actions occurred on which street
2. **Differentiation**: Same actions on different streets create different infosets
3. **Pluribus alignment**: Matches the encoding style from the Pluribus paper
4. **Debugging**: Easier to understand and analyze strategies

## Card Abstraction (Bucketing)

Cards are abstracted into buckets using k-means clustering on hand features:

### Bucket Counts (default)
- **Preflop**: 24 buckets (lossless or near-lossless)
- **Flop**: 80 buckets
- **Turn**: 80 buckets  
- **River**: 64 buckets

### Feature Engineering

**Preflop features (10-dimensional):**
- Pair strength
- High card strength
- Suitedness
- Connectivity
- Gap count
- Potential (suited connectors bonus)
- Equity vs random hand
- Position context
- Stack-to-pot ratio (SPR)
- All-in equity

**Postflop features (34-dimensional):**
- Hand categories (high card, pair, two pair, etc.)
- Flush draws (outs, backdoor)
- Straight draws (OESD, gutshot, backdoor)
- Board texture (monotone, paired, connected)
- Equity calculations
- Pot odds
- Position information
- SPR
- And more...

See `FEATURE_EXTRACTION.md` for complete details.

## Position Encoding

Position is **implicitly encoded** in the action sequence:
- The order of actions reveals position
- In heads-up: first to act preflop is OOP (SB), IP postflop (button)
- In multi-way: position relative to button determines action order

No explicit position marker is needed in the infoset string.

## Configuration

### Enabling Street-Based Encoding

```python
from holdem.types import MCCFRConfig

config = MCCFRConfig(
    include_action_history_in_infoset=True  # Default: True
)
```

When enabled, the system can use street-separated action histories for enhanced state representation.

### Using in Code

```python
from holdem.abstraction.state_encode import StateEncoder
from holdem.types import Street

encoder = StateEncoder(bucketing)

# Street-separated encoding (Pluribus-style)
actions_by_street = {
    Street.PREFLOP: ["check_call", "bet_0.5p", "call"],
    Street.FLOP: ["check", "bet_0.75p", "call"],
    Street.TURN: ["bet_1.0p"]
}

history = encoder.encode_action_history_by_street(actions_by_street)
# Result: "PREFLOP:C-B50-C|FLOP:C-B75-C|TURN:B100"

# Create infoset
infoset, _ = encoder.encode_infoset(
    hole_cards=hole_cards,
    board=board,
    street=Street.TURN,
    betting_history=history,
    pot=pot,
    stack=stack,
    is_in_position=is_in_position
)
# Result: "v2:TURN:42:PREFLOP:C-B50-C|FLOP:C-B75-C|TURN:B100"
```

## Parsing Infosets

```python
from holdem.abstraction.state_encode import parse_infoset_key

infoset = "v2:TURN:42:PREFLOP:C-B50-C|FLOP:C-B75-C|TURN:B100"
street_name, bucket, history = parse_infoset_key(infoset)

# street_name: "TURN"
# bucket: 42
# history: "PREFLOP:C-B50-C|FLOP:C-B75-C|TURN:B100"
```

## Versioning

### Version History

- **v1**: Initial format (deprecated)
- **v2**: Current format with abbreviated actions and versioning support

### Version Checking

Checkpoints include infoset version in metadata. When loading:
- **Matching version**: Loads successfully
- **Missing version**: Warning, may be incompatible
- **Version mismatch**: Error, training cannot continue

This prevents accidentally mixing incompatible strategies.

## Comparison with Pluribus

| Feature | Pluribus | Our Implementation | Status |
|---------|----------|-------------------|--------|
| Action abbreviation | ✓ | ✓ | ✅ Complete |
| Street separation | ✓ | ✓ | ✅ Complete |
| Card abstraction | ✓ | ✓ | ✅ Complete |
| Position encoding | Implicit | Implicit | ✅ Complete |
| Versioning | ? | ✓ | ✅ Enhanced |

Our implementation matches Pluribus encoding style with additional versioning for safety.

## Performance Considerations

### Infoset Space Size

The number of possible infosets grows exponentially with:
- Number of betting rounds (streets)
- Action abstraction granularity
- Card abstraction granularity

**Typical sizes:**
- Heads-up No-Limit: 10-100 million infosets
- 6-max No-Limit: 100 million - 1 billion+ infosets

### Memory Optimization

- Use compact string encoding (our abbreviations save ~60% space vs verbose)
- Aggressive card abstraction (buckets reduce card space exponentially)
- Action abstraction (limit bet sizes to ~4-6 per street)
- Pruning (remove rarely-visited infosets below threshold)

## Testing

Comprehensive test coverage ensures encoding correctness:

```bash
# Basic encoding tests
python tests/test_infoset_versioning.py

# Street-based encoding tests
python tests/test_street_based_action_encoding.py
```

## References

- **Pluribus paper**: "Superhuman AI for multiplayer poker" (Brown & Sandholm, 2019)
- **INFOSET_VERSIONING.md**: Implementation details and migration guide
- **FEATURE_EXTRACTION.md**: Hand feature engineering documentation
- **PLURIBUS_FEATURE_PARITY.csv**: Feature comparison with Pluribus
