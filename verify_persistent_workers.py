#!/usr/bin/env python3
"""
Verification script to check if persistent worker pool changes are in place.
Run this to verify you have the updated code before starting training.
"""

import sys
from pathlib import Path

# Constants
BRANCH_NAME = 'copilot/optimize-training-performance'
UPDATE_INSTRUCTIONS = f"""
You are running the OLD code. Please:
  1. git pull origin {BRANCH_NAME}
  2. pip install -e . --force-reinstall --no-deps
  3. Clear Python cache and restart training
"""

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

print("=" * 70)
print("Verifying Persistent Worker Pool Implementation")
print("=" * 70)
print()

try:
    # Check source code directly (works even without dependencies installed)
    source_file = Path(__file__).parent / 'src' / 'holdem' / 'mccfr' / 'parallel_solver.py'
    
    if not source_file.exists():
        print(f"❌ ERROR: Source file not found: {source_file}")
        sys.exit(1)
    
    with open(source_file, 'r') as f:
        content = f.read()
    
    # Check for persistent_worker_process function
    if 'def persistent_worker_process(' in content:
        print("✓ persistent_worker_process function found in source")
    else:
        print("✗ persistent_worker_process function NOT found in source")
        print(f"\n❌ VERIFICATION FAILED: You are running the OLD code")
        print(UPDATE_INSTRUCTIONS)
        sys.exit(1)
    
    # Check for new methods
    required_methods = ['def _start_worker_pool(', 'def _stop_worker_pool(']
    missing_methods = []
    
    for method in required_methods:
        if method in content:
            method_name = method.replace('def ', '').replace('(', '')
            print(f"✓ {method_name} method found in source")
        else:
            missing_methods.append(method)
            print(f"✗ {method} method NOT found in source")
    
    if missing_methods:
        print(f"\n❌ VERIFICATION FAILED: Missing methods")
        print(UPDATE_INSTRUCTIONS)
        sys.exit(1)
    
    # Check for old worker_process function (should be removed)
    if 'def worker_process(' in content and 'def persistent_worker_process(' in content:
        print("⚠ Warning: Both old and new worker functions found")
    elif 'def worker_process(' in content:
        print("✗ ERROR: Only old worker_process function found!")
        print("\n❌ VERIFICATION FAILED: You are running the OLD code")
        sys.exit(1)
    
    # Check for key log messages
    if 'Worker {worker_id} started and ready for tasks' in content:
        print("✓ New log message found: 'Worker started and ready for tasks'")
    else:
        print("⚠ Warning: Expected log message not found")
    
    if 'Starting worker pool with {self.num_workers} persistent worker(s)' in content:
        print("✓ New log message found: 'Starting worker pool with persistent workers'")
    else:
        print("⚠ Warning: Expected log message not found")
    
    print("\n" + "=" * 70)
    print("✅ VERIFICATION PASSED")
    print("=" * 70)
    print("\nYou have the updated persistent worker pool code!")
    print("\nExpected behavior when training:")
    print("  • Log: 'Starting worker pool with N persistent worker(s)'")
    print("  • Log: 'Worker X started and ready for tasks' (once per worker)")
    print("  • Log: 'Dispatching batch to workers' (for each batch)")
    print("  • NO repeated 'Worker X starting: iterations...' messages")
    print("  • Smooth CPU usage (no sawtooth pattern)")
    print("  • Better performance with multiple workers")
    print()
    
    sys.exit(0)
    
except FileNotFoundError as e:
    print(f"❌ ERROR: File not found: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
