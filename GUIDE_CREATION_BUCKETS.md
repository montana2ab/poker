# Guide de Création des Buckets (buckets.pkl)

Ce guide détaillé explique comment créer un fichier `buckets.pkl` pour l'abstraction de mains dans le système d'IA de poker Texas Hold'em basé sur MCCFR.

## Table des Matières

1. [Introduction](#introduction)
2. [Qu'est-ce qu'un bucket ?](#quest-ce-quun-bucket)
3. [Architecture du Système](#architecture-du-système)
4. [Fonctions Implémentées](#fonctions-implémentées)
5. [Création de buckets.pkl - Méthode Simple](#création-de-bucketspkl---méthode-simple)
6. [Création de buckets.pkl - Méthode Avancée](#création-de-bucketspkl---méthode-avancée)
7. [Options de Configuration](#options-de-configuration)
8. [Validation et Tests](#validation-et-tests)
9. [Dépannage](#dépannage)

---

## Introduction

Le système de **bucketing** (regroupement en buckets) est une technique d'abstraction utilisée pour réduire l'espace des états dans les jeux de poker. Au lieu de traiter chaque main de manière unique, les mains similaires sont regroupées dans des "buckets" (seaux/groupes), ce qui permet à l'algorithme MCCFR de fonctionner efficacement.

Le fichier `buckets.pkl` contient les modèles de clustering K-means entraînés pour chaque street (preflop, flop, turn, river), permettant de classifier rapidement n'importe quelle main dans un bucket spécifique.

## Qu'est-ce qu'un bucket ?

Un **bucket** est un groupe de mains de poker similaires basées sur :
- **Force de main** : Équité actuelle contre un adversaire
- **Potentiel de tirage** : Possibilités de flush draw, straight draw, combo draws
- **Texture du board** : Paires, monotonie de couleur, hauteur des cartes
- **Contexte** : Position, Stack-to-Pot Ratio (SPR), équité future

### Nombre de Buckets par Street

Le système utilise différents nombres de buckets selon la street :
- **Preflop** : 12-24 buckets (espace de mains limité)
- **Flop** : 60-80 buckets (haute complexité, nombreuses textures)
- **Turn** : 40-80 buckets (tirage se définissant)
- **River** : 24-64 buckets (décisions de showdown)

## Architecture du Système

### Modules Principaux

#### 1. **bucketing.py** (`src/holdem/abstraction/bucketing.py`)

Module principal pour la création et l'utilisation des buckets.

**Classe principale : `HandBucketing`**

```python
class HandBucketing:
    """K-means clustering pour l'abstraction de mains."""
    
    def __init__(self, config: BucketConfig, preflop_equity_samples: int = 100)
    def build(self, num_samples: int = None)
    def get_bucket(self, hole_cards, board, street, pot, stack, is_in_position) -> int
    def save(self, path: Path)
    @classmethod
    def load(cls, path: Path) -> "HandBucketing"
```

**Fonctions utilitaires :**
- `generate_random_hands()` : Génère des mains aléatoires pour les tests

#### 2. **postflop_features.py** (`src/holdem/abstraction/postflop_features.py`)

Extraction de features pour les situations postflop (flop, turn, river).

**Fonction principale :**
```python
def extract_postflop_features(
    hole_cards: List[Card],
    board: List[Card],
    street: Street,
    pot: float = 100.0,
    stack: float = 200.0,
    is_in_position: bool = True,
    num_opponents: int = 1,
    equity_samples: int = 500,
    future_equity_samples: int = 100
) -> np.ndarray
```

**Retourne un vecteur de 34 dimensions contenant :**
- 12 dimensions : Catégorie de main (one-hot encoding)
- 4 dimensions : Type de flush draw (one-hot encoding)
- 5 dimensions : Type de straight draw (one-hot + flag)
- 1 dimension : Combo draw
- 6 dimensions : Texture du board (flags binaires)
- 6 dimensions : Contexte (équité, SPR, position)

**Fonctions d'analyse de mains :**

```python
def classify_hand_category(hole_cards, board) -> int
```
Classifie la main en 12 catégories :
- HIGH_CARD (0) : Carte haute
- UNDERPAIR (1) : Paire inférieure au board
- SECOND_PAIR (2) : Deuxième paire
- TOP_PAIR (3) : Paire supérieure
- OVERPAIR (4) : Surpaire
- TWO_PAIR_BOARD_HAND (5) : Double paire (1 board + 1 main)
- TWO_PAIR_POCKET (6) : Double paire (paire de poche)
- TRIPS (7) : Brelan
- STRAIGHT (8) : Suite
- FLUSH (9) : Couleur
- FULL_HOUSE (10) : Full
- QUADS_OR_STRAIGHT_FLUSH (11) : Carré ou quinte flush

```python
def detect_flush_draw(hole_cards, board) -> int
```
Détecte le type de tirage couleur :
- NONE (0) : Pas de tirage
- BACKDOOR (1) : Tirage backdoor (2 cartes nécessaires)
- DIRECT_NON_NUT (2) : Tirage direct, non-nuts
- DIRECT_NUT (3) : Tirage direct, nuts

```python
def detect_straight_draw(hole_cards, board) -> Tuple[int, int]
```
Détecte le type de tirage quinte :
- Retourne (type, is_high)
- Types : NONE (0), GUTSHOT (1), OESD (2), DOUBLE (3)
- is_high : 1 si vise le haut du board, 0 sinon

```python
def has_combo_draw(flush_draw_type, straight_draw_type) -> int
```
Vérifie si la main a un combo draw (flush + straight).

```python
def analyze_board_texture(board) -> np.ndarray
```
Analyse la texture du board (6 flags binaires) :
- board_paired : Board contient au moins une paire
- board_trips_or_more : Board a brelan ou mieux
- board_monotone : Au moins 3 cartes de la même couleur
- board_two_suited : Exactement 2 cartes de la même couleur
- board_ace_high : Carte la plus haute est un As
- board_low : Toutes les cartes ≤ 9

```python
def calculate_future_equity(hole_cards, board, street, num_samples) -> float
```
Calcule l'équité moyenne sur les streets futures :
- Flop : équité moyenne sur les turns échantillonnés
- Turn : équité moyenne sur les rivers échantillonnés
- River : retourne 0 (pas de street future)

```python
def bin_spr(spr: float) -> np.ndarray
```
Convertit le SPR en bins (one-hot 3 dimensions) :
- [1, 0, 0] : SPR < 3 (faible)
- [0, 1, 0] : 3 ≤ SPR ≤ 8 (moyen)
- [0, 0, 1] : SPR > 8 (élevé)

#### 3. **preflop_features.py** (`src/holdem/abstraction/preflop_features.py`)

Extraction de features pour le preflop.

**Fonction principale :**
```python
def extract_preflop_features(
    hole_cards: List[Card],
    equity_samples: int = 500
) -> np.ndarray
```

**Retourne un vecteur de 10 dimensions :**
- High card value (0-1) : Rang normalisé de la carte haute
- Low card value (0-1) : Rang normalisé de la carte basse
- Is pair (binaire) : 1 si paire de poche
- Is suited (binaire) : 1 si même couleur
- Gap (0-1) : Écart normalisé entre les rangs
- Is broadway (binaire) : 1 si les deux cartes ≥ T
- Is suited connectors (binaire) : 1 si suited et connectées
- Is premium pair (binaire) : 1 si QQ/KK/AA
- Equity vs random (0-1) : Équité approx. contre une main aléatoire
- Hand strength score (0-1) : Métrique composite

#### 4. **Scripts de Construction**

##### build_flop.py (`abstraction/build_flop.py`)

Construit l'abstraction pour le flop avec clustering k-medoids.

**Fonction principale :**
```python
def build_flop_abstraction(
    num_buckets: int = 8000,
    num_samples: int = 50000,
    seed: int = 42,
    output_dir: Path = None
)
```

**Caractéristiques :**
- Crée 5k-10k buckets basés sur E[HS], E[HS²], texture, draw potential
- Utilise k-medoids pour meilleure interprétabilité
- Génère des checksums SHA-256
- Sauvegarde les medoids et paramètres de normalisation

**Utilisation en ligne de commande :**
```bash
python abstraction/build_flop.py --buckets 8000 --samples 50000 --seed 42 --output data/abstractions/flop
```

##### build_turn.py (`abstraction/build_turn.py`)

Construit l'abstraction pour le turn.

**Fonction principale :**
```python
def build_turn_abstraction(
    num_buckets: int = 2000,
    num_samples: int = 30000,
    seed: int = 42,
    output_dir: Path = None
)
```

**Caractéristiques :**
- Crée 1k-3k buckets
- Résolution des tirages
- Évolution de la texture du board

**Utilisation en ligne de commande :**
```bash
python abstraction/build_turn.py --buckets 2000 --samples 30000 --seed 42 --output data/abstractions/turn
```

##### build_river.py (`abstraction/build_river.py`)

Construit l'abstraction pour le river.

**Fonction principale :**
```python
def build_river_abstraction(
    num_buckets: int = 400,
    num_samples: int = 20000,
    seed: int = 42,
    output_dir: Path = None
)
```

**Caractéristiques :**
- Crée 200-500 buckets
- Calcul d'équité exacte
- Classement de main avec kickers
- Classification simplifiée (pas besoin de tirages)

**Utilisation en ligne de commande :**
```bash
python abstraction/build_river.py --buckets 400 --samples 20000 --seed 42 --output data/abstractions/river
```

#### 5. **features.py** (`src/holdem/abstraction/features.py`)

Utilitaires partagés pour l'extraction de features.

**Fonctions principales :**
```python
def card_to_eval7(card: Card) -> eval7.Card
```
Convertit un objet Card en carte eval7.

```python
def calculate_equity(
    hole_cards: List[Card],
    board: List[Card],
    num_opponents: int = 1,
    num_samples: int = 500
) -> float
```
Calcule l'équité par simulation Monte Carlo.

## Création de buckets.pkl - Méthode Simple

### Prérequis

```bash
# Installation des dépendances
pip install -e .
# ou
export PYTHONPATH=/path/to/poker/src:$PYTHONPATH
```

### Script Python Simple

Créez un fichier `create_buckets.py` :

```python
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
```

### Exécution

```bash
python create_buckets.py
```

**Temps d'exécution estimé :** 30-60 minutes selon la puissance de votre machine.

## Création de buckets.pkl - Méthode Avancée

### Configuration Personnalisée

Créez un fichier `custom_buckets_config.py` :

```python
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
```

### Utilisation des Configurations

```bash
# Configuration rapide (tests)
python custom_buckets_config.py fast

# Configuration équilibrée (recommandée)
python custom_buckets_config.py balanced

# Configuration haute qualité
python custom_buckets_config.py hq
```

## Options de Configuration

### BucketConfig

```python
from holdem.types import BucketConfig

config = BucketConfig(
    k_preflop=24,      # 12-24 recommandé
    k_flop=80,         # 60-80 recommandé
    k_turn=80,         # 40-80 recommandé
    k_river=64,        # 24-64 recommandé
    num_samples=500000, # 100k-500k
    seed=42            # Pour reproductibilité
)
```

### Paramètres d'Équité

- **equity_samples** : Nombre d'échantillons Monte Carlo pour calculer l'équité actuelle
  - Training: 100 (rapide)
  - Production: 500 (précis)

- **future_equity_samples** : Échantillons pour équité future
  - Training: 50 (rapide)
  - Production: 100 (précis)

- **preflop_equity_samples** : Échantillons pour preflop
  - Fast: 50
  - Balanced: 100
  - High-quality: 200

### Fichier YAML de Configuration

Vous pouvez aussi utiliser `assets/abstraction/buckets_config.yaml` :

```yaml
# Bucketing Configuration

# Number of buckets per street
k_preflop: 24
k_flop: 80
k_turn: 80
k_river: 64

# Number of hands to sample for clustering
num_samples: 500000

# Random seed for reproducibility
seed: 42

# Feature extraction settings
features:
  use_equity: true
  use_position: true
  use_spr: true
  use_draws: true
  
# K-means settings
kmeans:
  n_init: 10
  max_iter: 300
  tol: 0.0001
```

## Validation et Tests

### Test de Chargement

```python
from pathlib import Path
from holdem.abstraction.bucketing import HandBucketing
from holdem.types import Card, Street

# Charger les buckets
bucketing = HandBucketing.load(Path("assets/abstraction/buckets.pkl"))

# Tester avec une main
hole_cards = [Card('A', 'h'), Card('K', 'h')]
board = [Card('Q', 'h'), Card('J', 's'), Card('9', 'd')]

bucket = bucketing.get_bucket(
    hole_cards=hole_cards,
    board=board,
    street=Street.FLOP,
    pot=100.0,
    stack=200.0,
    is_in_position=True
)

print(f"Main: {hole_cards[0]}{hole_cards[1]}")
print(f"Board: {board}")
print(f"Bucket: {bucket}/80")
```

### Script de Validation Complet

Créez `validate_buckets.py` :

```python
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
```

### Exécution de la Validation

```bash
python validate_buckets.py assets/abstraction/buckets.pkl
```

### Tests Unitaires

```bash
# Tester l'extraction de features
export PYTHONPATH=/path/to/poker/src:$PYTHONPATH
pytest tests/test_preflop_features.py -v
pytest tests/test_postflop_features.py -v

# Tester le bucketing complet
pytest tests/test_bucketing.py -v
```

## Dépannage

### Problème : Erreur "sklearn-extra not installed"

**Solution :**
```bash
pip install scikit-learn-extra
```

Le système utilisera automatiquement KMeans de scikit-learn comme fallback si sklearn-extra n'est pas disponible.

### Problème : Temps d'exécution trop long

**Solutions :**
1. Réduire `num_samples` (ex: 100000 au lieu de 500000)
2. Réduire `equity_samples` dans les fonctions d'extraction
3. Réduire le nombre de buckets par street
4. Utiliser la configuration "fast"

### Problème : Erreur de mémoire

**Solutions :**
1. Réduire `num_samples`
2. Traiter les streets séparément
3. Augmenter la swap/mémoire virtuelle
4. Utiliser une machine avec plus de RAM

### Problème : Buckets non reproductibles

**Vérifications :**
1. Utilisez le même `seed` dans BucketConfig
2. Utilisez la même version de scikit-learn
3. Utilisez le même `num_samples`
4. Vérifiez que numpy utilise le même backend

### Problème : Erreur "eval7" lors du calcul d'équité

**Solution :**
```bash
pip install eval7
```

### Problème : Buckets existants ne se chargent pas

**Causes possibles :**
1. Version de Python différente
2. Version de scikit-learn différente
3. Fichier corrompu

**Solution :**
Recréer les buckets avec la configuration actuelle.

## Utilisation des Buckets Créés

### Dans un Script

```python
from pathlib import Path
from holdem.abstraction.bucketing import HandBucketing
from holdem.types import Card, Street

# Charger
bucketing = HandBucketing.load(Path("assets/abstraction/buckets.pkl"))

# Utiliser
hole_cards = [Card('A', 's'), Card('K', 's')]
board = [Card('Q', 's'), Card('J', 'h'), Card('9', 'd')]

bucket = bucketing.get_bucket(
    hole_cards=hole_cards,
    board=board,
    street=Street.FLOP,
    pot=150.0,
    stack=300.0,
    is_in_position=True
)

print(f"Bucket assigné: {bucket}")
```

### Dans le Système MCCFR

Les buckets sont automatiquement chargés lors de l'entraînement MCCFR :

```python
from holdem.training.blueprint import train_blueprint

train_blueprint(
    output_dir="checkpoints/my_strategy",
    buckets_path="assets/abstraction/buckets.pkl",  # Utilise vos buckets
    num_iterations=1000,
    checkpoint_freq=100
)
```

### Préchargement pour Performance

```python
# Charger une fois au démarrage
bucketing = HandBucketing.load(Path("assets/abstraction/buckets.pkl"))

# Réutiliser pour toutes les mains
for hand_state in game_states:
    bucket = bucketing.get_bucket(
        hole_cards=hand_state.hole_cards,
        board=hand_state.board,
        street=hand_state.street,
        pot=hand_state.pot,
        stack=hand_state.stack,
        is_in_position=hand_state.is_ip
    )
    # Utiliser le bucket...
```

## Comparaison des Méthodes de Construction

### Méthode Simple (HandBucketing)

**Avantages :**
- Code simple et direct
- Abstraction de haut niveau
- Gestion automatique des features
- Un seul fichier de sortie

**Inconvénients :**
- Moins de contrôle granulaire
- Paramètres d'équité fixés lors de l'entraînement

**Utilisation recommandée :** Production, entraînement standard

### Méthode Scripts (build_flop.py, build_turn.py, build_river.py)

**Avantages :**
- Contrôle fin sur chaque street
- Peut utiliser k-medoids
- Checksums SHA-256 pour vérification
- Fichiers séparés par street
- Paramètres de normalisation sauvegardés

**Inconvénients :**
- Plus complexe
- Fichiers multiples à gérer
- Format différent de HandBucketing

**Utilisation recommandée :** Recherche, expérimentation, analyse approfondie

## Recommandations Finales

### Pour Débuter
1. Utilisez la **méthode simple** avec configuration balanced
2. Temps: ~30-45 minutes
3. Fichier: `assets/abstraction/buckets.pkl`

### Pour Production
1. Utilisez la **configuration haute qualité**
2. `num_samples=500000` minimum
3. `equity_samples=500` dans les features
4. Validez avec `validate_buckets.py`

### Pour Recherche
1. Utilisez les **scripts build_*.py**
2. Expérimentez avec différents nombres de buckets
3. Analysez les medoids et checksums
4. Comparez les performances

### Performance
- **Temps de construction** : 10-90 minutes selon config
- **Temps d'inférence** : 1-5ms par main
- **Taille fichier** : 10-50MB selon nombre de buckets
- **Mémoire runtime** : ~100-500MB pour le modèle chargé

## Références

### Documentation Connexe
- [FEATURE_EXTRACTION.md](FEATURE_EXTRACTION.md) - Détails sur les vecteurs de features
- [README.md](README.md) - Vue d'ensemble du projet
- [GETTING_STARTED.md](GETTING_STARTED.md) - Guide de démarrage rapide

### Code Source
- `src/holdem/abstraction/bucketing.py` - Classe principale HandBucketing
- `src/holdem/abstraction/postflop_features.py` - Features postflop (34 dims)
- `src/holdem/abstraction/preflop_features.py` - Features preflop (10 dims)
- `src/holdem/abstraction/features.py` - Utilitaires (equity, eval7)
- `abstraction/build_flop.py` - Script construction flop
- `abstraction/build_turn.py` - Script construction turn
- `abstraction/build_river.py` - Script construction river

### Dépendances
- `numpy` - Calculs numériques
- `scikit-learn` - K-means clustering
- `scikit-learn-extra` - K-medoids clustering (optionnel)
- `eval7` - Évaluation rapide de mains
- `pyyaml` - Configuration YAML

---

**Auteur :** Documentation générée pour le projet montana2ab/poker  
**Date :** 2025-11  
**Version :** 1.0
