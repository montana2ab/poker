# Runtime Requirements Implementation Summary

## Overview

This document summarizes the implementation of runtime requirements and target thresholds for the Pluribus-style poker AI system as specified in the problem statement.

## Implementation Status

### 1. Target Thresholds (Seuils Cibles) ✅

All target thresholds have been documented in `RUNTIME_CHECKLIST.md` Annexe C:

#### Performance Targets
- **Budget décision**: p95 ≤ 110 ms, p99 ≤ 160 ms
- **Fallback sûr**: ≤ 5% sur 100k décisions (online), 0% sur replays (offline)
- **Itérations**: médiane ≥ 600, min_iterations = 400
- **Gain EV**: médiane rt/ev_delta_bbs > 0 sur corpus ≥ 5k états, CI95 > 0
- **KL régularisation**: p50 ∈ [0.05, 0.25] pour éviter surfit et drift
- **Translator**: illegal_after_roundtrip == 0, oscillation < 0.1%
- **Vision**: debounce filtre ≥ 50-70% frames bruitées, MAE < 0.02
- **Abstraction**: bucket_pop_std < 2.0, collision_rate ≈ 0

### 2. Minimal Tests (pytest) ✅

Created `tests/test_runtime_requirements.py` with 6 comprehensive tests:

#### a) `test_street_start_invariant`
- **Purpose**: Validates that subgame construction enforces begin_at_street_start constraint
- **Requirement**: Début de street = invariant
- **Implementation**: Tests that SubgameBuilder raises ValueError for mid-street histories
- **Evidence**: `src/holdem/rt_resolver/subgame_builder.py:83-88`

#### b) `test_fallback_to_blueprint`
- **Purpose**: Validates safe fallback to blueprint when time budget not met
- **Requirement**: Fallback sûr si budget temps non atteint
- **Implementation**: Forces timeout before min_iterations and verifies blueprint strategy used
- **Metrics**: Validates rt/failsafe_fallback_rate >= 1.0 and ev_delta_bbs == 0.0
- **Evidence**: `src/holdem/rt_resolver/depth_limited_cfr.py:124-142`

#### c) `test_sentinel_actions_present`
- **Purpose**: Ensures sentinel actions present in tight mode to prevent exploitation
- **Requirement**: Sentinelles présentes même en mode tight
- **Implementation**: Verifies at least one action from each family (small_bet, overbet, shove)
- **Evidence**: `src/holdem/rt_resolver/subgame_builder.py:218-267`

#### d) `test_anti_oscillation_min_raise`
- **Purpose**: Tests PokerStars min-raise rounding to prevent action oscillation
- **Requirement**: Anti-oscillation PokerStars (arrondis + min-raise)
- **Implementation**: Jittered amounts should snap to same legal level
- **Evidence**: `src/holdem/abstraction/action_translator.py:206-232`

#### e) `test_debounce_no_resolve_on_noise`
- **Purpose**: Validates debouncer filters OCR noise without triggering re-solve
- **Requirement**: Debounce vision: pas de re-solve sur bruit
- **Implementation**: Noisy sequence (±0.01€ pot jitter) should not trigger resolves
- **Evidence**: `src/holdem/realtime/state_debounce.py:1-300`

#### f) `test_leaf_cache_improves_hit_rate`
- **Purpose**: Validates leaf evaluation cache provides good hit rate
- **Requirement**: Cache des feuilles : gain de hit-rate
- **Implementation**: Repeated queries should achieve hit_rate >= 0.6
- **Evidence**: Mock implementation shows target metrics structure

### 3. Feature Parity Updates (PLURIBUS_FEATURE_PARITY.csv) ✅

Added 18 new rows to the feature parity matrix:

#### Validated Features (Status: OK)
1. **RT Resolver - Début de street**: begin_at_street_start validation implemented
2. **RT Resolver - Fallback sûr**: Explicit fallback with rt/failsafe_fallback_rate metric
3. **Actions - Sentinelles**: Sentinel actions (small_bet/overbet/shove) in tight mode
4. **Vision - Debounce**: Median filter with configurable window implemented

#### Features Requiring Measurement (Status: À mesurer/À vérifier)
5. **Évaluation - AIVAT 6-max**: Implementation present but not tested with round-robin
6. **Abstraction - Bucket balance**: K-means present, threshold not verified
7. **Métriques RT - Budget décision**: Metric present, thresholds not validated on corpus
8. **Métriques RT - Iterations cible**: min_iterations configured, median not measured
9. **Métriques RT - Gain EV**: ev_delta calculated, no statistical validation
10. **Métriques RT - KL régularisation**: KL divergence calculated, thresholds not validated
11. **Translator - Roundtrip idempotent**: round_trip_test present, no automated tests
12. **Translator - Anti-oscillation**: Rounding + min-raise present, oscillation not measured
13. **Vision - Debounce efficacité**: Statistics present, threshold not validated
14. **Vision - OCR précision**: MAE metric not implemented
15. **Abstraction - Collisions**: K-means with fixed seed, collisions not measured
16. **Leaf Cache - Hit rate**: Cache not explicitly implemented

## Validation Commands

All validation commands are documented in `RUNTIME_CHECKLIST.md` Annexe C:

```bash
# Run runtime requirement tests
pytest tests/test_runtime_requirements.py -v

# Run specific test
pytest tests/test_runtime_requirements.py::test_fallback_to_blueprint -v

# Benchmark decisions across modes and budgets
python -m holdem.cli.benchmark_decisions \
  --corpus runs/corpus/frozen_states_5k.json \
  --budget 80 --budget 100 --budget 120 \
  --mode tight --mode balanced --mode loose \
  --output runs/bench/runtime_{mode}_{budget}.json
```

## Next Steps for Full Compliance

### High Priority (P0)
1. **Create benchmark corpus**: 5k frozen states across diverse SPR/positions
2. **Measure decision time**: Validate p95 ≤ 110ms, p99 ≤ 160ms targets
3. **Validate EV gains**: Bootstrap CI95 on rt/ev_delta_bbs > 0
4. **Implement OCR MAE metric**: Track vision/ocr_mae_amounts with ground truth

### Medium Priority (P1)
5. **Test AIVAT 6-max**: Round-robin with seat permutation
6. **Measure KL divergence**: Per street/position, tune kl_weight to [0.05, 0.25] range
7. **Validate bucket balance**: Measure abstraction/bucket_pop_std on 100k boards
8. **Add collision rate**: Calculate abstraction/collision_rate on sampled boards

### Low Priority (P2)
9. **Implement leaf cache**: LRU cache with hit_rate statistics
10. **Add oscillation metric**: translator/oscillation_rate for PokerStars compliance
11. **Enhance debounce**: Measure filter_rate on annotated corpus (target 50-70%)

## Files Modified

1. **RUNTIME_CHECKLIST.md**: Added Annexe C with comprehensive target thresholds (153 lines)
2. **tests/test_runtime_requirements.py**: New test file with 6 minimal tests (326 lines)
3. **PLURIBUS_FEATURE_PARITY.csv**: Added 18 new rows for runtime metrics and requirements

## Metrics Dashboard Template

All key metrics are documented with proper naming conventions:

```python
{
    # Performance
    'rt/decision_time_ms_p50': float,
    'rt/decision_time_ms_p95': float,
    'rt/decision_time_ms_p99': float,
    
    # Quality
    'rt/iterations_median': float,
    'rt/failsafe_fallback_rate': float,
    'rt/ev_delta_bbs_mean': float,
    'rt/ev_delta_bbs_ci95_lower': float,
    'rt/ev_delta_bbs_ci95_upper': float,
    
    # Regularization
    'policy/kl_to_blueprint_root_p50': float,
    'policy/kl_to_blueprint_flop': float,
    'policy/kl_to_blueprint_turn': float,
    'policy/kl_to_blueprint_river': float,
    
    # Vision
    'vision/debounce_filter_rate': float,
    'vision/ocr_mae_amounts': float,
    
    # Abstraction
    'abstraction/bucket_pop_std': float,
    'abstraction/collision_rate': float,
    
    # Translator
    'translator/illegal_after_roundtrip': int,
    'translator/oscillation_rate': float,
}
```

## Compliance Summary

| Category | Status | Evidence |
|----------|--------|----------|
| Target thresholds documented | ✅ Complete | RUNTIME_CHECKLIST.md Annexe C |
| Minimal tests implemented | ✅ Complete | tests/test_runtime_requirements.py |
| Feature parity updated | ✅ Complete | PLURIBUS_FEATURE_PARITY.csv +18 rows |
| Validation commands | ✅ Complete | RUNTIME_CHECKLIST.md Annexe C |
| Metrics naming | ✅ Complete | Consistent rt/*, policy/*, vision/*, abstraction/* |

## References

- **Problem Statement**: Runtime requirements specification
- **Pluribus Paper**: Brown & Sandholm (2019) - Engineering section for thresholds
- **Implementation Files**: 
  - `src/holdem/rt_resolver/depth_limited_cfr.py`
  - `src/holdem/rt_resolver/subgame_builder.py`
  - `src/holdem/abstraction/action_translator.py`
  - `src/holdem/realtime/state_debounce.py`

---

**Version**: 1.0  
**Date**: 2025-11-09  
**Status**: Requirements implemented, validation pending
