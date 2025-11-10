# Fix: Automatic Chunk Restart Time Tracking and RAM Clearing

## Problem Statement

The issue was reported in French:
> "il ne prens pas en compte lors du rederamere automatisue le temps deja ecouler et le temps du redemarage automatique et trop rapide du coup la ram na pas le temps de se vider"

Translation:
> "It doesn't take into account during automatic restart the time already elapsed and the automatic restart time is too fast so the RAM doesn't have time to clear"

## Root Causes

### Issue 1: Cumulative Time Not Updated Before Completion Check

**Location:** `src/holdem/mccfr/chunked_coordinator.py`, line 233 (before fix)

**Problem:**
The `_is_training_complete()` method was called immediately after saving a checkpoint, but before updating `solver._cumulative_elapsed_seconds` with the current chunk's elapsed time. This meant:

- For time-budget mode: The completion check would use stale cumulative time
- The check would compare `solver._cumulative_elapsed_seconds` (old value) against `config.time_budget_seconds`
- Training might run longer than intended or stop prematurely

**Example Bug Scenario:**
```python
# Suppose time_budget_seconds = 100
# After chunk 1: cumulative = 60s (saved in checkpoint)
# Chunk 2 runs for 45s (total should be 105s)
# But completion check sees: cumulative = 60s (not updated yet!)
# 60 < 100, so training continues (WRONG - should have stopped)
```

**Fix:**
```python
# Save final checkpoint for this chunk
self._save_chunk_checkpoint(solver, chunk_start_time)

# Update cumulative elapsed time before checking completion
# This ensures the completion check uses the current total elapsed time
chunk_elapsed_seconds = time.time() - chunk_start_time
solver._cumulative_elapsed_seconds += chunk_elapsed_seconds

# NOW check if training is complete
training_complete = self._is_training_complete(solver)
```

### Issue 2: Insufficient Delay Between Chunk Restarts

**Location:** `src/holdem/mccfr/chunked_coordinator.py`, line 247 (before fix)

**Problem:**
The hardcoded 2-second delay (`time.sleep(2)`) was too short for some systems to fully release RAM, especially:
- Systems with slower memory management
- Systems with memory pressure
- Systems with swap enabled
- macOS systems with different memory management strategies

**Fix:**
1. Added configurable parameter: `chunk_restart_delay_seconds` (default: 5.0s)
2. Made it adjustable via CLI: `--chunk-restart-delay <seconds>`
3. Users can now customize based on their system's RAM clearing speed

## Changes Made

### 1. Configuration Type (`src/holdem/types.py`)

Added new parameter to `MCCFRConfig`:
```python
chunk_restart_delay_seconds: float = 5.0  # Delay between chunk restarts to allow RAM to clear (default: 5 seconds)
```

### 2. Chunked Coordinator (`src/holdem/mccfr/chunked_coordinator.py`)

**Before:**
```python
# Save final checkpoint for this chunk
self._save_chunk_checkpoint(solver, chunk_start_time)

# Flush TensorBoard if enabled
if solver.writer:
    logger.info("Flushing TensorBoard logs...")
    solver.writer.flush()
    solver.writer.close()

# Check if training is complete
training_complete = self._is_training_complete(solver)

if training_complete:
    logger.info("Training Complete!")
    logger.info(f"Final iteration: {solver.iteration}")
    break
else:
    logger.info("Chunk Complete - Automatically restarting for next chunk")
    logger.info(f"Progress: iteration {solver.iteration}")
    time.sleep(2)  # Hardcoded 2 seconds
```

**After:**
```python
# Save final checkpoint for this chunk
self._save_chunk_checkpoint(solver, chunk_start_time)

# Update cumulative elapsed time before checking completion
# This ensures the completion check uses the current total elapsed time
chunk_elapsed_seconds = time.time() - chunk_start_time
solver._cumulative_elapsed_seconds += chunk_elapsed_seconds

# Flush TensorBoard if enabled
if solver.writer:
    logger.info("Flushing TensorBoard logs...")
    solver.writer.flush()
    solver.writer.close()

# Check if training is complete
training_complete = self._is_training_complete(solver)

if training_complete:
    logger.info("Training Complete!")
    logger.info(f"Final iteration: {solver.iteration}")
    logger.info(f"Total elapsed time: {solver._cumulative_elapsed_seconds:.1f}s ({solver._cumulative_elapsed_seconds / 3600:.2f} hours)")
    break
else:
    logger.info("Chunk Complete - Automatically restarting for next chunk")
    logger.info(f"Progress: iteration {solver.iteration}")
    logger.info(f"Elapsed time: {solver._cumulative_elapsed_seconds:.1f}s ({solver._cumulative_elapsed_seconds / 3600:.2f} hours)")
    logger.info(f"Waiting {self.config.chunk_restart_delay_seconds:.1f}s before restart to allow RAM to clear...")
    time.sleep(self.config.chunk_restart_delay_seconds)  # Configurable delay
```

### 3. CLI Support (`src/holdem/cli/train_blueprint.py`)

Added argument:
```python
parser.add_argument("--chunk-restart-delay", type=float,
                   help="Delay in seconds between chunk restarts to allow RAM to clear (default: 5.0)")
```

Added to config creation:
```python
if hasattr(args, 'chunk_restart_delay') and args.chunk_restart_delay is not None:
    config_dict['chunk_restart_delay_seconds'] = args.chunk_restart_delay
```

### 4. Documentation Updates

- `AUTOMATIC_CHUNK_RESTART.md`: Added notes about configurable delay
- `CHUNKED_TRAINING.md`: Added examples with `--chunk-restart-delay` parameter

### 5. Test Suite (`tests/test_chunked_restart_fix.py`)

Added comprehensive tests:
- `test_cumulative_time_updated_before_completion_check()`: Validates time tracking fix
- `test_configurable_restart_delay_parameter()`: Tests parameter in config
- `test_restart_delay_used_in_coordinator()`: Verifies coordinator uses the config
- `test_cli_argument_for_restart_delay()`: Tests CLI argument parsing
- `test_iteration_based_completion_unchanged()`: Ensures iteration-based mode still works

## Usage Examples

### Default Behavior (5 second delay)
```bash
python -m holdem.cli.train_blueprint \
  --config configs/smoke_test_30m.yaml \
  --buckets assets/abstraction/buckets_mid_street.pkl \
  --logdir "$RUN" \
  --tensorboard \
  --num-instances 5 \
  --chunked \
  --chunk-minutes 25 \
  --time-budget 28800  # 8 hours
```

### Custom Delay (10 seconds for slower systems)
```bash
python -m holdem.cli.train_blueprint \
  --config configs/smoke_test_30m.yaml \
  --buckets assets/abstraction/buckets_mid_street.pkl \
  --logdir "$RUN" \
  --tensorboard \
  --num-instances 5 \
  --chunked \
  --chunk-minutes 25 \
  --chunk-restart-delay 10.0 \
  --time-budget 28800  # 8 hours
```

### In Python Code
```python
from holdem.types import MCCFRConfig

config = MCCFRConfig(
    time_budget_seconds=8 * 24 * 3600,  # 8 days
    enable_chunked_training=True,
    chunk_size_minutes=60.0,  # 1 hour per chunk
    chunk_restart_delay_seconds=10.0,  # Longer delay for systems with slower RAM cleanup
    discount_mode="dcfr",
    discount_interval=5000,
    exploration_epsilon=0.6,
    enable_pruning=True
)
```

## Impact

### Benefits
1. **Correct Time Budget Enforcement**: Training now stops at the correct time, respecting the configured time budget
2. **Better RAM Management**: Longer, configurable delays allow the OS to fully release memory
3. **System Flexibility**: Users can tune the delay based on their system's characteristics
4. **Better Logging**: Shows total elapsed time during restarts for better progress tracking

### Backward Compatibility
- Default delay increased from 2s to 5s (minimal impact, improves default behavior)
- New parameter is optional with sensible default
- No breaking changes to existing configurations

## Security Analysis

**CodeQL Scan:** ✅ No security issues found

**Manual Review:**
- No user input is directly used without validation
- Time values are floats, properly validated
- No risk of command injection or path traversal
- No sensitive data exposure

## Testing

All changes validated:
- ✅ Python syntax check passed
- ✅ Configuration loading works correctly
- ✅ CLI argument parsing tested
- ✅ Time tracking logic verified through unit tests
- ✅ CodeQL security scan passed
- ✅ No breaking changes to existing tests

## Conclusion

This fix addresses both the time tracking bug and RAM clearing issue, providing a more robust and configurable chunked training experience. Users on systems with slower memory management can now increase the restart delay, while the default 5-second delay should work well for most systems.
