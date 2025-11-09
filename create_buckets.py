#!/usr/bin/env python3
"""Script simple pour créer buckets.pkl"""

from pathlib import Path
from holdem.types import BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.utils.logging import get_logger

logger = get_logger("create_buckets")

def main():
    # Configuration
    config = BucketConfig(
        k_preflop=24,      # Nombre de buckets preflop
        k_flop=80,         # Nombre de buckets flop
        k_turn=80,         # Nombre de buckets turn
        k_river=64,        # Nombre de buckets river
        num_samples=500000, # Nombre d'échantillons par street
        seed=42            # Seed pour reproductibilité
    )
    
    logger.info("Création des buckets avec la configuration:")
    logger.info(f"  Preflop: {config.k_preflop} buckets")
    logger.info(f"  Flop: {config.k_flop} buckets")
    logger.info(f"  Turn: {config.k_turn} buckets")
    logger.info(f"  River: {config.k_river} buckets")
    logger.info(f"  Échantillons: {config.num_samples} par street")
    
    # Créer l'objet HandBucketing
    bucketing = HandBucketing(config)
    
    # Construire les buckets (cela peut prendre 30-60 minutes)
    logger.info("Construction des buckets en cours...")
    logger.info("Cela peut prendre 30-60 minutes selon votre machine.")
    bucketing.build()
    
    # Sauvegarder
    output_path = Path("assets/abstraction/buckets.pkl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bucketing.save(output_path)
    
    logger.info(f"Buckets sauvegardés dans {output_path}")
    logger.info("Création terminée avec succès!")

if __name__ == "__main__":
    main()
