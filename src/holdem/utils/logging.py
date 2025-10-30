"""Logging utilities."""

import logging
import sys
from pathlib import Path
from rich.logging import RichHandler
from rich.console import Console


def setup_logger(
    name: str = "holdem",
    level: int = logging.INFO,
    log_file: Path = None,
    use_rich: bool = True
) -> logging.Logger:
    """Setup logger with optional file output and rich formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler
    if use_rich:
        console_handler = RichHandler(
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            show_time=True,
            show_path=True
        )
    else:
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


# Default logger instance
default_logger = setup_logger()


def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance."""
    if name:
        return logging.getLogger(f"holdem.{name}")
    return default_logger
