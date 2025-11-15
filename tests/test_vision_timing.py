"""Tests for vision timing profiling system."""

import pytest
import time
import json
import tempfile
from pathlib import Path

from holdem.vision.vision_timing import (
    VisionTimingRecorder,
    VisionTimingLogger,
    VisionTimingProfiler,
    VisionTimingRecord,
    create_profiler,
    get_profiler,
    set_profiler
)


class TestVisionTimingRecorder:
    """Test VisionTimingRecorder."""
    
    def test_recorder_disabled(self):
        """Test that disabled recorder has minimal overhead."""
        recorder = VisionTimingRecorder(enabled=False, parse_id=1)
        
        # Should not record anything
        with recorder.time_block("test_block"):
            time.sleep(0.001)
        
        record = recorder.get_record()
        assert record.parse_id == 1
        assert record.t_total_parse_ms >= 0
        # Individual timings should be 0 when disabled
        assert recorder._timings == {}
    
    def test_recorder_enabled(self):
        """Test that enabled recorder captures timings."""
        recorder = VisionTimingRecorder(enabled=True, parse_id=42)
        
        # Record some timings
        with recorder.time_block("ocr_pot"):
            time.sleep(0.01)  # 10ms
        
        with recorder.time_block("ocr_stacks"):
            time.sleep(0.02)  # 20ms
        
        # Set metadata
        recorder.set_metadata(
            mode="full",
            street="FLOP",
            hero_pos=2,
            button=0,
            num_players=6,
            board_cards=3
        )
        
        record = recorder.get_record()
        
        # Check metadata
        assert record.parse_id == 42
        assert record.mode == "full"
        assert record.street == "FLOP"
        assert record.hero_pos == 2
        assert record.button == 0
        assert record.num_players == 6
        assert record.board_cards == 3
        
        # Check timings (should be roughly correct)
        assert record.t_ocr_pot_ms >= 9.0  # Should be ~10ms
        assert record.t_ocr_pot_ms <= 15.0
        assert record.t_ocr_stacks_ms >= 19.0  # Should be ~20ms
        assert record.t_ocr_stacks_ms <= 25.0
        assert record.t_total_parse_ms > 0
    
    def test_recorder_cache_tracking(self):
        """Test cache hit/miss tracking."""
        recorder = VisionTimingRecorder(enabled=True, parse_id=1)
        
        recorder.record_cache_hit()
        recorder.record_cache_hit()
        recorder.record_cache_miss()
        
        record = recorder.get_record()
        assert record.cache_hits == 2
        assert record.cache_misses == 1
    
    def test_record_to_dict(self):
        """Test converting record to dict for JSON serialization."""
        recorder = VisionTimingRecorder(enabled=True, parse_id=1)
        recorder.set_metadata(mode="light", street="PREFLOP")
        
        with recorder.time_block("test"):
            time.sleep(0.001)
        
        record = recorder.get_record()
        data = record.to_dict()
        
        assert isinstance(data, dict)
        assert data['parse_id'] == 1
        assert data['mode'] == "light"
        assert data['street'] == "PREFLOP"
        assert 'timestamp' in data
        assert 't_total_parse_ms' in data


class TestVisionTimingLogger:
    """Test VisionTimingLogger."""
    
    def test_logger_disabled(self):
        """Test that disabled logger doesn't create files."""
        logger = VisionTimingLogger(enabled=False)
        
        assert logger.log_file is None
        assert logger.log_path is None
        
        # Should be safe to call
        record = VisionTimingRecord(parse_id=1, timestamp="2024-01-01T00:00:00", mode="full")
        logger.write_record(record)
        logger.close()
    
    def test_logger_enabled_writes_jsonl(self):
        """Test that enabled logger writes JSONL correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            
            logger = VisionTimingLogger(
                enabled=True,
                log_dir=log_dir,
                log_filename="test_timing.jsonl"
            )
            
            assert logger.log_file is not None
            assert logger.log_path == log_dir / "test_timing.jsonl"
            
            # Write a record
            record = VisionTimingRecord(
                parse_id=1,
                timestamp="2024-01-01T00:00:00",
                mode="full",
                street="FLOP",
                t_total_parse_ms=123.45
            )
            logger.write_record(record)
            
            # Write another record
            record2 = VisionTimingRecord(
                parse_id=2,
                timestamp="2024-01-01T00:00:01",
                mode="light",
                street="TURN",
                t_total_parse_ms=67.89
            )
            logger.write_record(record2)
            
            logger.close()
            
            # Read back and verify
            with open(logger.log_path) as f:
                lines = f.readlines()
            
            # Should have 3 lines: header + 2 records
            assert len(lines) == 3
            
            # Parse header
            header = json.loads(lines[0])
            assert header['type'] == 'header'
            assert header['format'] == 'JSONL (one JSON object per line)'
            
            # Parse records
            rec1 = json.loads(lines[1])
            assert rec1['parse_id'] == 1
            assert rec1['mode'] == 'full'
            assert rec1['street'] == 'FLOP'
            assert rec1['t_total_parse_ms'] == 123.45
            
            rec2 = json.loads(lines[2])
            assert rec2['parse_id'] == 2
            assert rec2['mode'] == 'light'
            assert rec2['street'] == 'TURN'
            assert rec2['t_total_parse_ms'] == 67.89
    
    def test_logger_context_manager(self):
        """Test logger as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            
            with VisionTimingLogger(enabled=True, log_dir=log_dir, log_filename="ctx.jsonl") as logger:
                record = VisionTimingRecord(parse_id=1, timestamp="2024-01-01T00:00:00", mode="full")
                logger.write_record(record)
            
            # File should be closed and exist
            log_path = log_dir / "ctx.jsonl"
            assert log_path.exists()


class TestVisionTimingProfiler:
    """Test VisionTimingProfiler."""
    
    def test_profiler_disabled(self):
        """Test that disabled profiler works with minimal overhead."""
        profiler = VisionTimingProfiler(enabled=False)
        
        recorder = profiler.create_recorder()
        assert not recorder.enabled
        
        with recorder.time_block("test"):
            time.sleep(0.001)
        
        record = recorder.get_record()
        profiler.write_record(record)
        profiler.close()
    
    def test_profiler_enabled_workflow(self):
        """Test full workflow with enabled profiler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            
            profiler = VisionTimingProfiler(
                enabled=True,
                log_dir=log_dir,
                log_filename="workflow.jsonl"
            )
            
            # Simulate multiple parses
            for i in range(3):
                recorder = profiler.create_recorder()
                
                with recorder.time_block("ocr_pot"):
                    time.sleep(0.001)
                
                recorder.set_metadata(mode="full", street="FLOP")
                record = recorder.get_record()
                profiler.write_record(record)
            
            profiler.close()
            
            # Verify log file
            log_path = log_dir / "workflow.jsonl"
            assert log_path.exists()
            
            with open(log_path) as f:
                lines = f.readlines()
            
            # Should have header + 3 records
            assert len(lines) == 4
            
            # Check parse IDs increment
            for i, line in enumerate(lines[1:], start=1):
                rec = json.loads(line)
                assert rec['parse_id'] == i
    
    def test_profiler_context_manager(self):
        """Test profiler as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            
            with VisionTimingProfiler(enabled=True, log_dir=log_dir, log_filename="ctx.jsonl") as profiler:
                recorder = profiler.create_recorder()
                with recorder.time_block("test"):
                    pass
                record = recorder.get_record()
                profiler.write_record(record)
            
            log_path = log_dir / "ctx.jsonl"
            assert log_path.exists()


class TestGlobalProfiler:
    """Test global profiler management."""
    
    def test_global_profiler_lifecycle(self):
        """Test setting and getting global profiler."""
        # Initially None
        assert get_profiler() is None
        
        # Create and set
        profiler = VisionTimingProfiler(enabled=False)
        set_profiler(profiler)
        
        assert get_profiler() is profiler
        
        # Clear
        set_profiler(None)
        assert get_profiler() is None
    
    def test_create_profiler_sets_global(self):
        """Test that create_profiler sets global instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            
            profiler = create_profiler(enabled=True, log_dir=log_dir)
            
            assert get_profiler() is profiler
            assert profiler.enabled
            
            # Clean up
            profiler.close()
            set_profiler(None)


class TestTimingOverhead:
    """Test that timing system has minimal overhead when disabled."""
    
    def test_disabled_overhead(self):
        """Measure overhead when profiling is disabled."""
        profiler = VisionTimingProfiler(enabled=False)
        
        start = time.perf_counter()
        for _ in range(1000):
            recorder = profiler.create_recorder()
            with recorder.time_block("test"):
                pass
            record = recorder.get_record()
            profiler.write_record(record)
        duration = time.perf_counter() - start
        
        # Should be very fast (< 50ms for 1000 iterations)
        assert duration < 0.05, f"Overhead too high: {duration:.3f}s for 1000 iterations"
    
    def test_enabled_reasonable_overhead(self):
        """Verify that enabled profiling has reasonable overhead."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            
            profiler = VisionTimingProfiler(enabled=True, log_dir=log_dir)
            
            start = time.perf_counter()
            for _ in range(100):
                recorder = profiler.create_recorder()
                with recorder.time_block("test"):
                    time.sleep(0.001)  # Simulate 1ms work
                record = recorder.get_record()
                profiler.write_record(record)
            duration = time.perf_counter() - start
            
            profiler.close()
            
            # With 100x 1ms sleeps, should be ~100ms + overhead
            # Allow generous margin for overhead (should be < 200ms total)
            assert duration < 0.2, f"Overhead too high: {duration:.3f}s for 100 iterations"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
