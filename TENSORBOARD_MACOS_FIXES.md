# TensorBoard Integration and macOS Vision Enhancements

This document describes the fixes implemented to address the issues mentioned in the problem statement.

## Summary

Three main issues were addressed:

1. **TensorBoard Integration**: Added TensorFlow event file generation for training visualization
2. **macOS Vision Improvements**: Enhanced window detection with fallbacks and title normalization
3. **Vision Reference Loading**: Improved loading of reference images and descriptors from file paths

## 1. TensorBoard Integration

### Problem
The Python training script (`holdem-train-blueprint`) did not produce TensorFlow event files for TensorBoard, resulting in "No dashboards are active" messages when running TensorBoard.

### Solution
Added comprehensive TensorBoard logging to the MCCFR solver:

**Modified Files:**
- `src/holdem/mccfr/solver.py`
- `src/holdem/cli/train_blueprint.py`

**Changes:**
- Added optional TensorBoard import with graceful fallback
- Created `SummaryWriter` instance when training with `use_tensorboard=True`
- Log training metrics every 100 iterations:
  - `Training/Utility` - utility value from each iteration
  - `Training/UtilityMovingAvg` - moving average over last 1000 iterations
  - `Training/Iteration` - current iteration number
  - `Training/Epsilon` - exploration epsilon value
  - `Performance/IterationsPerSecond` - training speed
- Event files saved to `{logdir}/tensorboard/`
- Added CLI flags: `--tensorboard` (default) and `--no-tensorboard`

**Usage:**
```bash
# Train with TensorBoard enabled (default)
holdem-train-blueprint --iters 100000 --buckets buckets.pkl --logdir runs/blueprint

# Monitor training in real-time
tensorboard --logdir runs/blueprint/tensorboard

# Train without TensorBoard
holdem-train-blueprint --iters 100000 --buckets buckets.pkl --logdir runs/blueprint --no-tensorboard
```

**Metrics Available:**
- Training progress and convergence
- Utility values and trends
- Performance monitoring (iterations/second)
- Exploration parameters

## 2. macOS Vision Improvements

### Problem
Window detection failed on macOS in several scenarios:
- Window title sometimes empty on macOS
- Quote variants in window titles (e.g., "Hold'em" vs "Hold'em")
- No fallback mechanism when window not found

### Solution
Enhanced window detection with multiple fallback mechanisms and title normalization.

**Modified Files:**
- `src/holdem/vision/screen.py`
- `src/holdem/vision/calibrate.py`
- `src/holdem/cli/run_dry_run.py`
- `src/holdem/cli/run_autoplay.py`

**Changes:**

1. **Title Normalization** (`normalize_title` function):
   - Normalizes Unicode (NFC form)
   - Converts all quote variants to standard apostrophe:
     - `'` (U+2018) - Left single quotation mark
     - `'` (U+2019) - Right single quotation mark
     - `` ` `` - Grave accent
     - `´` (U+00B4) - Acute accent
     - `ʼ` (U+02BC) - Modifier letter apostrophe
   - Converts to lowercase
   - Normalizes whitespace
   
   Example: `"Hold'em"`, `"Hold'em"`, and `"Hold'em"` all normalize to `"hold'em"`

2. **Cascading Fallback Mechanism** (`_find_window_by_title`):
   - **Level 1**: Search by window title (with normalized matching)
   - **Level 2**: Search by owner/application name (e.g., "PokerStars")
   - **Level 3**: Use predefined screen region as fallback
   - **Level 4**: Return None if all methods fail

3. **Enhanced TableProfile**:
   - Added `owner_name` field for application owner fallback
   - Supports both window title and owner name in searches
   - Compatible with existing profiles (owner_name is optional)

**Usage:**
```python
# Profile with owner name fallback
profile = TableProfile()
profile.window_title = "Hold'em Table"  # May have quote variants
profile.owner_name = "PokerStars"       # Fallback to app name
profile.screen_region = (100, 100, 800, 600)  # Ultimate fallback

# Window detection now tries:
# 1. Find window with title containing "hold'em table" (normalized)
# 2. If not found, find window owned by "pokerstars"
# 3. If still not found, use screen_region (100, 100, 800, 600)
```

**Profile JSON Format:**
```json
{
  "window_title": "Texas Hold'em - Table 1",
  "owner_name": "PokerStars",
  "screen_region": [100, 100, 1200, 800],
  ...
}
```

## 3. Vision Reference Loading

### Problem
- Detection code expected ndarray objects but profile JSON contained file paths
- Warning: "No reference image/descriptors in profile"
- Heterogeneous keys (reference_descriptors vs descriptors)
- Relative paths not resolved

### Solution
Integrated path-based reference loading with proper key unification.

**Modified Files:**
- `src/holdem/vision/detect_table.py`
- `src/holdem/vision/calibrate.py`
- `assets/table_profiles/default_profile.json`

**Changes:**

1. **Reference Loading Function** (`_load_refs_from_paths`):
   - Loads reference images from PNG files
   - Loads descriptors from NPY or NPZ files
   - Handles both absolute and relative paths
   - Resolves relative paths using profile directory as base
   - Supports multiple NPZ keys: `"des"`, `"descriptors"`, or first array
   - Graceful error handling with logging

2. **TableDetector Integration**:
   - Calls `_load_refs_from_paths` during initialization
   - Accepts `profile_path` parameter for relative path resolution
   - Computes descriptors from image if only image provided

3. **Unified Profile Keys**:
   - Standardized on `reference_image` and `descriptors`
   - Supports loading from:
     - File paths (string) in JSON
     - Default .npy files alongside profile
     - Already-loaded ndarray objects

**Profile JSON Format:**
```json
{
  "window_title": "Poker Table",
  "reference_image": "assets/ref/table_ref.png",
  "descriptors": "assets/ref/table_ref_orb.npz",
  ...
}
```

**Supported Reference Formats:**

1. **PNG/JPG Images** (reference_image):
   - Absolute path: `/path/to/ref.png`
   - Relative path: `assets/ref/table_ref.png`
   - Default: `{profile_name}_reference.npy`

2. **Descriptors** (descriptors or reference_descriptors):
   - NPY file: `ref_descriptors.npy`
   - NPZ file with key: `ref_descriptors.npz` (keys: "des", "descriptors", or first)
   - Default: `{profile_name}_descriptors.npy`

**Usage:**
```python
from pathlib import Path
from holdem.vision.calibrate import TableProfile
from holdem.vision.detect_table import TableDetector

# Load profile with references from paths
profile_path = Path("assets/table_profiles/my_table.json")
profile = TableProfile.load(profile_path)

# Create detector - automatically loads references
detector = TableDetector(profile, method="orb", profile_path=profile_path)

# References are now loaded as ndarrays
assert isinstance(detector.profile.reference_image, np.ndarray)
assert isinstance(detector.profile.descriptors, np.ndarray)
```

## Testing

### Test Files Created:
1. `tests/test_tensorboard_integration.py` - TensorBoard logging tests
2. `tests/test_macos_vision.py` - Title normalization and window detection tests
3. `tests/test_vision_reference_loading.py` - Reference loading from paths tests

### Test Coverage:
- ✅ TensorBoard event file generation
- ✅ Title normalization with quote variants
- ✅ Window finding with cascading fallbacks
- ✅ Reference image loading from PNG files
- ✅ Descriptor loading from NPY/NPZ files
- ✅ Relative path resolution
- ✅ Profile save/load with new fields

## Backward Compatibility

All changes are backward compatible:

1. **TensorBoard**: Optional dependency, disabled with `--no-tensorboard`
2. **owner_name**: Optional field in profiles, existing profiles still work
3. **Reference paths**: Supports both paths and pre-loaded ndarrays
4. **Default behavior**: Unchanged when new features not used

## macOS Permissions

For macOS users, ensure these permissions are granted:

1. **Screen Recording**: System Preferences → Security & Privacy → Privacy → Screen Recording
2. **Accessibility**: System Preferences → Security & Privacy → Privacy → Accessibility
3. **Automation**: System Preferences → Security & Privacy → Privacy → Automation

## Dependencies

Ensure these packages are installed:
```bash
pip install tensorboard>=2.14.0  # For TensorBoard support
pip install opencv-python>=4.8.0  # For vision features
```

## Example: Complete Workflow

```bash
# 1. Train with TensorBoard
holdem-train-blueprint \
  --iters 100000 \
  --buckets assets/abstraction/buckets.pkl \
  --logdir runs/my_training \
  --tensorboard

# 2. Monitor training in browser
tensorboard --logdir runs/my_training/tensorboard
# Open http://localhost:6006

# 3. Create profile with fallbacks
# Edit assets/table_profiles/pokerstars.json:
# {
#   "window_title": "Texas Hold'em",
#   "owner_name": "PokerStars",
#   "screen_region": [0, 0, 1920, 1080],
#   "reference_image": "assets/ref/pokerstars_table.png",
#   "descriptors": "assets/ref/pokerstars_orb.npz"
# }

# 4. Run with enhanced vision
holdem-dry-run \
  --profile assets/table_profiles/pokerstars.json \
  --policy runs/my_training/avg_policy.json
```

## Troubleshooting

### TensorBoard shows "No dashboards are active"
- Check that `--tensorboard` flag is used (or not disabled with `--no-tensorboard`)
- Verify tensorboard is installed: `pip install tensorboard`
- Ensure logdir path is correct: `tensorboard --logdir runs/blueprint/tensorboard`

### Window not found on macOS
- Check System Preferences permissions (Screen Recording, Accessibility)
- Add `owner_name` to profile as fallback
- Add `screen_region` as ultimate fallback
- Verify window title with: `python -c "from holdem.vision.screen import normalize_title; print(normalize_title('Your Title'))"`

### "No reference image/descriptors in profile"
- Ensure reference files exist at specified paths
- Use absolute paths or paths relative to profile directory
- Check file permissions and formats (PNG for images, NPY/NPZ for descriptors)
- Verify NPZ files contain "des" or "descriptors" key
