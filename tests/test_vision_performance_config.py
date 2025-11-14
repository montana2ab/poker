"""Tests for vision performance configuration."""

import pytest
from pathlib import Path
from holdem.vision.vision_performance_config import (
    VisionPerformanceConfig,
    BoardCacheConfig,
    HeroCacheConfig
)


class TestVisionPerformanceConfig:
    """Tests for VisionPerformanceConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = VisionPerformanceConfig.default()
        
        assert config.enable_caching is True
        assert config.enable_light_parse is True
        assert config.light_parse_interval == 3
        assert config.cache_roi_hash is True
        assert config.downscale_ocr_rois is True
        assert config.max_roi_dimension == 400
        assert config.chat_parse_interval == 3
    
    def test_nested_configs_initialized(self):
        """Test nested configs are initialized."""
        config = VisionPerformanceConfig.default()
        
        assert config.board_cache is not None
        assert isinstance(config.board_cache, BoardCacheConfig)
        assert config.board_cache.enabled is True
        assert config.board_cache.stability_threshold == 2
        
        assert config.hero_cache is not None
        assert isinstance(config.hero_cache, HeroCacheConfig)
        assert config.hero_cache.enabled is True
        assert config.hero_cache.stability_threshold == 2
    
    def test_from_dict(self):
        """Test loading from dictionary."""
        config_dict = {
            "enable_caching": False,
            "enable_light_parse": False,
            "light_parse_interval": 5,
            "cache_roi_hash": False,
            "downscale_ocr_rois": False,
            "max_roi_dimension": 600,
            "chat_parse_interval": 2,
            "board_cache": {
                "enabled": False,
                "stability_threshold": 3
            },
            "hero_cache": {
                "enabled": False,
                "stability_threshold": 4
            }
        }
        
        config = VisionPerformanceConfig.from_dict(config_dict)
        
        assert config.enable_caching is False
        assert config.enable_light_parse is False
        assert config.light_parse_interval == 5
        assert config.cache_roi_hash is False
        assert config.downscale_ocr_rois is False
        assert config.max_roi_dimension == 600
        assert config.chat_parse_interval == 2
        assert config.board_cache.enabled is False
        assert config.board_cache.stability_threshold == 3
        assert config.hero_cache.enabled is False
        assert config.hero_cache.stability_threshold == 4
    
    def test_from_yaml(self, tmp_path):
        """Test loading from YAML file."""
        yaml_content = """
vision_performance:
  enable_caching: true
  enable_light_parse: true
  light_parse_interval: 4
  cache_roi_hash: true
  downscale_ocr_rois: true
  max_roi_dimension: 500
  chat_parse_interval: 5
  board_cache:
    enabled: true
    stability_threshold: 2
  hero_cache:
    enabled: true
    stability_threshold: 3
"""
        yaml_file = tmp_path / "test_config.yaml"
        yaml_file.write_text(yaml_content)
        
        config = VisionPerformanceConfig.from_yaml(yaml_file)
        
        assert config.enable_caching is True
        assert config.enable_light_parse is True
        assert config.light_parse_interval == 4
        assert config.max_roi_dimension == 500
        assert config.chat_parse_interval == 5
        assert config.board_cache.stability_threshold == 2
        assert config.hero_cache.stability_threshold == 3
    
    def test_custom_values(self):
        """Test creating config with custom values."""
        board_config = BoardCacheConfig(enabled=False, stability_threshold=5)
        hero_config = HeroCacheConfig(enabled=False, stability_threshold=6)
        
        config = VisionPerformanceConfig(
            enable_caching=False,
            enable_light_parse=False,
            light_parse_interval=10,
            cache_roi_hash=False,
            downscale_ocr_rois=False,
            max_roi_dimension=800,
            board_cache=board_config,
            hero_cache=hero_config,
            chat_parse_interval=10
        )
        
        assert config.enable_caching is False
        assert config.enable_light_parse is False
        assert config.light_parse_interval == 10
        assert config.cache_roi_hash is False
        assert config.downscale_ocr_rois is False
        assert config.max_roi_dimension == 800
        assert config.chat_parse_interval == 10
        assert config.board_cache.enabled is False
        assert config.board_cache.stability_threshold == 5
        assert config.hero_cache.enabled is False
        assert config.hero_cache.stability_threshold == 6


class TestBoardCacheConfig:
    """Tests for BoardCacheConfig."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = BoardCacheConfig()
        
        assert config.enabled is True
        assert config.stability_threshold == 2
    
    def test_custom_values(self):
        """Test creating config with custom values."""
        config = BoardCacheConfig(enabled=False, stability_threshold=5)
        
        assert config.enabled is False
        assert config.stability_threshold == 5


class TestHeroCacheConfig:
    """Tests for HeroCacheConfig."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = HeroCacheConfig()
        
        assert config.enabled is True
        assert config.stability_threshold == 2
    
    def test_custom_values(self):
        """Test creating config with custom values."""
        config = HeroCacheConfig(enabled=False, stability_threshold=4)
        
        assert config.enabled is False
        assert config.stability_threshold == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
