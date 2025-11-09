#!/usr/bin/env python3
"""Validation des buckets créés"""

from pathlib import Path
from holdem.abstraction.bucketing import HandBucketing, generate_random_hands
from holdem.types import Street
from holdem.utils.logging import get_logger
import time

logger = get_logger("validate_buckets")

def validate_buckets(buckets_path: str = "assets/abstraction/buckets.pkl"):
    """Valide le fichier buckets.pkl"""
    
    logger.info(f"Chargement de {buckets_path}...")
    start = time.time()
    
    try:
        bucketing = HandBucketing.load(Path(buckets_path))
        load_time = time.time() - start
        logger.info(f"Chargé avec succès en {load_time:.2f}s")
    except Exception as e:
        logger.error(f"Erreur de chargement: {e}")
        return False
    
    # Vérifier chaque street
    streets = [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER]
    
    for street in streets:
        logger.info(f"\n=== Test {street.name} ===")
        
        # Générer des mains de test
        num_test = 100
        test_hands = generate_random_hands(num_test, street, seed=123)
        
        start = time.time()
        buckets_assigned = []
        
        for hole_cards, board in test_hands:
            try:
                bucket = bucketing.get_bucket(
                    hole_cards=hole_cards,
                    board=board,
                    street=street,
                    pot=100.0,
                    stack=200.0,
                    is_in_position=True
                )
                buckets_assigned.append(bucket)
            except Exception as e:
                logger.error(f"Erreur get_bucket: {e}")
                return False
        
        elapsed = time.time() - start
        avg_time = elapsed / num_test * 1000  # en ms
        
        # Statistiques
        unique_buckets = len(set(buckets_assigned))
        min_bucket = min(buckets_assigned)
        max_bucket = max(buckets_assigned)
        
        logger.info(f"  {num_test} mains testées")
        logger.info(f"  Temps moyen: {avg_time:.2f}ms par main")
        logger.info(f"  Buckets uniques utilisés: {unique_buckets}")
        logger.info(f"  Range buckets: [{min_bucket}, {max_bucket}]")
    
    logger.info("\n✓ Validation réussie!")
    return True

if __name__ == "__main__":
    import sys
    
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/abstraction/buckets.pkl"
    
    if validate_buckets(path):
        sys.exit(0)
    else:
        sys.exit(1)
