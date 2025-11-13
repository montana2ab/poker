# Fix Summary: Showdown Label Interpretation and Vision Metrics

## Problem Statement

Two critical bugs were identified in the vision system's run_dry_run logs:

### Bug 1: Showdown Labels Treated as Bets
- Lines like "Won 5,249" and "Won 2,467" were being parsed as player names
- These showdown labels (pot win notifications) were creating fake BET events
- This triggered unnecessary real-time searches on the river
- Example from logs:
  ```
  Player 3 name OCR: Won 5,249
  Player 3 bet OCR: 5249.00
  Event: action - Player: Won 5,249 - Action: ActionType.BET - Amount: 5249.0
  [REAL-TIME SEARCH] Street: river ...
  ```

### Bug 2: Vision Metrics Not Being Used
- Mean Confidence always showed 0.00 despite cards being recognized
- Parse latency averaging ~4000ms but no alerts were generated
- Example from logs:
  ```
  CARD RECOGNITION METRICS:
    Total Recognitions: 38
    Mean Confidence: 0.00  ← Should show actual confidence
  
  PERFORMANCE METRICS:
    Mean Parse Latency: ~4011ms  ← Way above thresholds!
    P95 Threshold Met (50.0ms): ✗
    P99 Threshold Met (80.0ms): ✗
  
  ALERTS:
    Total: 0  ← Should have critical alerts!
  ```

## Solution Implementation

### Bug 1: Showdown Label Filtering

#### 1. Added Utility Function (`parse_state.py`)
```python
def is_showdown_won_label(name: str) -> bool:
    """
    Detects if OCR text is a showdown 'Won X,XXX' label.
    Uses regex pattern: ^Won\s+[0-9,.\s]+$
    """
```

**Features:**
- Case-insensitive matching
- Handles various number formats (commas, dots, spaces)
- Comprehensive docstring with examples

#### 2. Filter in Name Parsing (`parse_state.py`)
- Checks parsed names with `is_showdown_won_label()`
- Keeps default player name instead of showdown label
- Logs filtered labels for debugging
- Prevents showdown text from becoming player identity

#### 3. Filter in Bet Parsing (`parse_state.py`)
- Skips recording bets for players with showdown label names
- Prevents "Won 5,249" from creating a bet of 5249.00
- Clear debug logging when bets are skipped

#### 4. Filter in Event Creation (`event_fusion.py`)
- Import utility function with fallback implementation
- Check player names before creating action events
- Filter in three locations:
  - Stack delta events (VISION_STACK source)
  - Fold events (VISION source)
  - Bet/raise/call events (VISION_BET_REGION source)
- Info-level logging when events are skipped

### Bug 2: Vision Metrics Recording

#### 1. Track Confidence in CardRecognizer (`cards.py`)
```python
class CardRecognizer:
    def __init__(self, ...):
        # Track last confidence scores for metrics
        self.last_confidence_scores: List[float] = []
```

**Implementation:**
- Clear confidence list at start of `recognize_cards()`
- Store confidence when card is successfully recognized in `_recognize_template()`
- Confidence available after each recognition batch

#### 2. Record Card Confidence (`parse_state.py`)
```python
# Board cards
if self.vision_metrics:
    confidences = self.card_recognizer.last_confidence_scores
    for i, card in enumerate(cards):
        if card is not None:
            confidence = confidences[i] if i < len(confidences) else 0.0
            self.vision_metrics.record_card_recognition(
                detected_card=str(card),
                confidence=confidence
            )

# Hero cards (similar, with street and seat info)
```

**Features:**
- Retrieves confidence from recognizer's last batch
- Handles missing confidences gracefully (defaults to 0.0)
- Records for both board and hero cards
- Includes optional street and seat position metadata

#### 3. Generate Latency Alerts (`vision_metrics.py`)
```python
def _check_latency_alerts(self):
    """Check parse latency and generate alerts if thresholds are exceeded."""
    # Calculate P95, P99, mean from recent samples
    # Generate CRITICAL alerts for P99 violations
    # Generate WARNING alerts for P95 violations
    # Generate CRITICAL alerts for very high mean latency
```

**Features:**
- Called automatically after each `record_parse_latency()`
- Uses configurable thresholds (P95: 50ms, P99: 80ms)
- Requires minimum samples before alerting (default: 10)
- Three alert types:
  - P99 threshold violation → CRITICAL
  - P95 threshold violation → WARNING  
  - Mean > 2x P99 threshold → CRITICAL
- Alerts include current value and threshold for context

## Testing

### Test Coverage

#### Showdown Label Tests (`test_showdown_label_filtering.py`)
1. `test_detects_won_labels_with_comma` - Basic patterns
2. `test_detects_won_labels_with_spaces` - Extra whitespace
3. `test_detects_won_labels_with_dots` - Decimal points
4. `test_case_insensitive` - Upper/lower case
5. `test_rejects_real_player_names` - Real players
6. `test_rejects_partial_matches` - Partial text
7. `test_handles_none_and_empty` - Edge cases

**Result: 7/7 tests passing ✓**

#### Vision Metrics Tests (`test_vision_metrics_fixes.py`)
1. `test_card_confidence_recording` - Basic recording
2. `test_card_confidence_with_zero_scores` - Zero handling
3. `test_high_latency_generates_alerts` - Alert generation
4. `test_low_latency_no_alerts` - No false alerts
5. `test_latency_threshold_boundary` - Boundary cases
6. `test_metrics_summary_completeness` - Summary fields
7. `test_metrics_report_generation` - Report format

**Result: 7/7 tests passing ✓**

#### Regression Tests
- Existing vision_metrics tests: 22/22 passing ✓
- No functionality broken

**Total: 36 tests passing**

### Verification Results

Manual verification script confirms:

```
✓ Showdown labels correctly detected and filtered
  - "Won 5,249" → True
  - "Won 2,467" → True
  - "Player123" → False

✓ Card confidence properly recorded
  - 5 cards recognized
  - Mean confidence: 0.91 (calculated correctly)

✓ Latency alerts generated
  - 15 samples at ~4000ms
  - 18 alerts: 12 critical, 6 warning
  - Thresholds shown as violated (✗)

✓ Metrics in report
  - Mean Confidence: 0.91 (no longer 0.00)
  - Mean Parse Latency: 4070.0ms (accurate)
  - Recent alerts displayed with levels
```

## Impact

### Before Fix

**Showdown Labels:**
- ❌ "Won 5,249" treated as player name
- ❌ Creates BET 5249.0 event
- ❌ Triggers unnecessary real-time search
- ❌ Pollutes game state tracking

**Vision Metrics:**
- ❌ Mean Confidence always 0.00
- ❌ No alerts despite 4s latency
- ❌ Can't diagnose vision performance issues
- ❌ Metrics report mostly empty

### After Fix

**Showdown Labels:**
- ✅ "Won 5,249" detected and filtered
- ✅ No fake BET events created
- ✅ No unnecessary searches
- ✅ Clean game state tracking
- ✅ Clear logging when labels detected

**Vision Metrics:**
- ✅ Mean Confidence shows real values (e.g., 0.91)
- ✅ Latency alerts generated appropriately
- ✅ Can diagnose slow vision performance
- ✅ Complete metrics report with alerts
- ✅ Threshold status visible (✓/✗)

## Files Changed

### Core Logic
- `src/holdem/vision/parse_state.py` - Utility function, filtering in parsing
- `src/holdem/vision/event_fusion.py` - Filtering in event creation
- `src/holdem/vision/cards.py` - Confidence score tracking
- `src/holdem/vision/vision_metrics.py` - Latency alert generation

### Tests
- `tests/test_showdown_label_filtering.py` - New test suite
- `tests/test_vision_metrics_fixes.py` - New test suite

## Code Quality

- ✅ All tests passing (36 tests)
- ✅ No security issues (CodeQL scan clean)
- ✅ No existing functionality broken
- ✅ Comprehensive documentation
- ✅ Clear logging for debugging
- ✅ Minimal, surgical changes

## Recommendations

### For Production Use

1. **Monitor Alerts**: Check metrics reports regularly for:
   - High latency warnings → investigate vision optimization
   - Low confidence scores → check template quality

2. **Log Analysis**: Search logs for:
   - `[SHOWDOWN]` - Verify labels are being caught
   - `CRITICAL.*latency` - High parse times

3. **Tuning**: If needed, adjust thresholds in `VisionMetricsConfig`:
   ```python
   config = VisionMetricsConfig(
       latency_p95_threshold=100.0,  # More lenient
       latency_p99_threshold=150.0,
   )
   ```

### Future Enhancements

1. **Additional Patterns**: If other showdown text appears (e.g., "Lost X,XXX"), extend regex
2. **Template Quality Alerts**: Alert if confidence consistently low
3. **Adaptive Thresholds**: Auto-adjust based on hardware capabilities
4. **Confidence Histograms**: Track confidence distribution by suit/rank

## Conclusion

Both bugs are now fixed with comprehensive testing and verification:

1. ✅ Showdown labels no longer trigger fake bet events
2. ✅ Vision metrics properly track card confidence and generate latency alerts
3. ✅ All tests passing, no regressions
4. ✅ Clean code with good documentation
5. ✅ No security issues

The system now correctly distinguishes between actual player actions and showdown notifications, and provides actionable metrics for diagnosing vision performance issues.
