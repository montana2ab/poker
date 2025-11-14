"""Test that CLI files do not have Path import shadowing issues."""

import sys
from pathlib import Path


def test_run_dry_run_no_duplicate_path_import():
    """Test that run_dry_run.py doesn't have duplicate Path imports that cause UnboundLocalError."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    assert dry_run_path.exists(), f"run_dry_run.py not found at {dry_run_path}"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Find all imports of Path
    path_imports = []
    for i, line in enumerate(lines, 1):
        if 'from pathlib import Path' in line and not line.strip().startswith('#'):
            path_imports.append(i)
    
    # Check that Path is imported at the module level
    assert len(path_imports) > 0, "Path should be imported at module level"
    
    # The first import should be near the top (within first 20 lines)
    assert path_imports[0] < 20, f"Path import should be at module level, found at line {path_imports[0]}"
    
    # Check that there are no duplicate imports
    # We allow only one import of Path from pathlib
    assert len(path_imports) == 1, f"Found {len(path_imports)} imports of Path from pathlib at lines {path_imports}. Should only have one at module level."
    
    print(f"✓ run_dry_run.py has exactly one Path import at line {path_imports[0]}")


def test_run_autoplay_no_duplicate_path_import():
    """Test that run_autoplay.py doesn't have duplicate Path imports that cause UnboundLocalError."""
    autoplay_path = Path(__file__).parent.parent / "src/holdem/cli/run_autoplay.py"
    assert autoplay_path.exists(), f"run_autoplay.py not found at {autoplay_path}"
    
    with open(autoplay_path, 'r') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Find all imports of Path
    path_imports = []
    for i, line in enumerate(lines, 1):
        if 'from pathlib import Path' in line and not line.strip().startswith('#'):
            path_imports.append(i)
    
    # Check that Path is imported at the module level
    assert len(path_imports) > 0, "Path should be imported at module level"
    
    # The first import should be near the top (within first 20 lines)
    assert path_imports[0] < 20, f"Path import should be at module level, found at line {path_imports[0]}"
    
    # Check that there are no duplicate imports
    assert len(path_imports) == 1, f"Found {len(path_imports)} imports of Path from pathlib at lines {path_imports}. Should only have one at module level."
    
    print(f"✓ run_autoplay.py has exactly one Path import at line {path_imports[0]}")


def test_run_dry_run_argparse_uses_path():
    """Test that argparse arguments correctly use Path type."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check that argparse arguments use Path type
    assert 'add_argument("--profile", type=Path' in content, "Profile argument should use Path type"
    assert 'add_argument("--policy", type=Path' in content, "Policy argument should use Path type"
    assert 'add_argument("--debug-images", type=Path' in content, "Debug-images argument should use Path type"
    
    print("✓ run_dry_run.py argparse arguments correctly use Path type")


def test_run_dry_run_imports_syntax():
    """Test that run_dry_run.py can be parsed without syntax errors."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    try:
        import ast
        with open(dry_run_path, 'r') as f:
            ast.parse(f.read())
        print("✓ run_dry_run.py has valid Python syntax")
    except SyntaxError as e:
        raise AssertionError(f"run_dry_run.py has syntax error: {e}")


def test_run_autoplay_imports_syntax():
    """Test that run_autoplay.py can be parsed without syntax errors."""
    autoplay_path = Path(__file__).parent.parent / "src/holdem/cli/run_autoplay.py"
    
    try:
        import ast
        with open(autoplay_path, 'r') as f:
            ast.parse(f.read())
        print("✓ run_autoplay.py has valid Python syntax")
    except SyntaxError as e:
        raise AssertionError(f"run_autoplay.py has syntax error: {e}")


if __name__ == "__main__":
    try:
        import pytest
        pytest.main([__file__, "-v"])
    except ImportError:
        # Run tests manually without pytest
        print("Running tests without pytest...")
        
        test_run_dry_run_no_duplicate_path_import()
        test_run_autoplay_no_duplicate_path_import()
        test_run_dry_run_argparse_uses_path()
        test_run_dry_run_imports_syntax()
        test_run_autoplay_imports_syntax()
        
        print("\n✅ All tests passed!")
