"""Logging utilities."""

import logging
import sys
import multiprocessing as mp
from pathlib import Path


def _is_main_process() -> bool:
    """Check if we're in the main process (not a spawned child).
    
    Returns:
        True if in main process, False if in a spawned child process
    """
    return mp.current_process().name == 'MainProcess'


def setup_logger(
    name: str = "holdem",
    level: int = logging.INFO,
    log_file: Path = None,
    use_rich: bool = True
) -> logging.Logger:
    """Setup logger with optional file output and rich formatting.
    
    Note: Rich logging is automatically disabled in child processes spawned by
    multiprocessing to avoid terminal/console initialization issues on macOS.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Detect if we're in a spawned child process
    # In child processes, use simple logging to avoid Rich initialization issues
    is_main_process = _is_main_process()
    use_rich = use_rich and is_main_process
    
    # Console handler
    if use_rich:
        try:
            from rich.logging import RichHandler
            console_handler = RichHandler(
                rich_tracebacks=True,
                tracebacks_show_locals=True,
                show_time=True,
                show_path=True
            )
        except (ImportError, RuntimeError):
            # Fall back to simple logging if Rich import fails or has issues
            use_rich = False
    
    if not use_rich:
        console_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
    
    console_handler.setLevel(level)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Default logger instance - lazy initialization to avoid issues in child processes
_default_logger = None


def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance.
    
    This function ensures loggers are properly initialized even in spawned child processes.
    """
    global _default_logger
    
    if name:
        # Get or create named logger
        logger_name = f"holdem.{name}"
        logger = logging.getLogger(logger_name)
        
        # Initialize if it has no handlers
        if not logger.handlers:
            # In child processes, use simple logging
            is_main_process = _is_main_process()
            # setup_logger modifies the logger in-place and also returns it
            logger = setup_logger(logger_name, use_rich=is_main_process)
        
        return logger
    
    # Return default logger
    if _default_logger is None:
        _default_logger = setup_logger()
    
    return _default_logger
