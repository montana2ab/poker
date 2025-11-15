"""Test that perf_config is defined before use in CLI files."""

from pathlib import Path


def test_perf_config_order_run_dry_run():
    """Test that perf_config is defined before it's used in run_dry_run.py."""
    file_path = Path(__file__).parent / "src/holdem/cli/run_dry_run.py"
    assert file_path.exists(), f"run_dry_run.py not found at {file_path}"
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Find where perf_config is first assigned
    first_assignment = None
    first_usage = None
    
    for i, line in enumerate(lines, 1):
        # Skip comments and empty lines
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        
        # Check for first assignment (perf_config = ...)
        if first_assignment is None and 'perf_config = ' in line:
            first_assignment = i
            print(f"First assignment at line {i}: {line.strip()}")
        
        # Check for first usage (perf_config. or if perf_config)
        if first_usage is None and 'perf_config' in line and 'perf_config =' not in line and 'perf_config_path' not in line:
            first_usage = i
            print(f"First usage at line {i}: {line.strip()}")
    
    assert first_assignment is not None, "perf_config assignment not found"
    assert first_usage is not None, "perf_config usage not found"
    assert first_assignment < first_usage, \
        f"perf_config is used at line {first_usage} before it's assigned at line {first_assignment}"
    
    print(f"✓ run_dry_run.py: perf_config assigned at line {first_assignment}, first used at line {first_usage}")


def test_perf_config_order_run_autoplay():
    """Test that perf_config is defined before it's used in run_autoplay.py."""
    file_path = Path(__file__).parent / "src/holdem/cli/run_autoplay.py"
    assert file_path.exists(), f"run_autoplay.py not found at {file_path}"
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Find where perf_config is first assigned
    first_assignment = None
    first_usage = None
    
    for i, line in enumerate(lines, 1):
        # Skip comments and empty lines
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        
        # Check for first assignment (perf_config = ...)
        if first_assignment is None and 'perf_config = ' in line:
            first_assignment = i
            print(f"First assignment at line {i}: {line.strip()}")
        
        # Check for first usage (perf_config. or if perf_config)
        if first_usage is None and 'perf_config' in line and 'perf_config =' not in line and 'perf_config_path' not in line:
            first_usage = i
            print(f"First usage at line {i}: {line.strip()}")
    
    assert first_assignment is not None, "perf_config assignment not found"
    assert first_usage is not None, "perf_config usage not found"
    assert first_assignment < first_usage, \
        f"perf_config is used at line {first_usage} before it's assigned at line {first_assignment}"
    
    print(f"✓ run_autoplay.py: perf_config assigned at line {first_assignment}, first used at line {first_usage}")


def test_no_duplicate_perf_config_loading():
    """Test that perf_config loading code is not duplicated."""
    for filename in ["run_dry_run.py", "run_autoplay.py"]:
        file_path = Path(__file__).parent / f"src/holdem/cli/{filename}"
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Count occurrences of the loading comment
        count = content.count("# Load vision performance config")
        assert count == 1, f"{filename} has {count} instances of vision performance config loading (expected 1)"
        
        print(f"✓ {filename}: perf_config loading code appears exactly once")


if __name__ == "__main__":
    print("Testing perf_config order in CLI files...\n")
    
    test_perf_config_order_run_dry_run()
    print()
    test_perf_config_order_run_autoplay()
    print()
    test_no_duplicate_perf_config_loading()
    
    print("\n✅ All tests passed!")
