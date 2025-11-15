"""Vision timing profiling system for detailed performance analysis.

This module provides a lightweight timing recording system that can be enabled
on-demand to measure detailed timings for all vision parsing steps.

When disabled, the overhead is minimal (just a few boolean checks).
When enabled, it records timing data to JSONL files for analysis.
"""

import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from holdem.utils.logging import get_logger

logger = get_logger("vision.timing")


@dataclass
class VisionTimingRecord:
    """Complete timing record for a single parse operation."""
    parse_id: int
    timestamp: str
    mode: str  # "full" or "light"
    street: Optional[str] = None
    hero_pos: Optional[int] = None
    button: Optional[int] = None
    
    # Total parse time
    t_total_parse_ms: float = 0.0
    
    # Table detection / homography
    t_detect_table_ms: float = 0.0
    
    # OCR timings
    t_ocr_pot_ms: float = 0.0
    t_ocr_stacks_ms: float = 0.0
    t_ocr_bets_ms: float = 0.0
    t_ocr_names_ms: float = 0.0
    
    # Card recognition
    t_hero_cards_ms: float = 0.0
    t_board_vision_ms: float = 0.0
    
    # Chat parsing
    t_chat_ocr_ms: float = 0.0
    t_chat_parse_ms: float = 0.0
    t_chat_validation_ms: float = 0.0
    
    # Event fusion
    t_event_fusion_ms: float = 0.0
    t_chat_enrichment_ms: float = 0.0
    
    # State building
    t_build_parsed_state_ms: float = 0.0
    
    # Cache metrics (optional)
    cache_hits: int = 0
    cache_misses: int = 0
    
    # Additional metadata
    num_players: int = 0
    board_cards: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class VisionTimingRecorder:
    """Records timing data for a single parse operation.
    
    This class is designed to be lightweight when profiling is disabled.
    When enabled, it collects timing data for various subsystems.
    """
    
    def __init__(self, enabled: bool = False, parse_id: int = 0):
        """Initialize timing recorder.
        
        Args:
            enabled: Whether timing recording is enabled
            parse_id: Unique identifier for this parse
        """
        self.enabled = enabled
        self.parse_id = parse_id
        self._timings: Dict[str, float] = {}
        self._start_time = time.perf_counter()
        
        # Metadata
        self._mode = "full"
        self._street = None
        self._hero_pos = None
        self._button = None
        self._num_players = 0
        self._board_cards = 0
        self._cache_hits = 0
        self._cache_misses = 0
    
    def set_metadata(
        self,
        mode: Optional[str] = None,
        street: Optional[str] = None,
        hero_pos: Optional[int] = None,
        button: Optional[int] = None,
        num_players: Optional[int] = None,
        board_cards: Optional[int] = None
    ):
        """Set metadata for this parse."""
        if not self.enabled:
            return
        
        if mode is not None:
            self._mode = mode
        if street is not None:
            self._street = street
        if hero_pos is not None:
            self._hero_pos = hero_pos
        if button is not None:
            self._button = button
        if num_players is not None:
            self._num_players = num_players
        if board_cards is not None:
            self._board_cards = board_cards
    
    def record_cache_hit(self):
        """Record a cache hit."""
        if self.enabled:
            self._cache_hits += 1
    
    def record_cache_miss(self):
        """Record a cache miss."""
        if self.enabled:
            self._cache_misses += 1
    
    def record_timing(self, block_name: str, duration_ms: float):
        """Record timing for a specific block.
        
        Args:
            block_name: Name of the timed block (e.g., "ocr_pot")
            duration_ms: Duration in milliseconds
        """
        if not self.enabled:
            return
        
        self._timings[block_name] = duration_ms
    
    @contextmanager
    def time_block(self, block_name: str):
        """Context manager for timing a block of code.
        
        Usage:
            with recorder.time_block("ocr_pot"):
                pot = ocr_engine.extract_number(pot_region)
        
        Args:
            block_name: Name of the block being timed
        """
        if not self.enabled:
            # When disabled, just yield without timing
            yield
            return
        
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            self.record_timing(block_name, duration_ms)
    
    def get_record(self) -> VisionTimingRecord:
        """Build final timing record.
        
        Returns:
            VisionTimingRecord with all collected timings
        """
        # Calculate total parse time
        total_ms = (time.perf_counter() - self._start_time) * 1000.0
        
        record = VisionTimingRecord(
            parse_id=self.parse_id,
            timestamp=datetime.now().isoformat(),
            mode=self._mode,
            street=self._street,
            hero_pos=self._hero_pos,
            button=self._button,
            t_total_parse_ms=total_ms,
            num_players=self._num_players,
            board_cards=self._board_cards,
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses
        )
        
        # Copy individual timings
        record.t_detect_table_ms = self._timings.get("detect_table", 0.0)
        record.t_ocr_pot_ms = self._timings.get("ocr_pot", 0.0)
        record.t_ocr_stacks_ms = self._timings.get("ocr_stacks", 0.0)
        record.t_ocr_bets_ms = self._timings.get("ocr_bets", 0.0)
        record.t_ocr_names_ms = self._timings.get("ocr_names", 0.0)
        record.t_hero_cards_ms = self._timings.get("hero_cards", 0.0)
        record.t_board_vision_ms = self._timings.get("board_vision", 0.0)
        record.t_chat_ocr_ms = self._timings.get("chat_ocr", 0.0)
        record.t_chat_parse_ms = self._timings.get("chat_parse", 0.0)
        record.t_chat_validation_ms = self._timings.get("chat_validation", 0.0)
        record.t_event_fusion_ms = self._timings.get("event_fusion", 0.0)
        record.t_chat_enrichment_ms = self._timings.get("chat_enrichment", 0.0)
        record.t_build_parsed_state_ms = self._timings.get("build_parsed_state", 0.0)
        
        return record


class VisionTimingLogger:
    """Writes vision timing records to JSONL files.
    
    This class manages the log file lifecycle and ensures thread-safe
    writes to the timing log.
    """
    
    def __init__(
        self,
        enabled: bool = False,
        log_dir: Optional[Path] = None,
        log_filename: Optional[str] = None
    ):
        """Initialize timing logger.
        
        Args:
            enabled: Whether logging is enabled
            log_dir: Directory for log files (default: logs/vision_timing)
            log_filename: Optional custom filename (default: vision_timing_{timestamp}.jsonl)
        """
        self.enabled = enabled
        
        if not enabled:
            self.log_file = None
            self.log_path = None
            return
        
        # Set up log directory
        if log_dir is None:
            log_dir = Path("logs/vision_timing")
        else:
            log_dir = Path(log_dir)
        
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create log file
        if log_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"vision_timing_{timestamp}.jsonl"
        
        self.log_path = log_dir / log_filename
        
        try:
            self.log_file = open(self.log_path, 'w')
            logger.info(f"[TIMING] Opened detailed timing log: {self.log_path}")
            
            # Write header comment
            header = {
                "type": "header",
                "timestamp": datetime.now().isoformat(),
                "description": "Vision timing profiling log",
                "format": "JSONL (one JSON object per line)"
            }
            self.log_file.write(json.dumps(header) + '\n')
            self.log_file.flush()
            
        except Exception as e:
            logger.error(f"[TIMING] Failed to open log file {self.log_path}: {e}")
            self.enabled = False
            self.log_file = None
    
    def write_record(self, record: VisionTimingRecord):
        """Write a timing record to the log file.
        
        Args:
            record: Timing record to write
        """
        if not self.enabled or self.log_file is None:
            return
        
        try:
            line = json.dumps(record.to_dict())
            self.log_file.write(line + '\n')
            self.log_file.flush()
        except Exception as e:
            logger.error(f"[TIMING] Failed to write record: {e}")
    
    def close(self):
        """Close the log file."""
        if self.log_file is not None:
            try:
                self.log_file.close()
                logger.info(f"[TIMING] Closed timing log: {self.log_path}")
            except Exception as e:
                logger.error(f"[TIMING] Error closing log file: {e}")
            finally:
                self.log_file = None
    
    def __del__(self):
        """Ensure file is closed on deletion."""
        self.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class VisionTimingProfiler:
    """Main interface for vision timing profiling.
    
    This class coordinates the recorder and logger, providing a simple
    interface for the rest of the codebase.
    """
    
    def __init__(
        self,
        enabled: bool = False,
        log_dir: Optional[Path] = None,
        log_filename: Optional[str] = None
    ):
        """Initialize profiler.
        
        Args:
            enabled: Whether profiling is enabled
            log_dir: Directory for log files
            log_filename: Optional custom filename
        """
        self.enabled = enabled
        self.logger = VisionTimingLogger(enabled, log_dir, log_filename)
        self._parse_counter = 0
    
    def create_recorder(self) -> VisionTimingRecorder:
        """Create a new timing recorder for a parse operation.
        
        Returns:
            VisionTimingRecorder instance
        """
        self._parse_counter += 1
        return VisionTimingRecorder(enabled=self.enabled, parse_id=self._parse_counter)
    
    def write_record(self, record: VisionTimingRecord):
        """Write a timing record to the log.
        
        Args:
            record: Timing record to write
        """
        self.logger.write_record(record)
    
    def close(self):
        """Close the profiler and log file."""
        self.logger.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global profiler instance (can be set by CLI)
_global_profiler: Optional[VisionTimingProfiler] = None


def get_profiler() -> Optional[VisionTimingProfiler]:
    """Get the global profiler instance.
    
    Returns:
        Global profiler or None if not initialized
    """
    return _global_profiler


def set_profiler(profiler: Optional[VisionTimingProfiler]):
    """Set the global profiler instance.
    
    Args:
        profiler: Profiler instance or None to disable
    """
    global _global_profiler
    _global_profiler = profiler


def create_profiler(
    enabled: bool = False,
    log_dir: Optional[Path] = None,
    log_filename: Optional[str] = None
) -> VisionTimingProfiler:
    """Create and set a new global profiler.
    
    Args:
        enabled: Whether profiling is enabled
        log_dir: Directory for log files
        log_filename: Optional custom filename
    
    Returns:
        Created profiler instance
    """
    profiler = VisionTimingProfiler(enabled, log_dir, log_filename)
    set_profiler(profiler)
    return profiler
