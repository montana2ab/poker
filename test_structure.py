#!/usr/bin/env python3
"""
Test script to verify the package works without installing dependencies.
This tests the wrapper scripts and module structure.
"""

import sys
from pathlib import Path
import subprocess

# Add src to path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root / 'src'))

print("=" * 70)
print("Testing Package Structure and Wrapper Scripts")
print("=" * 70)
print()

# Test 1: Basic imports
print("Test 1: Basic module imports")
print("-" * 70)
try:
    import holdem
    print("✓ holdem package imports successfully")
    print(f"  Version: {holdem.__version__}")
except ImportError as e:
    print(f"✗ Failed to import holdem: {e}")
    sys.exit(1)

try:
    from holdem import types
    print("✓ holdem.types imports successfully")
except ImportError as e:
    print(f"✗ Failed to import holdem.types: {e}")

try:
    from holdem import config
    print("✓ holdem.config imports successfully")
except ImportError as e:
    print(f"✗ Failed to import holdem.config: {e}")

print()

# Test 2: Check wrapper scripts exist and are executable
print("Test 2: Wrapper scripts")
print("-" * 70)
bin_dir = repo_root / "bin"
wrapper_scripts = [
    "holdem-build-buckets",
    "holdem-train-blueprint",
    "holdem-eval-blueprint",
    "holdem-profile-wizard",
    "holdem-dry-run",
    "holdem-autoplay",
]

all_scripts_ok = True
for script in wrapper_scripts:
    script_path = bin_dir / script
    if script_path.exists():
        if script_path.stat().st_mode & 0o111:  # Check if executable
            print(f"✓ {script} exists and is executable")
        else:
            print(f"⚠ {script} exists but is not executable")
            all_scripts_ok = False
    else:
        print(f"✗ {script} not found")
        all_scripts_ok = False

print()

# Test 3: Check directory structure
print("Test 3: Directory structure")
print("-" * 70)
required_dirs = [
    "assets/templates",
    "assets/samples",
    "assets/abstraction",
    "assets/table_profiles",
    "runs",
    "bin",
    "src/holdem",
    "src/holdem/cli",
    "src/holdem/vision",
    "src/holdem/abstraction",
    "src/holdem/mccfr",
    "src/holdem/realtime",
    "src/holdem/control",
    "src/holdem/rl_eval",
    "src/holdem/utils",
    "tests",
]

all_dirs_ok = True
for dir_path in required_dirs:
    full_path = repo_root / dir_path
    if full_path.exists():
        print(f"✓ {dir_path}/")
    else:
        print(f"✗ {dir_path}/ not found")
        all_dirs_ok = False

print()

# Test 4: Check important files
print("Test 4: Important files")
print("-" * 70)
required_files = [
    "README.md",
    "QUICKSTART.md",
    "IMPLEMENTATION.md",
    "LICENSE",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "verify_structure.py",
    "install.sh",
    "activate.sh",
    "Makefile",
]

all_files_ok = True
for file_path in required_files:
    full_path = repo_root / file_path
    if full_path.exists():
        print(f"✓ {file_path}")
    else:
        print(f"✗ {file_path} not found")
        all_files_ok = False

print()

# Test 5: Check that wrapper scripts can show help (even without dependencies)
print("Test 5: Wrapper script functionality")
print("-" * 70)
print("Note: Scripts may fail due to missing dependencies (expected)")
print()

# Just test one script to verify the mechanism works
test_script = bin_dir / "holdem-build-buckets"
try:
    result = subprocess.run(
        [str(test_script), "--help"],
        capture_output=True,
        timeout=5
    )
    if result.returncode == 0:
        print("✓ holdem-build-buckets --help works")
    else:
        # Check if it's a dependency error (expected) or structural error
        error_msg = result.stderr.decode()
        if "ModuleNotFoundError" in error_msg or "ImportError" in error_msg:
            print("⚠ holdem-build-buckets fails due to missing dependencies (expected)")
            print("  Install dependencies with: pip install -r requirements.txt")
        else:
            print(f"✗ holdem-build-buckets --help failed: {error_msg[:100]}")
except subprocess.TimeoutExpired:
    print("✗ holdem-build-buckets --help timed out")
except Exception as e:
    print(f"✗ Could not test script: {e}")

print()

# Summary
print("=" * 70)
print("Summary")
print("=" * 70)
if all_scripts_ok and all_dirs_ok and all_files_ok:
    print("✓ Package structure is complete!")
    print()
    print("Next steps:")
    print("  1. Install dependencies: pip install -r requirements.txt")
    print("  2. Use wrapper scripts: ./bin/holdem-build-buckets --help")
    print("  3. Or set PYTHONPATH: export PYTHONPATH=$(pwd)/src:$PYTHONPATH")
    print("  4. Or source activation: source activate.sh")
else:
    print("⚠ Some issues found in package structure")
    if not all_scripts_ok:
        print("  - Check wrapper scripts in bin/")
    if not all_dirs_ok:
        print("  - Run: python setup.py")
    if not all_files_ok:
        print("  - Some required files are missing")

print()
