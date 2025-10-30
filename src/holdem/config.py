"""Configuration management."""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from holdem.types import (
    BucketConfig, MCCFRConfig, SearchConfig, 
    VisionConfig, ControlConfig
)


class Config:
    """Central configuration manager."""
    
    def __init__(self):
        self.bucket: BucketConfig = BucketConfig()
        self.mccfr: MCCFRConfig = MCCFRConfig()
        self.search: SearchConfig = SearchConfig()
        self.vision: VisionConfig = VisionConfig()
        self.control: ControlConfig = ControlConfig()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Load config from dictionary."""
        config = cls()
        if "bucket" in data:
            config.bucket = BucketConfig(**data["bucket"])
        if "mccfr" in data:
            config.mccfr = MCCFRConfig(**data["mccfr"])
        if "search" in data:
            config.search = SearchConfig(**data["search"])
        if "vision" in data:
            config.vision = VisionConfig(**data["vision"])
        if "control" in data:
            config.control = ControlConfig(**data["control"])
        return config
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load config from YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    @classmethod
    def from_json(cls, path: Path) -> "Config":
        """Load config from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "bucket": vars(self.bucket),
            "mccfr": vars(self.mccfr),
            "search": vars(self.search),
            "vision": vars(self.vision),
            "control": vars(self.control),
        }
    
    def save_yaml(self, path: Path):
        """Save config to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)
    
    def save_json(self, path: Path):
        """Save config to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


# Default configurations
DEFAULT_BUCKET_CONFIG = BucketConfig()
DEFAULT_MCCFR_CONFIG = MCCFRConfig()
DEFAULT_SEARCH_CONFIG = SearchConfig()
DEFAULT_VISION_CONFIG = VisionConfig()
DEFAULT_CONTROL_CONFIG = ControlConfig()
