# Feature Extraction System

This document describes the comprehensive feature extraction system implemented for hand abstraction and bucketing in the Texas Hold'em MCCFR solver.

## Overview

The system uses different feature extraction strategies for preflop and postflop play:

- **Preflop**: 10-dimensional feature vector → 24 buckets
- **Flop**: 34-dimensional feature vector → 80 buckets
- **Turn**: 34-dimensional feature vector → 80 buckets
- **River**: 34-dimensional feature vector → 64 buckets

## Postflop Features (34 dimensions)

The postflop feature vector consists of 4 main blocks:

### 1. Hand Category (12 dimensions, one-hot)

Classifies the current made hand into one of 12 exclusive categories:

1. **High card** - No pair or better
2. **Underpair / 3rd pair or less** - Pocket pair below board's highest card, or paired with 3rd board card or lower
3. **Second pair** - Paired with 2nd highest board card
4. **Top pair** - Paired with highest board card
5. **Overpair** - Pocket pair higher than all board cards
6. **Two pair (board + hand)** - Two pair made with 1 hole card + 1 board card
7. **Two pair (pocket)** - Two pair with both pocket cards
8. **Trips** - Three of a kind (without full house)
9. **Straight** - Five cards in sequence
10. **Flush** - Five cards of same suit
11. **Full house** - Three of a kind plus a pair
12. **Quads or Straight flush** - Four of a kind or straight flush

**Implementation**: Uses `eval7.handtype()` to determine hand strength, then analyzes hole cards vs board to determine specific pair type.

### 2. Flush Draws (4 dimensions, one-hot)

Detects flush draw potential:

1. **FD_none** - No flush draw
2. **FD_backdoor** - Need 2 cards of same suit (3 suited cards total)
3. **FD_direct_non_nut** - 4 suited cards, but missing Ace of that suit
4. **FD_direct_nut** - 4 suited cards including Ace

**Implementation**: Counts suits in board and hole cards, checks for Ace in hole cards for nut designation.

### 3. Straight Draws (5 dimensions)

Detects straight draw potential:

- **4 dimensions (one-hot)** for draw type:
  1. **SD_none** - No straight draw
  2. **SD_gutshot** - Inside straight draw (~4 outs)
  3. **SD_oesd** - Open-ended straight draw (~8 outs)
  4. **SD_double** - Double gutshot or better (>8 outs)

- **1 dimension (binary flag)** for draw quality:
  - **SD_high** - Draw targets high end of board (1 if yes, 0 if no)

**Implementation**: Tests all possible cards to count outs, classifies based on number of outs.

### 4. Combo Draw (1 dimension)

Binary flag indicating both flush and straight draws:
- **1** if has direct flush draw (nut or non-nut) AND straight draw (gutshot/OESD/double)
- **0** otherwise

### 5. Board Texture (6 dimensions, binary flags)

Analyzes community card texture:

1. **board_paired** - Board contains at least one pair
2. **board_trips_or_more** - Board is trips or better (includes two pair)
3. **board_monotone** - At least 3 cards of same suit on board
4. **board_two_suited** - Exactly 2 cards of same suit (not monotone)
5. **board_ace_high** - Highest board card is an Ace
6. **board_low** - All board cards ≤ 9

### 6. Context (6 dimensions)

Situational information:

1. **equity_now** (0-1) - Current hand equity vs opponent range (Monte Carlo estimation)
2. **equity_future_mean** (0-1) - Average equity on next street(s):
   - Flop: average equity over sampled turns
   - Turn: average equity over sampled rivers
   - River: 0 (no future street)
3. **SPR bins** (3 dimensions, one-hot):
   - **spr_low**: SPR < 3
   - **spr_mid**: 3 ≤ SPR ≤ 8
   - **spr_high**: SPR > 8
4. **is_ip** (binary) - 1 if in position, 0 otherwise

**SPR (Stack-to-Pot Ratio)** = `stack / pot`

## Preflop Features (10 dimensions)

Simpler feature set for preflop bucketing:

1. **High card value** (0-1) - Normalized rank of higher card
2. **Low card value** (0-1) - Normalized rank of lower card
3. **Is pair** (binary) - 1 if pocket pair, 0 otherwise
4. **Is suited** (binary) - 1 if both cards same suit, 0 otherwise
5. **Gap** (0-1) - Normalized gap between ranks (0 for pairs, max for A-2)
6. **Is broadway** (binary) - 1 if both cards T or higher, 0 otherwise
7. **Is suited connectors** (binary) - 1 if suited and connected/1-gap, 0 otherwise
8. **Is premium pair** (binary) - 1 if QQ/KK/AA, 0 otherwise
9. **Equity vs random** (0-1) - Approximate equity against random hand
10. **Hand strength score** (0-1) - Composite metric combining multiple factors

## Usage

### Building Buckets

```python
from holdem.types import BucketConfig
from holdem.abstraction.bucketing import HandBucketing

# Create configuration
config = BucketConfig(
    k_preflop=24,
    k_flop=80,
    k_turn=80,
    k_river=64,
    num_samples=500000,  # Number of hands to sample per street
    seed=42
)

# Build buckets
bucketing = HandBucketing(config)
bucketing.build()

# Save for later use
bucketing.save("buckets.pkl")
```

### Getting Bucket Assignment

```python
from holdem.types import Card, Street

# Example hand
hole_cards = [Card('A', 'h'), Card('K', 'h')]
board = [Card('Q', 'h'), Card('J', 's'), Card('9', 'd')]

# Get bucket (with context)
bucket = bucketing.get_bucket(
    hole_cards=hole_cards,
    board=board,
    street=Street.FLOP,
    pot=100.0,
    stack=200.0,
    is_in_position=True
)

print(f"Bucket: {bucket}/80")
```

### Direct Feature Extraction

```python
from holdem.abstraction.postflop_features import extract_postflop_features
from holdem.abstraction.preflop_features import extract_preflop_features

# Postflop features
features = extract_postflop_features(
    hole_cards=hole_cards,
    board=board,
    street=Street.FLOP,
    pot=100.0,
    stack=200.0,
    is_in_position=True,
    num_opponents=1,
    equity_samples=500,
    future_equity_samples=100
)

# Preflop features
preflop_features = extract_preflop_features(
    hole_cards=hole_cards,
    equity_samples=500
)
```

## Implementation Details

### Equity Calculation

Uses `eval7` library for fast hand evaluation:
- Monte Carlo simulation to estimate equity
- Samples opponent hands and remaining board cards
- Configurable number of samples (default: 500 for training, can be adjusted)

### K-means Clustering

- Uses scikit-learn's `KMeans` with `n_init=10`
- Features are normalized and converted to float64
- Separate model trained for each street
- Deterministic with fixed random seed

### Performance Considerations

- **Training**: Building buckets with 500k samples per street takes ~30-60 minutes
- **Inference**: Getting bucket assignment is fast (~1-5ms per hand)
- **Memory**: Fitted models are ~10-50MB depending on configuration

### Testing

Comprehensive test coverage:
- `tests/test_preflop_features.py` - 10 tests for preflop feature extraction
- `tests/test_postflop_features.py` - 24 tests for postflop feature extraction
- `tests/test_bucketing.py` - 3 tests for end-to-end bucketing

Run tests:
```bash
export PYTHONPATH=/path/to/poker/src:$PYTHONPATH
pytest tests/test_*features.py tests/test_bucketing.py -v
```

## Design Rationale

### Why 34 Features?

The 34-dimensional vector balances:
- **Expressiveness**: Captures made hands, draws, texture, and context
- **Efficiency**: Small enough for fast k-means clustering
- **Separability**: Different hand types cluster naturally in this space

### Why Different Bucket Counts?

- **Preflop (24)**: Limited hand space, simpler decisions
- **Flop (80)**: High complexity, many possible textures and draws
- **Turn (80)**: Similar complexity to flop, draws becoming more defined
- **River (64)**: Showdown decisions, reduced need for draw differentiation

### Future Equity

Including future equity (equity on next street) makes the bucketing "potential-aware":
- Two hands with same current equity but different future potential get different features
- Helps distinguish speculative hands (draws) from made hands
- Important for multi-street planning in MCCFR

## References

- `src/holdem/abstraction/postflop_features.py` - Postflop feature extraction
- `src/holdem/abstraction/preflop_features.py` - Preflop feature extraction
- `src/holdem/abstraction/bucketing.py` - Main bucketing implementation
- `src/holdem/abstraction/features.py` - Shared utilities (equity calculation, eval7 integration)
