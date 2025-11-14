"""Configuration for vision performance optimizations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class BoardCacheConfig:
    """Configuration for board card caching."""
    enabled: bool = True
    stability_threshold: int = 2


@dataclass
class HeroCacheConfig:
    """Configuration for hero card caching."""
    enabled: bool = True
    stability_threshold: int = 2


@dataclass
class VisionButtonDetectionConfig:
    """Configuration for visual button detection."""
    mode: str = "hybrid"  # "logical_only", "visual_only", "hybrid", "off"
    min_stable_frames: int = 2


@dataclass
class VisionPerformanceConfig:
    """Configuration for vision performance optimizations.
    
    Controls caching, light parsing, and OCR optimizations to reduce
    parse latency from ~4s to <1s.
    """
    # Enable/disable all caching features
    enable_caching: bool = True
    
    # Enable/disable light parse mode
    enable_light_parse: bool = True
    
    # Interval for full parse (1 = every frame, 3 = every 3rd frame)
    light_parse_interval: int = 3
    
    # Enable hash-based ROI caching for OCR
    cache_roi_hash: bool = True
    
    # Enable amount cache (stacks, bets, pot) with image change detection
    # When enabled, OCR is skipped if image hash hasn't changed
    enable_amount_cache: bool = True
    
    # Downscale large ROIs before OCR
    downscale_ocr_rois: bool = True
    
    # Maximum dimension for OCR ROIs
    max_roi_dimension: int = 400
    
    # Board card caching settings
    board_cache: BoardCacheConfig = None
    
    # Hero card caching settings
    hero_cache: HeroCacheConfig = None
    
    # Chat parsing frequency (0 = disable, 1 = every frame, N = every Nth frame)
    chat_parse_interval: int = 3
    
    # Visual button detection settings
    vision_button_detection: VisionButtonDetectionConfig = None
    
    def __post_init__(self):
        """Initialize nested configs if not provided."""
        if self.board_cache is None:
            self.board_cache = BoardCacheConfig()
        if self.hero_cache is None:
            self.hero_cache = HeroCacheConfig()
        if self.vision_button_detection is None:
            self.vision_button_detection = VisionButtonDetectionConfig()
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> "VisionPerformanceConfig":
        """Create config from dictionary.
        
        Args:
            config_dict: Dictionary with configuration values
            
        Returns:
            VisionPerformanceConfig instance
        """
        # Extract nested configs
        board_config = config_dict.get("board_cache", {})
        hero_config = config_dict.get("hero_cache", {})
        button_config = config_dict.get("vision_button_detection", {})
        
        return cls(
            enable_caching=config_dict.get("enable_caching", True),
            enable_light_parse=config_dict.get("enable_light_parse", True),
            light_parse_interval=config_dict.get("light_parse_interval", 3),
            cache_roi_hash=config_dict.get("cache_roi_hash", True),
            enable_amount_cache=config_dict.get("enable_amount_cache", True),
            downscale_ocr_rois=config_dict.get("downscale_ocr_rois", True),
            max_roi_dimension=config_dict.get("max_roi_dimension", 400),
            board_cache=BoardCacheConfig(**board_config) if board_config else BoardCacheConfig(),
            hero_cache=HeroCacheConfig(**hero_config) if hero_config else HeroCacheConfig(),
            chat_parse_interval=config_dict.get("chat_parse_interval", 3),
            vision_button_detection=VisionButtonDetectionConfig(**button_config) if button_config else VisionButtonDetectionConfig()
        )
    
    @classmethod
    def from_yaml(cls, path: Path) -> "VisionPerformanceConfig":
        """Load config from YAML file.
        
        Args:
            path: Path to YAML config file
            
        Returns:
            VisionPerformanceConfig instance
        """
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Extract vision_performance section if it exists
        if "vision_performance" in data:
            data = data["vision_performance"]
        
        return cls.from_dict(data)
    
    @classmethod
    def default(cls) -> "VisionPerformanceConfig":
        """Create default config with all optimizations enabled.
        
        Returns:
            VisionPerformanceConfig with default settings
        """
        return cls()
