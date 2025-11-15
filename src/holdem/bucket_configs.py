"""Predefined bucket configurations for experimentation.

This module provides a factory for creating named bucket configurations
to facilitate experimentation and comparison of different abstraction strategies.
"""

from holdem.types import BucketConfig


class BucketConfigFactory:
    """Factory for creating predefined bucket configurations."""
    
    # Predefined configurations
    CONFIGS = {
        'A': {
            'name': 'config_a',
            'description': 'Base configuration (24/80/80/64)',
            'k_preflop': 24,
            'k_flop': 80,
            'k_turn': 80,
            'k_river': 64,
        },
        'B': {
            'name': 'config_b',
            'description': 'Fine-grained configuration (48/160/160/128)',
            'k_preflop': 48,
            'k_flop': 160,
            'k_turn': 160,
            'k_river': 128,
        },
        'C': {
            'name': 'config_c',
            'description': 'Coarse configuration (12/40/40/32)',
            'k_preflop': 12,
            'k_flop': 40,
            'k_turn': 40,
            'k_river': 32,
        },
    }
    
    @classmethod
    def create(cls, config_name: str, num_samples: int = 500000, seed: int = 42, 
               num_players: int = 2) -> tuple[BucketConfig, dict]:
        """Create a bucket configuration by name.
        
        Args:
            config_name: Name of the configuration ('A', 'B', 'C', etc.)
            num_samples: Number of samples for bucket generation
            seed: Random seed for reproducibility
            num_players: Number of players (2-6)
            
        Returns:
            Tuple of (BucketConfig instance, metadata dict)
            
        Raises:
            ValueError: If config_name is not recognized
        """
        config_name = config_name.upper()
        
        if config_name not in cls.CONFIGS:
            available = ', '.join(cls.CONFIGS.keys())
            raise ValueError(
                f"Unknown configuration: {config_name}. "
                f"Available configurations: {available}"
            )
        
        config_spec = cls.CONFIGS[config_name]
        
        bucket_config = BucketConfig(
            k_preflop=config_spec['k_preflop'],
            k_flop=config_spec['k_flop'],
            k_turn=config_spec['k_turn'],
            k_river=config_spec['k_river'],
            num_samples=num_samples,
            seed=seed,
            num_players=num_players,
        )
        
        metadata = {
            'config_name': config_name,
            'internal_name': config_spec['name'],
            'description': config_spec['description'],
            'spec': f"{config_spec['k_preflop']}/{config_spec['k_flop']}/"
                    f"{config_spec['k_turn']}/{config_spec['k_river']}",
        }
        
        return bucket_config, metadata
    
    @classmethod
    def list_configs(cls) -> list[dict]:
        """List all available configurations.
        
        Returns:
            List of configuration metadata dictionaries
        """
        configs = []
        for name, spec in cls.CONFIGS.items():
            configs.append({
                'name': name,
                'internal_name': spec['name'],
                'description': spec['description'],
                'spec': f"{spec['k_preflop']}/{spec['k_flop']}/{spec['k_turn']}/{spec['k_river']}",
            })
        return configs
    
    @classmethod
    def get_config_spec(cls, config_name: str) -> str:
        """Get the specification string for a configuration.
        
        Args:
            config_name: Name of the configuration ('A', 'B', 'C', etc.)
            
        Returns:
            Specification string like "24/80/80/64"
        """
        config_name = config_name.upper()
        if config_name not in cls.CONFIGS:
            raise ValueError(f"Unknown configuration: {config_name}")
        
        spec = cls.CONFIGS[config_name]
        return f"{spec['k_preflop']}/{spec['k_flop']}/{spec['k_turn']}/{spec['k_river']}"
