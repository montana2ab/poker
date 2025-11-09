#!/usr/bin/env python3
"""Configuration personnalisée pour buckets.pkl"""

from pathlib import Path
from holdem.types import BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.utils.logging import get_logger

logger = get_logger("custom_buckets")

def create_custom_buckets(
    k_preflop: int = 12,
    k_flop: int = 60,
    k_turn: int = 40,
    k_river: int = 24,
    num_samples: int = 100000,
    seed: int = 42,
    output_path: str = "assets/abstraction/buckets.pkl",
    preflop_equity_samples: int = 100
):
    """
    Crée des buckets avec configuration personnalisée.
    
    Args:
        k_preflop: Nombre de buckets preflop (recommandé: 12-24)
        k_flop: Nombre de buckets flop (recommandé: 60-80)
        k_turn: Nombre de buckets turn (recommandé: 40-80)
        k_river: Nombre de buckets river (recommandé: 24-64)
        num_samples: Échantillons par street (100k = rapide, 500k = qualité)
        seed: Seed aléatoire pour reproductibilité
        output_path: Chemin de sortie pour buckets.pkl
        preflop_equity_samples: Échantillons d'équité pour preflop
    """
    
    config = BucketConfig(
        k_preflop=k_preflop,
        k_flop=k_flop,
        k_turn=k_turn,
        k_river=k_river,
        num_samples=num_samples,
        seed=seed
    )
    
    logger.info("Configuration personnalisée:")
    logger.info(f"  Preflop: {k_preflop} buckets")
    logger.info(f"  Flop: {k_flop} buckets")
    logger.info(f"  Turn: {k_turn} buckets")
    logger.info(f"  River: {k_river} buckets")
    logger.info(f"  Échantillons: {num_samples}")
    logger.info(f"  Seed: {seed}")
    logger.info(f"  Equity samples (preflop): {preflop_equity_samples}")
    
    # Créer avec equity_samples personnalisé pour preflop
    bucketing = HandBucketing(config, preflop_equity_samples=preflop_equity_samples)
    
    logger.info("Construction en cours...")
    bucketing.build()
    
    # Sauvegarder
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bucketing.save(path)
    
    logger.info(f"Buckets personnalisés sauvegardés: {path}")
    return bucketing

# Exemples de configurations

def create_fast_buckets():
    """Création rapide pour tests (10-15 minutes)"""
    logger.info("=== Configuration RAPIDE (pour tests) ===")
    return create_custom_buckets(
        k_preflop=12,
        k_flop=60,
        k_turn=40,
        k_river=24,
        num_samples=100000,  # Réduit pour vitesse
        preflop_equity_samples=50,
        output_path="assets/abstraction/buckets_fast.pkl"
    )

def create_balanced_buckets():
    """Configuration équilibrée (30-45 minutes)"""
    logger.info("=== Configuration ÉQUILIBRÉE (recommandée) ===")
    return create_custom_buckets(
        k_preflop=24,
        k_flop=80,
        k_turn=80,
        k_river=64,
        num_samples=300000,
        preflop_equity_samples=100,
        output_path="assets/abstraction/buckets.pkl"
    )

def create_high_quality_buckets():
    """Configuration haute qualité (60-90 minutes)"""
    logger.info("=== Configuration HAUTE QUALITÉ ===")
    return create_custom_buckets(
        k_preflop=24,
        k_flop=80,
        k_turn=80,
        k_river=64,
        num_samples=500000,
        preflop_equity_samples=200,
        output_path="assets/abstraction/buckets_hq.pkl"
    )

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == "fast":
            create_fast_buckets()
        elif mode == "balanced":
            create_balanced_buckets()
        elif mode == "hq":
            create_high_quality_buckets()
        else:
            print(f"Mode inconnu: {mode}")
            print("Modes disponibles: fast, balanced, hq")
            sys.exit(1)
    else:
        print("Usage: python custom_buckets_config.py [fast|balanced|hq]")
        print("  fast     - Création rapide (10-15 min)")
        print("  balanced - Configuration équilibrée (30-45 min)")
        print("  hq       - Haute qualité (60-90 min)")
        sys.exit(1)
