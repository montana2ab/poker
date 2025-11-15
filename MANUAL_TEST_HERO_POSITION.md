# Manual Test Scenario for Hero Position Optimization

## Purpose
Verify that the fixed hero position feature works correctly with both config and CLI override.

## Prerequisites
- Poker table profile configured: `assets/table_profiles/pokerstars6max.json`
- Policy file available (e.g., from training)
- Bucket file available (optional)

## Test Scenario 1: Using Config Hero Position

### Setup
The `pokerstars6max.json` config has `"hero_position": 2` set.

### Steps
1. Run dry-run mode WITHOUT `--hero-position` flag:
```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/pokerstars6max.json \
  --policy <path-to-policy> \
  --buckets <path-to-buckets>
```

### Expected Results
- Logs should show: `Using fixed hero position: 2 (source: config)`
- Only cards at position 2 should be parsed (hero cards)
- Opponent cards (positions 0, 1, 3, 4, 5) should NOT be parsed
- Board cards should still be parsed
- Game state should be correctly tracked

## Test Scenario 2: Using CLI Override

### Setup
Same config, but override with CLI flag.

### Steps
1. Run dry-run mode WITH `--hero-position 3` flag:
```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/pokerstars6max.json \
  --policy <path-to-policy> \
  --buckets <path-to-buckets> \
  --hero-position 3
```

### Expected Results
- Logs should show: `Using fixed hero position: 3 (source: cli)`
- Only cards at position 3 should be parsed (hero cards)
- Config value (position 2) should be ignored
- Parsed state logs should show `hero_pos=3`
- Board recognition and resolution should remain functional

## Test Scenario 3: No Hero Position (Backward Compatibility)

### Setup
Modify `pokerstars6max.json` to set `"hero_position": null` (or use a profile without this field).

### Steps
1. Run dry-run mode WITHOUT `--hero-position` flag:
```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/pokerstars6max.json \
  --policy <path-to-policy> \
  --buckets <path-to-buckets>
```

### Expected Results
- Logs should show: `No fixed hero position - using automatic detection`
- Existing behavior should be maintained (auto-detection logic)
- All cards may be parsed depending on `parse_opponent_cards` setting
- No errors or regressions

## Test Scenario 4: Auto-play Mode

### Steps
1. Run auto-play mode with hero position override:
```bash
python -m holdem.cli.run_autoplay \
  --profile assets/table_profiles/pokerstars6max.json \
  --policy <path-to-policy> \
  --buckets <path-to-buckets> \
  --hero-position 2 \
  --i-understand-the-tos
```

### Expected Results
- Same as Scenario 2 but with action execution enabled
- Actions should be computed for the correct hero position
- No conflicts with existing auto-play logic

## Validation Points

For each test scenario, verify:

1. **Startup Logs**: Check for the hero position source message
2. **Card Parsing**: Verify only hero cards are parsed when position is fixed
3. **State Parsing**: Confirm `hero_pos=X` in parsed state logs matches expected value
4. **Board Recognition**: Ensure community cards are still recognized correctly
5. **Game Logic**: Verify pot, bets, and player states are tracked correctly
6. **Real-time Search**: If hero cards are present, search should execute normally
7. **Performance**: With fixed position, card parsing should be faster (fewer OCR calls)

## Performance Comparison

To measure the optimization impact:

1. Run without fixed position (auto-detection) for 100 frames
2. Run with fixed position (config or CLI) for 100 frames
3. Compare:
   - Total parse time per frame
   - Number of card recognition calls
   - CPU usage

Expected improvement: 15-30% reduction in parse time when skipping opponent card parsing.

## Notes

- The optimization is most effective when `parse_opponent_cards` is `false` (default)
- Setting `hero_position` does NOT affect board card recognition
- CLI override always takes precedence over config value
- No hero position (null/None) maintains backward compatibility
