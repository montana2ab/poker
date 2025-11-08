# RUNTIME_CHECKLIST.md

Checklist de performance, latence et mémoire pour le jeu en temps réel (per-hand budget, threads, RAM)

## Vue d'ensemble

Ce document fournit une checklist complète pour optimiser et valider les performances du système poker AI en temps réel. Chaque section contient des cibles mesurables et des actions de vérification.

---

## 1. BUDGET TEMPS PAR MAIN (LATENCE)

### 1.1 Cibles de latence

| Composant | Target p50 | Target p95 | Target p99 | Max acceptable |
|-----------|-----------|-----------|-----------|----------------|
| Vision/OCR (parsing complet) | 50ms | 100ms | 150ms | 200ms |
| Bucketing (assign bucket) | 5ms | 10ms | 15ms | 20ms |
| Blueprint lookup | 1ms | 2ms | 5ms | 10ms |
| Realtime search (total) | 80ms | 150ms | 200ms | 300ms |
| Action execution (click) | 20ms | 50ms | 80ms | 100ms |
| **TOTAL (end-to-end)** | **150ms** | **300ms** | **400ms** | **600ms** |

### 1.2 Vérifications

- [ ] Mesurer latences avec profiling sur 1000+ mains
- [ ] Logger percentiles (p50/p95/p99) dans métriques
- [ ] Identifier bottlenecks si p95 > target
- [ ] Optimiser top 3 hotspots
- [ ] Valider amélioration post-optimisation
- [ ] Configurer alertes si p99 > max acceptable

### 1.3 Commandes de test

```bash
# Profiling complet avec cProfile
python -m cProfile -o profile.stats -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 \
  --hands 1000

# Analyser résultats
python -m pstats profile.stats
# Dans pstats shell:
# stats 20  # Top 20 fonctions
# sort cumtime
# stats 20

# Time budget validation
pytest tests/test_realtime_budget.py -v
```

### 1.4 Configuration optimale

**SearchConfig recommandé:**
```python
SearchConfig(
    time_budget_ms=80,        # 80ms pour majorité des cas
    min_iterations=100,        # Minimum pour qualité
    max_iterations=500,        # Plafond si temps restant
    kl_weight=0.5,            # Régularisation modérée
    num_public_samples=10,    # Compromise variance/speed
    use_warm_start=True       # Toujours activer
)
```

---

## 2. THREADS ET PARALLÉLISME

### 2.1 Configuration multi-threading

#### Workers MCCFR Training

- [ ] `num_workers = 0` (auto-detect cores) pour training
- [ ] Vérifier charge CPU ~95% pendant training
- [ ] Valider aucun worker idle >5% du temps
- [ ] Queue timeouts adaptés à la plateforme:
  - Linux/Windows x86: 10ms
  - Intel macOS: 50ms
  - Apple Silicon (M1/M2/M3): 100ms

#### Parallel Resolving (temps réel)

- [ ] `num_resolve_threads = 2-4` pour parallel solving
- [ ] Thread pool persistant (éviter création/destruction)
- [ ] Affinity CPU si disponible (Linux: `taskset`, macOS: éviter)
- [ ] Monitoring context switches: viser <1000/sec

### 2.2 Vérifications

```bash
# Vérifier utilisation CPU
htop  # Linux/macOS
# ou
top  # macOS

# Monitoring threads
python -c "
import threading
print(f'Active threads: {threading.active_count()}')
print(f'Thread names: {[t.name for t in threading.enumerate()]}')
"

# Tests parallélisme
pytest tests/test_parallel_*.py -v

# Vérifier affinité (Linux only)
taskset -c 0-7 python -m holdem.cli.train_blueprint \
  --num-workers 8 \
  --iters 10000
```

### 2.3 Configuration optimale

**MCCFRConfig recommandé:**
```python
MCCFRConfig(
    num_iterations=10_000_000,
    use_linear_weighting=True,
    enable_pruning=True,
    pruning_threshold=-300_000_000,  # Pluribus value
    
    # Parallel config
    num_workers=0,  # Auto-detect
    batch_size=100,  # Balance communication overhead
    
    # Platform-specific (set automatically)
    queue_timeout_ms=10 if not is_macos() else 50
)
```

---

## 3. MÉMOIRE RAM

### 3.1 Cibles mémoire

| Composant | Baseline | Target | Max acceptable |
|-----------|----------|--------|----------------|
| Bucketing models (loaded) | 50MB | 100MB | 200MB |
| Blueprint policy (10M iters) | 2GB | 4GB | 8GB |
| Regrets (training) | 4GB | 8GB | 16GB |
| Vision buffers | 100MB | 200MB | 500MB |
| Process total (runtime) | 1GB | 2GB | 4GB |
| Process total (training) | 8GB | 12GB | 24GB |

### 3.2 Vérifications

- [ ] Mesurer RSS (Resident Set Size) en steady state
- [ ] Vérifier pas de memory leak (RSS croît linéairement)
- [ ] Profiler allocations avec `memory_profiler`
- [ ] Valider garbage collection efficace
- [ ] Compresser checkpoints (gzip level 6)
- [ ] Considérer compact storage si RAM limitée

### 3.3 Commandes de test

```bash
# Memory profiling
python -m memory_profiler -m holdem.cli.train_blueprint \
  --iters 1000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir /tmp/train_test

# Monitoring continu
watch -n 1 'ps aux | grep python'

# Detailed memory breakdown
pip install pympler
python -c "
from pympler import asizeof
from holdem.mccfr.policy_store import PolicyStore

policy = PolicyStore.load('runs/blueprint/avg_policy.json')
print(f'Policy size: {asizeof.asizeof(policy) / 1024**2:.1f} MB')
"

# Tests mémoire
pytest tests/ -v --memray  # Si memray installé
```

### 3.4 Optimisations mémoire

**Options de configuration:**

```python
# Compact storage (si RAM limitée)
MCCFRConfig(
    use_compact_storage=True,  # Utilise float16 pour regrets
    checkpoint_interval=100000,  # Checkpoint + clear memory
    tensorboard_log_interval=5000  # Réduire overhead logging
)

# Preflop equity optimisation
BucketConfig(
    preflop_equity_samples=100  # Runtime: fast
    # vs 1000 pour training: precise
)
```

---

## 4. STOCKAGE DISQUE

### 4.1 Cibles I/O

| Opération | Target | Max acceptable |
|-----------|--------|----------------|
| Checkpoint save | 5s | 10s |
| Checkpoint load | 3s | 8s |
| Snapshot save | 2s | 5s |
| Policy export JSON | 1s | 3s |
| Bucketing save/load | 1s | 3s |

### 4.2 Tailles fichiers

| Fichier | Size (typical) | Size (compressed) |
|---------|----------------|-------------------|
| Checkpoint (1M iters) | 500MB | 100MB |
| Checkpoint (10M iters) | 5GB | 1GB |
| Average policy JSON | 200MB | 50MB |
| Bucketing models | 50MB | 10MB |

### 4.3 Vérifications

- [ ] Utiliser pickle protocol 4 (efficient binary)
- [ ] Compresser checkpoints avec gzip/lz4
- [ ] Rotation checkpoints (garder derniers 5)
- [ ] Monitorer espace disque (alerte <10GB libre)
- [ ] Tests I/O performance sur SSD vs HDD
- [ ] Checkpoints sur SSD si possible

### 4.4 Commandes

```bash
# Mesurer I/O
time python -c "
from holdem.utils.serialization import save_pickle, load_pickle
data = {'test': list(range(1000000))}
save_pickle(data, '/tmp/test.pkl')
"

# Compresser checkpoints
gzip runs/blueprint/checkpoint_*.pkl

# Nettoyer vieux checkpoints
find runs/ -name "checkpoint_*.pkl" -mtime +7 -delete

# Monitoring espace disque
df -h
du -sh runs/blueprint/
```

---

## 5. LATENCE RÉSEAU (SI CLIENT DISTANT)

### 5.1 Cibles

| Métrique | Target | Max acceptable |
|----------|--------|----------------|
| RTT (ping) | <10ms | <50ms |
| Bandwidth upload | >1Mbps | >0.5Mbps |
| Bandwidth download | >5Mbps | >1Mbps |
| Packet loss | <0.1% | <1% |

### 5.2 Vérifications

- [ ] Ping serveur poker: `ping poker-server.com`
- [ ] Bandwidth test: `speedtest-cli`
- [ ] Latence API calls si applicable
- [ ] Timeout configurations réseau (5-10s)
- [ ] Retry logic pour appels réseau

---

## 6. INSTRUMENTATION ET MONITORING

### 6.1 Métriques essentielles

**Collecter en temps réel:**

- Latence par composant (vision, bucketing, search, action)
- CPU utilisation par worker
- RAM RSS et swap usage
- Queue depths (task queue, result queue)
- Iteration throughput (iters/sec)
- Error rates (vision, OCR, parse)

### 6.2 Outils recommandés

```bash
# Prometheus + Grafana (production)
pip install prometheus-client

# TensorBoard (training)
tensorboard --logdir runs/blueprint/tensorboard

# Custom logging
python -m holdem.cli.run_dry_run \
  --profile profile.json \
  --policy policy.json \
  --log-level DEBUG \
  --metrics-file metrics.json
```

### 6.3 Dashboard exemple

**Metrics à afficher:**

1. Latency heatmap (par hand)
2. CPU/RAM time series
3. Iteration throughput (training)
4. Vision accuracy rolling average
5. Error log (dernières 100)

---

## 7. TESTS DE CHARGE

### 7.1 Scénarios

#### Scenario 1: Training intensif
```bash
# 8h training continu
timeout 28800 python -m holdem.cli.train_blueprint \
  --iters 10000000 \
  --num-workers 0 \
  --batch-size 100 \
  --logdir runs/load_test
  
# Vérifier:
# - Pas de memory leak
# - CPU stable ~95%
# - Pas de crash
# - Throughput stable (±10%)
```

#### Scenario 2: Autoplay prolongé
```bash
# 100 mains consécutives
python -m holdem.cli.run_autoplay \
  --profile profile.json \
  --policy policy.json \
  --max-hands 100 \
  --metrics-file autoplay_metrics.json
  
# Vérifier:
# - Latence p95 < 300ms
# - Aucun timeout
# - Vision accuracy > 97%
# - Pas de crash
```

#### Scenario 3: Stress test
```bash
# Training + autoplay simultanés
python -m holdem.cli.train_blueprint --logdir train_bg &
python -m holdem.cli.run_autoplay --profile profile.json --policy policy.json &

# Vérifier:
# - Dégradation latence < 20%
# - CPU total < 100%
# - RAM stable
```

### 7.2 Critères de succès

- [ ] Training: 8h sans crash
- [ ] Autoplay: 100 mains sans timeout
- [ ] Stress: latence dégradation < 20%
- [ ] Memory: aucun leak détecté
- [ ] CPU: stable ±10%

---

## 8. PROTOCOLE VALIDATION PRÉ-PRODUCTION

### 8.1 Checklist pré-déploiement

#### Performance
- [ ] Latence p95 < 300ms sur 1000 mains
- [ ] CPU utilization 90-95% training
- [ ] RAM steady state < 4GB runtime
- [ ] Aucun memory leak sur 8h
- [ ] I/O checkpoint < 10s

#### Qualité
- [ ] Vision accuracy > 97%
- [ ] OCR accuracy > 97%
- [ ] Blueprint convergence vérifiée
- [ ] Tests end-to-end passent
- [ ] Pas de régression vs baseline

#### Robustesse
- [ ] 100 mains sans crash
- [ ] Gestion erreurs OK (screenshots invalides, OCR fail)
- [ ] Fallback blueprint fonctionne
- [ ] Logging complet sans spam
- [ ] Monitoring dashboards fonctionnels

### 8.2 Sign-off

**Responsable technique:** ___________  **Date:** __________

**Performance:** ✓ / ✗  
**Qualité:** ✓ / ✗  
**Robustesse:** ✓ / ✗  

**Notes:**
_____________________________________________________________
_____________________________________________________________

---

## 9. OPTIMISATIONS AVANCÉES

### 9.1 Si latence excessive

1. **Profiling détaillé**
   ```bash
   python -m cProfile -o profile.stats script.py
   python -m pstats profile.stats
   ```

2. **Hotspots communs:**
   - Vision: OCR trop lent → augmenter cache, réduire résolution
   - Bucketing: predict lent → pré-calculer buckets fréquents
   - Search: timeout → réduire min_iterations ou num_public_samples

3. **Optimisations code:**
   - Vectorisation numpy
   - Cython pour boucles critiques
   - JIT avec numba (@jit decorator)
   - Caching avec functools.lru_cache

### 9.2 Si RAM insuffisante

1. **Compact storage:**
   ```python
   MCCFRConfig(use_compact_storage=True)  # Utilise float16
   ```

2. **Streaming checkpoints:**
   - Sauvegarder plus fréquemment
   - Libérer mémoire après save

3. **Gradient checkpointing** (si applicable)
   - Recompute au lieu de stocker

4. **Swap sur SSD** (dernier recours)
   ```bash
   sudo swapon --show
   # Augmenter si nécessaire
   ```

### 9.3 Si CPU sous-utilisé

1. **Augmenter batch_size**
   ```python
   MCCFRConfig(batch_size=200)  # vs 100 par défaut
   ```

2. **Vérifier num_workers = 0** (auto-detect)

3. **Réduire queue timeouts** (si non-macOS)

4. **Affinité CPU**
   ```bash
   taskset -c 0-7 python script.py
   ```

---

## 10. TROUBLESHOOTING

### Problème: Latence > 500ms
- **Cause:** Vision/OCR trop lent
- **Solution:** 
  1. Réduire résolution screenshots
  2. Cache templates matching
  3. Augmenter queue timeouts
  4. Profiler avec cProfile

### Problème: Memory leak
- **Cause:** Objets non libérés
- **Solution:**
  1. Profiler avec memory_profiler
  2. Vérifier cycles de références
  3. Garbage collect explicite: `gc.collect()`
  4. Utiliser weak references

### Problème: Training lent
- **Cause:** I/O overhead, workers idle
- **Solution:**
  1. Augmenter batch_size
  2. Réduire checkpoint_interval
  3. Réduire tensorboard_log_interval
  4. Vérifier num_workers = 0

### Problème: Crashes fréquents
- **Cause:** Spawn issues, memory overflow
- **Solution:**
  1. Vérifier multiprocessing start method = 'spawn'
  2. Augmenter ulimits (Linux)
  3. Réduire num_workers si OOM
  4. Logger stack traces complètes

---

## 11. RÉFÉRENCES

- **Pluribus paper:** Brown & Sandholm (2019), Supplementary Materials section "Engineering"
- **MCCFR optimizations:** Lanctot et al. (2009), "Monte Carlo Sampling for Regret Minimization"
- **Performance profiling:** Python docs - https://docs.python.org/3/library/profile.html
- **Memory profiling:** memory_profiler - https://pypi.org/project/memory-profiler/

---

## ANNEXE A: CONFIGURATION MATÉRIELLE RECOMMANDÉE

### Minimum (Development)
- CPU: 4 cores (Intel i5 / AMD Ryzen 5)
- RAM: 8GB
- Disk: 100GB SSD
- GPU: Non requis

### Recommandé (Training)
- CPU: 16+ cores (Intel Xeon / AMD Threadripper)
- RAM: 32GB
- Disk: 500GB NVMe SSD
- GPU: Non requis (CPU-bound)

### Optimal (Production)
- CPU: 32+ cores
- RAM: 64GB
- Disk: 1TB NVMe SSD RAID
- Network: Low-latency (<10ms RTT)

---

## ANNEXE B: COMMANDES RAPIDES

```bash
# Profiling rapide
python -m cProfile -o /tmp/profile.stats script.py && python -m pstats /tmp/profile.stats

# Memory snapshot
python -m memory_profiler script.py

# Monitoring continu
watch -n 1 'ps aux | grep python | grep -v grep'

# Latency test
time python -m holdem.cli.run_dry_run --hands 100

# Throughput test
python -c "
import time
start = time.time()
# Training code here
elapsed = time.time() - start
print(f'Iterations per second: {iterations / elapsed:.1f}')
"

# Disk I/O test
dd if=/dev/zero of=/tmp/test bs=1M count=1024
```

---

**Version:** 1.0  
**Dernière mise à jour:** 2025-11-08  
**Maintenu par:** montana2ab
