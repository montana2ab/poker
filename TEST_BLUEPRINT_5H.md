# Test avec blueprint_training_5h.yaml et --num-workers

Ce document explique comment tester le fix avec le fichier `blueprint_training_5h.yaml` qui était utilisé quand le problème est survenu.

## Le Problème Original

Quand tu lançais :
```bash
python -m holdem.cli.train_blueprint \
    --config configs/blueprint_training_5h.yaml \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/5h_test \
    --num-workers 4
```

Le moniteur d'activité restait plat (pas d'activité CPU) parce que les workers ne démarraient pas à cause du conflit avec `mp.set_start_method('spawn', force=True)`.

## Pourquoi ça Fonctionnait Sans --num-workers

Quand tu lançais **sans** `--num-workers` :
```bash
python -m holdem.cli.train_blueprint \
    --config configs/blueprint_training_5h.yaml \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/5h_test
```

- La valeur par défaut était `num_workers=1`
- Avec 1 worker, le code utilisait `MCCFRSolver` (mode simple processus) au lieu de `ParallelMCCFRSolver`
- Donc le problème avec `mp.set_start_method()` ne se produisait pas
- Tu voyais Python utiliser 2 threads dans le moniteur (1 thread principal + 1 thread système)

## Avec le Fix

Maintenant, avec le fix appliqué, tu peux utiliser `--num-workers` avec n'importe quelle valeur et ça fonctionnera correctement !

### Test 1: Avec 4 workers (recommandé pour M2)
```bash
python -m holdem.cli.train_blueprint \
    --config configs/blueprint_training_5h.yaml \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/5h_4workers \
    --num-workers 4 \
    --batch-size 100
```

**Résultat attendu dans le moniteur d'activité :**
- 1 processus Python principal
- 4 processus Python workers (chacun utilisant ~100% d'un core)
- Total: ~400% CPU utilisé

### Test 2: Avec auto-détection (utilise tous les cores)
```bash
python -m holdem.cli.train_blueprint \
    --config configs/blueprint_training_5h.yaml \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/5h_auto \
    --num-workers 0 \
    --batch-size 100
```

**Sur un Mac M2 (nombre de cores varie selon le modèle) :**
- M2 standard: 8 cores (4 performance + 4 efficiency)
- M2 Pro: 10 ou 12 cores
- M2 Max: 12 cores

**Résultat attendu :**
- 1 processus Python principal
- N processus Python workers (N = nombre de cores)
- Total: ~N*100% CPU utilisé

### Test 3: Test rapide pour vérifier que ça fonctionne
Pour un test rapide (30 secondes au lieu de 5 heures) :
```bash
python -m holdem.cli.train_blueprint \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/quick_test \
    --iters 10000 \
    --num-workers 4 \
    --batch-size 100
```

**Vérifications pendant l'exécution :**
1. Ouvre le Moniteur d'activité (Activity Monitor)
2. Cherche "Python" dans les processus
3. Tu devrais voir plusieurs processus Python actifs
4. La somme du % CPU devrait être proche de 400% (pour 4 workers)

### Test 4: Avec configuration dans le YAML
Tu peux aussi ajouter `num_workers` directement dans le fichier YAML :

Crée un nouveau fichier `configs/blueprint_training_5h_parallel.yaml` :
```yaml
# Blueprint training configuration - 5h avec parallélisation
time_budget_seconds: 18000  # 5 hours
snapshot_interval_seconds: 900  # Save snapshots every 15 minutes

# Parallélisation
num_workers: 4  # ou 0 pour auto-detect
batch_size: 100

# Linear MCCFR parameters
use_linear_weighting: true
discount_interval: 1000
regret_discount_alpha: 1.0
strategy_discount_beta: 1.0

# Exploration
exploration_epsilon: 0.6

epsilon_schedule:
  - [0,        0.60]
  - [200000,   0.35]
  - [1000000,  0.20]
  - [2000000,  0.10]

# Dynamic pruning
enable_pruning: true
pruning_threshold: -300000000.0
pruning_probability: 0.95
```

Puis lance :
```bash
python -m holdem.cli.train_blueprint \
    --config configs/blueprint_training_5h_parallel.yaml \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/5h_parallel
```

## Performance Attendue sur Mac M2

Avec le fix appliqué, voici les performances approximatives que tu devrais obtenir :

| Configuration | Iterations/sec | Temps pour 1M iter | Utilisation CPU |
|--------------|----------------|-------------------|----------------|
| 1 worker (défaut) | ~100-150 | ~2h | ~100% (1 core) |
| 4 workers | ~350-500 | ~40min | ~400% (4 cores) |
| 8 workers (M2 8-core) | ~600-800 | ~25min | ~800% (8 cores) |
| Auto (0) | ~600-1000 | ~20-25min | Maximum |

**Note:** Les iterations/sec varient selon :
- Le modèle de M2 (standard/Pro/Max)
- La température du CPU (throttling thermique)
- Les autres applications en cours d'exécution
- La complexité du bucket abstraction utilisé

## Vérification du Fix

Pour confirmer que le fix fonctionne, lance :
```bash
# Test de 1 minute avec 4 workers
python -m holdem.cli.train_blueprint \
    --config configs/blueprint_training_5h.yaml \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/test_fix \
    --time-budget 60 \
    --num-workers 4 \
    --batch-size 100
```

**Indicateurs de succès :**
1. ✅ Le script démarre sans erreur
2. ✅ Le moniteur d'activité montre 4 processus Python workers
3. ✅ La somme du % CPU est ~400%
4. ✅ Les logs montrent : "Using 4 worker process(es)"
5. ✅ Les iterations progressent (ex: "Iteration 400 (400 iter/s)")

**Indicateurs d'échec (problème non résolu) :**
1. ❌ Le moniteur d'activité reste plat (pas d'activité CPU)
2. ❌ Le script se bloque sans progresser
3. ❌ Erreur "RuntimeError" dans les logs
4. ❌ Aucun processus worker n'apparaît dans le moniteur
