# Quick Reference: Runtime Requirements

This is a quick reference guide for the runtime requirements implementation.

## Test Files

| Test File | Purpose | Tests |
|-----------|---------|-------|
| `tests/test_runtime_requirements.py` | **NEW** - Minimal tests for problem statement | 6 tests covering all requirements |
| `tests/test_subgame_street_start.py` | Existing - Street start validation | Extended with sentinel action tests |
| `tests/test_fallback_and_metrics.py` | Existing - Fallback mechanism | Tests fallback scenarios |
| `tests/test_state_debounce.py` | Existing - Debounce functionality | Comprehensive debounce tests |

## Target Thresholds Quick Reference

```python
# Decision Time (ms)
p95 <= 110
p99 <= 160

# Fallback Rate (%)
online <= 5
offline == 0

# Iterations
median >= 600
min = 400

# EV Delta (BBs)
median > 0
CI95 > 0

# KL Divergence
p50 in [0.05, 0.25]

# Translator
illegal_after_roundtrip == 0
oscillation_rate < 0.1

# Vision
debounce_filter_rate >= 50-70
ocr_mae < 0.02

# Abstraction
bucket_pop_std < 2.0
collision_rate < 0.001
```

## Running Tests

```bash
# All runtime requirement tests
pytest tests/test_runtime_requirements.py -v

# Individual tests
pytest tests/test_runtime_requirements.py::test_street_start_invariant -v
pytest tests/test_runtime_requirements.py::test_fallback_to_blueprint -v
pytest tests/test_runtime_requirements.py::test_sentinel_actions_present -v
pytest tests/test_runtime_requirements.py::test_anti_oscillation_min_raise -v
pytest tests/test_runtime_requirements.py::test_debounce_no_resolve_on_noise -v
pytest tests/test_runtime_requirements.py::test_leaf_cache_improves_hit_rate -v

# Related existing tests
pytest tests/test_subgame_street_start.py -v
pytest tests/test_fallback_and_metrics.py -v
pytest tests/test_state_debounce.py -v
```

## Metrics Collection

```python
# From DepthLimitedCFR
metrics = solver.get_metrics()
assert metrics['rt/decision_time_ms'] <= 110  # p95 target
assert metrics['rt/iterations'] >= 600  # median target
assert metrics['rt/failsafe_fallback_rate'] <= 0.05  # 5% target
assert metrics['rt/ev_delta_bbs'] > 0  # positive EV

# From StateDebouncer
stats = debouncer.get_statistics()
assert stats['filter_rate'] >= 0.5  # 50% minimum

# From ActionTranslator
success, ev_distance = translator.round_trip_test(action, pot, stack, constraints)
assert success and ev_distance < 0.001  # <0.1% oscillation
```

## Implementation Locations

| Feature | File | Lines |
|---------|------|-------|
| Street start validation | `src/holdem/rt_resolver/subgame_builder.py` | 83-88 |
| Fallback mechanism | `src/holdem/rt_resolver/depth_limited_cfr.py` | 124-142 |
| Sentinel actions | `src/holdem/rt_resolver/subgame_builder.py` | 218-267 |
| Debounce filter | `src/holdem/realtime/state_debounce.py` | 61-150 |
| Action translation | `src/holdem/abstraction/action_translator.py` | 139-233 |
| Metrics tracking | `src/holdem/rt_resolver/depth_limited_cfr.py` | 330-346 |

## Documentation

- **RUNTIME_CHECKLIST.md**: Comprehensive checklist with Annexe C containing all target thresholds
- **RUNTIME_REQUIREMENTS_SUMMARY.md**: Complete implementation status and next steps
- **PLURIBUS_FEATURE_PARITY.csv**: Feature parity matrix with 18 new runtime entries

## Validation Status

✅ **Complete**
- Target thresholds documented
- Minimal tests implemented
- Feature parity updated
- Metrics naming consistent

⏳ **Pending Validation**
- Measure actual p95/p99 on 5k corpus
- Bootstrap CI95 for EV delta
- AIVAT 6-max round-robin
- Bucket population std measurement

## Commands for Validation

```bash
# Create benchmark corpus
python -m holdem.cli.create_corpus \
  --output runs/corpus/frozen_states_5k.json \
  --count 5000 \
  --diverse-spr

# Benchmark decisions
for mode in tight balanced loose; do
  for budget in 80 100 120; do
    python -m holdem.cli.benchmark_decisions \
      --corpus runs/corpus/frozen_states_5k.json \
      --budget $budget \
      --mode $mode \
      --output runs/bench/runtime_${mode}_${budget}.json
  done
done

# Analyze results
python -m holdem.cli.analyze_benchmarks \
  --results runs/bench/*.json \
  --report runs/bench/summary.json
```

## Next Actions

1. **P0 - Create corpus**: 5k diverse frozen states
2. **P0 - Measure latency**: Validate p95/p99 targets  
3. **P0 - EV validation**: Bootstrap CI95 > 0
4. **P1 - KL tuning**: Per street/position measurements
5. **P1 - AIVAT testing**: 6-max round-robin
6. **P2 - Cache implementation**: LRU with hit_rate stats

---

**See**: `RUNTIME_REQUIREMENTS_SUMMARY.md` for detailed information.
