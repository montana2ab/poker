# Action Abstraction Fix Summary

## Problem Statement
The codebase had several issues with action abstraction:

1. **Incorrect Naming**: `BET_ONE_HALF_POT` was misleading - "one half" means 0.5×, not 1.5×
2. **Position Determination**: Simple odd/even heuristic broke when streets changed (HU position flips postflop)
3. **Betting Semantics**: Bet sizing didn't distinguish between facing check vs facing bet
4. **Action Ordering**: Need canonical order for strategy/regret alignment

## Changes Made

### 1. Action Naming (src/holdem/abstraction/actions.py)
- **Renamed**: `BET_ONE_HALF_POT` → `BET_OVERBET_150`
- **Rationale**: "one half" = 0.5×, but we want 1.5× (150% overbet)
- Added clear documentation of canonical order in docstring

### 2. Betting Semantics (src/holdem/abstraction/actions.py)
Enhanced `abstract_to_concrete()` with proper bet/raise sizing:

```python
# Facing check: bet = round(f * pot)
# Facing bet: raise_to = round(f * (pot + call_amount))
# All-in threshold: if bet >= 97% of remaining stack → ALL-IN
```

This implements the "to-size" convention for raises mentioned in the requirements.

### 3. Position Determination (src/holdem/mccfr/mccfr_os.py)
Fixed `_get_available_actions()` to properly handle HU position:

**Before (broken)**:
```python
in_position = len(history) % 2 == 1  # Same logic for all streets
```

**After (correct)**:
```python
if street == Street.PREFLOP:
    # Preflop: even length -> OOP (SB), odd -> IP (BB)
    in_position = action_count % 2 == 1
else:
    # Postflop: positions flip! even length -> IP (button/SB), odd -> OOP (BB)
    in_position = action_count % 2 == 0
```

This correctly handles the fact that in heads-up poker:
- **Preflop**: SB acts first (OOP), BB second (IP)
- **Postflop**: SB/button has position (IP), BB is OOP

### 4. Executor Update (src/holdem/control/executor.py)
Updated button mapping:
```python
AbstractAction.BET_OVERBET_150: "raise"
```

### 5. Action Ordering
Verified that actions maintain canonical order:
- Bet sizes defined in ascending order: `[0.33, 0.75, 1.0, 1.5]`
- Actions appended in order: `[CHECK_CALL, BET_33, BET_75, BET_100, BET_150, ALL_IN]`
- Consistent across all streets and positions

## Test Coverage

### New Tests Added

#### test_action_abstraction.py
- `test_bet_vs_raise_semantics()`: Verifies bet sizing differs when facing check vs bet
- `test_overbet_sizing()`: Tests 150% overbet in both scenarios
- `test_all_in_threshold()`: Verifies 97% rule works correctly
- `test_action_order_consistency()`: Ensures canonical order maintained
- `test_preflop_action_order()`: Verifies preflop ordering

#### test_position_determination.py (NEW FILE)
Comprehensive position tests:
- `test_preflop_position_determination()`: Verifies preflop position logic
- `test_flop_position_determination()`: Verifies postflop position logic
- `test_turn_position_determination()`: Tests turn actions
- `test_river_position_determination()`: Tests river actions
- `test_position_flips_postflop()`: Key test verifying position flip works

### Updated Tests
All existing tests updated to use `BET_OVERBET_150` instead of `BET_ONE_HALF_POT`.

## Street-Specific Action Menus

As implemented and tested:

- **Preflop**: `{25%, 50%, 100%, 200%}` (unchanged)
- **Flop IP**: `{33%, 75%, 100%, 150%}` 
- **Flop OOP**: `{33%, 75%, 100%}` (no 150% overbet)
- **Turn**: `{66%, 100%, 150%}` (both IP and OOP)
- **River**: `{75%, 100%, 150%, ALL-IN}` (both IP and OOP)

## Files Changed

1. `src/holdem/abstraction/actions.py` - Core action abstraction logic
2. `src/holdem/control/executor.py` - Button mapping
3. `src/holdem/mccfr/mccfr_os.py` - Position determination
4. `tests/test_action_abstraction.py` - Updated and expanded tests
5. `tests/test_position_determination.py` - New comprehensive position tests

## Verification

All changes have been:
- ✅ Syntax checked with `py_compile`
- ✅ Updated consistently across all files
- ✅ Tested with comprehensive unit tests
- ✅ Documented with clear comments

## Impact

These changes ensure:
1. **Correct naming** that reflects actual bet sizes
2. **Proper position handling** in HU poker across all streets
3. **Accurate bet sizing** with proper bet vs raise semantics
4. **Consistent action ordering** for strategy/regret alignment
5. **Same menu everywhere** (MCCFR training, eval, live resolve)

## Notes

The changes maintain backward compatibility with the overall architecture while fixing critical bugs in:
- Position inference that would have caused incorrect strategy construction
- Bet sizing that would have led to suboptimal play
- Action naming that could have caused confusion

All requirements from the problem statement have been addressed.
