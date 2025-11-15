"""Integration test for vision timing profiling system."""

import tempfile
import json
from pathlib import Path

def test_vision_timing_integration():
    """Test that vision timing profiling integrates correctly with parse_state."""
    print("Testing vision timing profiling integration...")
    
    # Import required modules
    from holdem.vision.vision_timing import create_profiler, get_profiler
    
    # Create a temporary directory for logs
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        
        # Create and enable profiler
        profiler = create_profiler(enabled=True, log_dir=log_dir)
        
        # Verify profiler is set globally
        assert get_profiler() is profiler
        print("✓ Profiler created and set globally")
        
        # Create a few dummy timing records
        for i in range(3):
            recorder = profiler.create_recorder()
            
            # Simulate some work with timing blocks
            import time
            with recorder.time_block("ocr_pot"):
                time.sleep(0.001)
            
            with recorder.time_block("ocr_stacks"):
                time.sleep(0.002)
            
            with recorder.time_block("board_vision"):
                time.sleep(0.001)
            
            # Set metadata
            recorder.set_metadata(
                mode="full",
                street="FLOP",
                hero_pos=2,
                button=0,
                num_players=6,
                board_cards=3
            )
            
            # Get and write record
            record = recorder.get_record()
            profiler.write_record(record)
            
            print(f"✓ Created and wrote record {i+1}")
        
        # Close profiler
        profiler.close()
        print("✓ Profiler closed")
        
        # Verify log file was created
        log_files = list(log_dir.glob("vision_timing_*.jsonl"))
        assert len(log_files) == 1, f"Expected 1 log file, found {len(log_files)}"
        log_file = log_files[0]
        print(f"✓ Log file created: {log_file.name}")
        
        # Read and verify log contents
        with open(log_file) as f:
            lines = f.readlines()
        
        # Should have header + 3 records
        assert len(lines) == 4, f"Expected 4 lines, found {len(lines)}"
        print(f"✓ Log file has {len(lines)} lines (header + 3 records)")
        
        # Parse and verify header
        header = json.loads(lines[0])
        assert header['type'] == 'header'
        assert header['format'] == 'JSONL (one JSON object per line)'
        print("✓ Header is valid")
        
        # Parse and verify records
        for i, line in enumerate(lines[1:], start=1):
            record = json.loads(line)
            
            # Check required fields
            assert record['parse_id'] == i
            assert record['mode'] == 'full'
            assert record['street'] == 'FLOP'
            assert record['hero_pos'] == 2
            assert record['button'] == 0
            assert record['num_players'] == 6
            assert record['board_cards'] == 3
            
            # Check timing fields exist and are reasonable
            assert 't_total_parse_ms' in record
            assert record['t_total_parse_ms'] > 0
            assert 't_ocr_pot_ms' in record
            assert record['t_ocr_pot_ms'] >= 0
            assert 't_ocr_stacks_ms' in record
            assert record['t_ocr_stacks_ms'] >= 0
            assert 't_board_vision_ms' in record
            assert record['t_board_vision_ms'] >= 0
            
            print(f"✓ Record {i} is valid (total: {record['t_total_parse_ms']:.2f}ms)")
    
    print("\n✅ All integration tests passed!")
    return True


if __name__ == "__main__":
    try:
        test_vision_timing_integration()
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
