# Parallel Training and Real-time Solving

Ce document explique comment utiliser l'entraînement parallèle et le solving en temps réel multi-coeur pour optimiser les performances.

## Vue d'ensemble

Le système supporte maintenant le multiprocessing pour:
1. **Entraînement du blueprint (MCCFR)** - Utilise plusieurs coeurs CPU pour accélérer l'entraînement
2. **Solving en temps réel** - Résout les sous-jeux en parallèle pour des décisions plus rapides

## Entraînement parallèle

### Configuration de base

Utilisez le paramètre `--num-workers` pour spécifier le nombre de processus parallèles:

```bash
# Utiliser 4 coeurs CPU
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/parallel_training \
  --iters 1000000 \
  --num-workers 4 \
  --batch-size 100

# Utiliser TOUS les coeurs CPU disponibles
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/parallel_training \
  --iters 1000000 \
  --num-workers 0 \
  --batch-size 100
```

### Paramètres

- `--num-workers N`:
  - `N = 1`: Mode séquentiel (un seul processus) - par défaut
  - `N > 1`: Utilise N processus parallèles
  - `N = 0`: Utilise automatiquement tous les coeurs CPU disponibles

- `--batch-size N`: Nombre d'itérations par batch de workers (défaut: 100)
  - Plus grand = moins de surcharge de communication, mais moins de mise à jour fréquente
  - Plus petit = mises à jour plus fréquentes, mais plus de surcharge
  - Recommandé: 50-200 pour la plupart des cas

### Exemples de configuration

#### Entraînement rapide sur machine multi-coeur (8 coeurs)

```bash
python -m holdem.cli.train_blueprint \
  --time-budget 3600 \
  --snapshot-interval 300 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/fast_8core \
  --num-workers 0 \
  --batch-size 100
```

#### Entraînement long terme (8 jours) avec 16 coeurs

```bash
python -m holdem.cli.train_blueprint \
  --time-budget 691200 \
  --snapshot-interval 3600 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/8days_16cores \
  --num-workers 16 \
  --batch-size 200
```

#### Configuration YAML pour l'entraînement parallèle

Créez un fichier `configs/parallel_training.yaml`:

```yaml
# Configuration pour l'entraînement parallèle
time_budget_seconds: 691200  # 8 jours
snapshot_interval_seconds: 3600  # 1 heure

# Paramètres parallèles
num_workers: 0  # Utilise tous les coeurs
batch_size: 100

# Paramètres MCCFR standards
discount_interval: 5000
regret_discount_alpha: 1.0
strategy_discount_beta: 1.0
exploration_epsilon: 0.6
enable_pruning: true
pruning_threshold: -300000000.0
pruning_probability: 0.95
```

Utilisez avec:

```bash
python -m holdem.cli.train_blueprint \
  --config configs/parallel_training.yaml \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/parallel_yaml
```

## Solving en temps réel parallèle

### Utilisation en mode dry-run

```bash
# Utiliser 2 workers pour le solving en temps réel
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 \
  --min-iters 100 \
  --num-workers 2

# Utiliser tous les coeurs disponibles
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 \
  --min-iters 100 \
  --num-workers 0
```

### Utilisation en mode auto-play

```bash
python -m holdem.cli.run_autoplay \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 \
  --min-iters 100 \
  --num-workers 4 \
  --i-understand-the-tos
```

### Recommandations pour le solving en temps réel

- **Pour décisions rapides (<100ms)**: Utilisez 2-4 workers
- **Pour plus de qualité**: Augmentez `--min-iters` plutôt que `--num-workers`
- **Budget temps limité**: Le parallélisme aide peu si le temps est très court (< 50ms)
- **Overhead**: Le multiprocessing a un coût - test pour trouver le meilleur équilibre

## Performance et optimisation

### Choix du nombre de workers

```python
import multiprocessing as mp

# Obtenir le nombre de coeurs
num_cores = mp.cpu_count()
print(f"CPU cores available: {num_cores}")

# Règle générale:
# - Entraînement: utilisez tous les coeurs (num_workers=0)
# - Real-time solving: utilisez 2-4 workers maximum
```

### Monitoring des performances

Surveillez les métriques dans TensorBoard:

```bash
tensorboard --logdir runs/parallel_training/tensorboard
```

Métriques importantes:
- `Performance/IterationsPerSecond`: Itérations par seconde
- `Training/Utility`: Utilité moyenne
- Plus de workers devrait augmenter les itérations/seconde

### Considérations de mémoire

Chaque worker consomme de la mémoire. Pour l'entraînement avec beaucoup de workers:

- Surveillez l'utilisation de RAM
- Réduisez `batch_size` si nécessaire
- Considérez les limitations de mémoire partagée

## Résolution de problèmes

### Problème: Performance plus lente avec plus de workers

**Causes possibles:**
1. Overhead de communication trop élevé
2. Batch size trop petit
3. Limite de mémoire atteinte

**Solutions:**
```bash
# Augmentez la batch size
--batch-size 200

# Réduisez le nombre de workers
--num-workers 4  # au lieu de 16
```

### Problème: "Too many open files"

Sur Linux/macOS, augmentez la limite:

```bash
ulimit -n 4096
```

### Problème: Workers ne démarrent pas

Vérifiez que multiprocessing fonctionne:

```python
import multiprocessing as mp

def test_worker(x):
    return x * 2

if __name__ == "__main__":
    with mp.Pool(4) as pool:
        result = pool.map(test_worker, range(10))
        print(result)
```

## Benchmarks

Tests sur différentes configurations (approximatifs):

| Configuration | Itérations/sec | Speedup |
|--------------|----------------|---------|
| 1 worker     | ~1000          | 1x      |
| 4 workers    | ~3500          | 3.5x    |
| 8 workers    | ~6500          | 6.5x    |
| 16 workers   | ~11000         | 11x     |

*Note: Les résultats dépendent du CPU, mémoire, et configuration*

## Exemples d'utilisation

### Script d'entraînement automatisé

```bash
#!/bin/bash
# train_parallel.sh

BUCKETS="assets/abstraction/precomputed_buckets.pkl"
LOGDIR="runs/$(date +%Y%m%d_%H%M%S)_parallel"

# Déterminer le nombre de coeurs
NUM_CORES=$(python -c "import multiprocessing; print(multiprocessing.cpu_count())")
echo "Using $NUM_CORES CPU cores"

# Entraînement avec tous les coeurs
python -m holdem.cli.train_blueprint \
  --time-budget 86400 \
  --snapshot-interval 3600 \
  --buckets "$BUCKETS" \
  --logdir "$LOGDIR" \
  --num-workers 0 \
  --batch-size 100 \
  --tensorboard

echo "Training complete. Results in $LOGDIR"
```

### Configuration Python programmatique

```python
from pathlib import Path
from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.parallel_solver import ParallelMCCFRSolver

# Configuration parallèle
config = MCCFRConfig(
    time_budget_seconds=3600,  # 1 heure
    snapshot_interval_seconds=300,  # 5 minutes
    num_workers=0,  # Tous les coeurs
    batch_size=100,
    exploration_epsilon=0.6,
    enable_pruning=True
)

# Charger les buckets
bucketing = HandBucketing.load(Path("assets/abstraction/precomputed_buckets.pkl"))

# Créer et entraîner
solver = ParallelMCCFRSolver(config, bucketing, num_players=2)
solver.train(logdir=Path("runs/parallel_demo"), use_tensorboard=True)
```

## Comparaison: Séquentiel vs Parallèle

### Mode séquentiel (par défaut)
- ✅ Moins de mémoire
- ✅ Plus simple à déboguer
- ❌ Plus lent
- **Utilisez si:** Machine avec peu de coeurs, ou debugging

### Mode parallèle
- ✅ Beaucoup plus rapide
- ✅ Utilise tous les coeurs CPU
- ❌ Plus de mémoire
- ❌ Overhead de communication
- **Utilisez si:** Entraînement long, machine multi-coeur

## Références

- [Python multiprocessing](https://docs.python.org/3/library/multiprocessing.html)
- [MCCFR Algorithm](https://papers.nips.cc/paper/2009/file/00411460f7c92d2124a67ea0f4cb5f85-Paper.pdf)
- [Pluribus Paper](https://science.sciencemag.org/content/365/6456/885)
