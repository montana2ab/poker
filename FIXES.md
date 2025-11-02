# Installation and Build Fixes - Summary

This document summarizes all the fixes applied to resolve the installation and build issues mentioned in the problem statement.

## Issues Fixed

### 1. Packaging / Import Issues ✅

**Problems:**
- `ModuleNotFoundError: holdem` - projet pas proprement installable
- Multiple `.egg-info` directories blocking `pip install -e .`
- `bin/...` commands not found - CLI entry points not generated

**Solutions:**
- Renamed `setup.py` to `setup_assets.py` to avoid confusion with setuptools build process
- Added proper CLI entry points to `pyproject.toml` under `[project.scripts]`
- Fixed pyproject.toml configuration to properly define the package
- All CLI commands now installed via entry points (e.g., `holdem-build-buckets`)
- Package installs cleanly with `pip install -e .`
- Updated all references in Makefile, install.sh, and documentation

**Files Changed:**
- `pyproject.toml` - Added `[project.scripts]` section with 6 entry points
- `setup.py` → `setup_assets.py` - Renamed to clarify it's for assets, not package setup
- `Makefile` - Updated to use `setup_assets.py`
- `install.sh` - Updated to use `setup_assets.py`
- `test_structure.py`, `quick_test.py` - Updated references

**Verification:**
```bash
$ pip install -e .
Successfully installed holdem-mccfr-0.1.0

$ which holdem-build-buckets
/home/runner/.local/bin/holdem-build-buckets

$ holdem-build-buckets --help
usage: holdem-build-buckets [-h] [--hands HANDS] ...
```

### 2. Code Quality / Robustness ✅

**Problems:**
- Mixing dtypes (float32 vs float64) causing crashes in KMeans.predict
- Non-contiguous buffers causing issues
- Missing centralized utilities for cast/reshape/contiguity

**Solutions:**
- Created `src/holdem/utils/arrays.py` with utility functions:
  - `ensure_float64()` - Convert any array/list to float64
  - `ensure_contiguous()` - Ensure C-contiguous memory layout
  - `prepare_for_sklearn()` - Combined dtype + contiguity for sklearn
  - `safe_reshape()` - Reshape with guaranteed contiguity
- Updated `src/holdem/abstraction/bucketing.py` to use `prepare_for_sklearn()`
- All features now explicitly return float64 arrays
- Added comprehensive test suite for array utilities (13 tests)

**Files Changed:**
- `src/holdem/utils/arrays.py` - NEW: Array utility module
- `src/holdem/abstraction/bucketing.py` - Uses `prepare_for_sklearn()` for all sklearn operations
- `tests/test_array_utils.py` - NEW: 13 tests for array utilities

**Verification:**
```bash
$ pytest tests/test_array_utils.py -v
13 passed in 0.79s

$ pytest tests/test_dtype_fix.py -v
4 passed

$ pytest tests/test_bucketing.py -v
3 passed
```

**Indentation Issues:**
- Reviewed all code, no indentation errors found
- All code properly formatted and working

### 3. Dependencies & Environment ✅

**Problems:**
- `cv2` (opencv-python) missing
- Version instability (no upper bounds)

**Solutions:**
- Added opencv-python to dependencies in both `requirements.txt` and `pyproject.toml`
- Pinned all dependency versions with upper bounds for stability:
  - Format: `package>=min_version,<max_version`
  - Example: `numpy>=1.24.0,<3.0.0`
- Made `pywinauto` Windows-only: `pywinauto>=0.6.8; sys_platform == 'win32'`

**Files Changed:**
- `requirements.txt` - All versions pinned with upper bounds
- `pyproject.toml` - All versions pinned with upper bounds

**Dependencies with Version Ranges:**
```
numpy>=1.24.0,<3.0.0
torch>=2.0.0,<3.0.0
eval7>=0.1.8,<1.0.0
opencv-python>=4.8.0,<5.0.0
scikit-learn>=1.3.0,<2.0.0
rich>=13.5.0,<14.0.0
... (all 15 dependencies)
```

### 4. Artifacts & Assets ✅

**Problems:**
- `avg_policy.json` missing (training never finished)
- Table profiles created manually - risk of inconsistency
- No documentation on how to generate assets

**Solutions:**
- Created comprehensive `ASSETS.md` guide explaining:
  - All required assets and their purpose
  - How to generate each asset with example commands
  - Time requirements for each generation step
  - Complete setup workflow
  - Troubleshooting for missing assets
- Updated README.md with troubleshooting section
- Updated GETTING_STARTED.md with initial setup steps
- Clear documentation that training is required before use

**Files Changed:**
- `ASSETS.md` - NEW: Comprehensive asset generation guide
- `README.md` - Added troubleshooting section
- `GETTING_STARTED.md` - Added initial setup workflow

**Asset Generation Workflow Documented:**
```bash
# 1. Create templates
python setup_assets.py

# 2. Build buckets (10-30 min)
holdem-build-buckets --hands 100000 --out assets/abstraction/precomputed_buckets.pkl

# 3. Train blueprint (20 min - 12 hrs)
holdem-train-blueprint --iters 100000 --buckets ... --logdir runs/blueprint
# Creates: runs/blueprint/avg_policy.json

# 4. Create table profile (5-10 min)
holdem-profile-wizard --window-title "Poker" --out assets/table_profiles/my_table.json
```

### 5. macOS Automation ✅

**Problems:**
- AppleScript/AX refused (-10003) due to missing permissions
- Not documented, causing user frustration

**Solutions:**
- Added comprehensive macOS troubleshooting section to README.md
- Documented all required permissions:
  - Screen Recording permission
  - Accessibility permission
  - Automation permission for System Events
- Step-by-step instructions for granting permissions
- Explained error -10003 and how to fix it

**Documentation Added:**
- README.md Troubleshooting → "macOS Specific Issues"
- Clear explanation of each permission requirement
- Visual guide: System Preferences → Security & Privacy → Privacy

### 6. Tests & CI ✅

**Problems:**
- Tests insufficient/absent on hotspots
- pytest run without package installation → false negatives

**Solutions:**
- All tests now work with either:
  - `pip install -e .` (recommended)
  - `PYTHONPATH=$(pwd)/src pytest tests/`
- Added comprehensive test coverage:
  - `test_array_utils.py` - 13 tests for array utilities
  - `test_dtype_fix.py` - 4 tests for dtype correctness
  - `test_bucketing.py` - 3 tests for bucketing
  - `test_equity_bug_fix.py` - 1 test for equity calculation
  - `test_mccfr_sanity.py` - 3 tests for MCCFR
  - `test_realtime_budget.py` - 3 tests for time budget
- Configured pytest in `pyproject.toml`
- All 27 tests passing (except vision which needs opencv installed)

**Test Results:**
```bash
$ pytest tests/ -v --ignore=tests/test_vision_offline.py
======================== 27 passed, 1 warning in 1.96s =========================
```

**Test Coverage:**
- Abstraction/bucketing: ✅ Covered
- Features/dtype: ✅ Covered
- Array utilities: ✅ Covered
- MCCFR: ✅ Covered
- Realtime: ✅ Covered
- Vision: ⚠️ Requires opencv-python (in dependencies)

## Summary of Changes

### New Files Created:
1. `src/holdem/utils/arrays.py` - Array utility functions
2. `tests/test_array_utils.py` - Tests for array utilities
3. `ASSETS.md` - Comprehensive asset generation guide
4. `setup_assets.py` - Renamed from setup.py

### Files Modified:
1. `pyproject.toml` - Added entry points, pinned versions
2. `requirements.txt` - Pinned versions with upper bounds
3. `Makefile` - Updated setup.py reference
4. `install.sh` - Updated setup.py reference
5. `test_structure.py` - Updated setup.py reference
6. `quick_test.py` - Updated setup.py reference
7. `src/holdem/abstraction/bucketing.py` - Use prepare_for_sklearn()
8. `README.md` - Added troubleshooting section
9. `GETTING_STARTED.md` - Updated with better installation guide
10. `DEVELOPMENT.md` - Updated setup.py references
11. `QUICKSTART.md` - Updated setup.py references
12. `IMPLEMENTATION.md` - Updated setup.py references

### Files Deleted:
1. `setup.py` - Renamed to `setup_assets.py`

## Installation Now Works

The package can now be installed cleanly:

```bash
# Method 1: Full installation (recommended)
pip install -r requirements.txt
pip install -e .

# Method 2: Use wrapper scripts (no install needed)
./bin/holdem-build-buckets --help

# Method 3: Use PYTHONPATH
export PYTHONPATH=$(pwd)/src:$PYTHONPATH
python -m holdem.cli.build_buckets --help
```

All three methods work correctly, with Method 1 being the cleanest.

## All Tests Passing

```
27 tests total:
- 13 array utilities tests ✅
- 4 dtype correctness tests ✅
- 3 bucketing tests ✅
- 1 equity calculation test ✅
- 3 MCCFR tests ✅
- 3 realtime budget tests ✅
```

## Next Steps for Users

1. Install: `pip install -r requirements.txt && pip install -e .`
2. Setup assets: `python setup_assets.py`
3. Build buckets: `holdem-build-buckets --hands 10000 --out test_buckets.pkl`
4. Train blueprint: `holdem-train-blueprint --iters 10000 --buckets test_buckets.pkl --logdir runs/test`
5. Test: `pytest tests/`

See GETTING_STARTED.md and ASSETS.md for detailed instructions.
