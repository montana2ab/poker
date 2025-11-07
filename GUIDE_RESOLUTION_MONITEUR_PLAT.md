# Guide: Résolution du Problème de Moniteur d'Activité Plat

## Problème Résolu

Lorsque vous lanciez cette commande:

```bash
python -m holdem.cli.train_blueprint \
  --config configs/blueprint_training_5h_parallel.yaml \
  --time-budget 28800 \
  --snapshot-interval 1200 \
  --buckets assets/abstraction/buckets_mid.pkl \
  --logdir /Volumes/122/Blueprintmid_8h_v3 \
  --tensorboard \
  --num-workers 6 \
  --batch-size 100
```

Le moniteur d'activité restait plat (aucune utilisation du CPU). Ce problème est maintenant **résolu**.

## Solution Implémentée

Le code a été amélioré avec:

1. **Gestion d'erreurs complète**: Les workers qui échouent signalent maintenant leurs erreurs
2. **Timeouts adaptatifs**: Les workers bloqués sont maintenant terminés automatiquement
3. **Logging détaillé**: Vous verrez maintenant exactement ce qui se passe
4. **Test de diagnostic**: Vérifie que le multiprocessing fonctionne avant de commencer

## Comment Utiliser

### Option 1: Relancer la Même Commande

Vous pouvez maintenant relancer la même commande sans problème:

```bash
python -m holdem.cli.train_blueprint \
  --config configs/blueprint_training_5h_parallel.yaml \
  --time-budget 28800 \
  --snapshot-interval 1200 \
  --buckets assets/abstraction/buckets_mid.pkl \
  --logdir /Volumes/122/Blueprintmid_8h_v3 \
  --tensorboard \
  --num-workers 6 \
  --batch-size 100
```

### Option 2: Détecter Automatiquement le Nombre de Cœurs

Pour utiliser tous les cœurs disponibles automatiquement:

```bash
python -m holdem.cli.train_blueprint \
  --config configs/blueprint_training_5h_parallel.yaml \
  --time-budget 28800 \
  --snapshot-interval 1200 \
  --buckets assets/abstraction/buckets_mid.pkl \
  --logdir /Volumes/122/Blueprintmid_8h_v3 \
  --tensorboard \
  --num-workers 0 \
  --batch-size 100
```

**Note**: `--num-workers 0` détecte automatiquement le nombre de cœurs CPU disponibles.

## Nouveaux Messages de Diagnostic

Vous verrez maintenant ces messages:

### Au Démarrage
```
INFO: Using multiprocessing context: 'spawn' for cross-platform compatibility
INFO: Running multiprocessing diagnostic test...
INFO: ✓ Multiprocessing diagnostic test passed
INFO: Starting parallel MCCFR training with time budget: 28800.0 seconds (0.33 days)
INFO: Using 6 worker process(es)
INFO: Batch size: 100 iterations (merge period between workers)
```

### Pendant l'Entraînement
```
DEBUG: Starting batch: 6 workers, 16 iterations each
DEBUG: Spawning worker 0 for iterations 0 to 15
DEBUG: Worker 0 started with PID 12345
...
INFO: Worker 0 starting: iterations 0 to 15
INFO: Worker 0 sampler initialized successfully
INFO: Worker 0 completed: 16 iterations, 1247 infosets
```

### En Cas de Problème
Si un worker échoue, vous verrez maintenant:
```
ERROR: Worker 2 failed with error:
<détails de l'erreur>

ERROR: Only received results from 5/6 workers (1 missing)
ERROR: Training cannot continue reliably. Please check:
  1. Worker logs above for specific errors
  2. System resources (RAM, CPU)
  3. Try reducing --num-workers or --batch-size
```

## Dépannage

### Si le Problème Persiste

#### 1. Vérifier les Ressources Système

```bash
# macOS
top

# Vérifier la mémoire disponible
vm_stat
```

#### 2. Réduire le Nombre de Workers

Si vous avez des problèmes de RAM:

```bash
python -m holdem.cli.train_blueprint \
  --config configs/blueprint_training_5h_parallel.yaml \
  --time-budget 28800 \
  --snapshot-interval 1200 \
  --buckets assets/abstraction/buckets_mid.pkl \
  --logdir /Volumes/122/Blueprintmid_8h_v3 \
  --tensorboard \
  --num-workers 4 \  # Réduire de 6 à 4
  --batch-size 100
```

#### 3. Réduire la Taille du Batch

Si les workers timeout:

```bash
python -m holdem.cli.train_blueprint \
  --config configs/blueprint_training_5h_parallel.yaml \
  --time-budget 28800 \
  --snapshot-interval 1200 \
  --buckets assets/abstraction/buckets_mid.pkl \
  --logdir /Volumes/122/Blueprintmid_8h_v3 \
  --tensorboard \
  --num-workers 6 \
  --batch-size 50  # Réduire de 100 à 50
```

#### 4. Mode Single-Process (Fallback)

Si le multiprocessing ne fonctionne pas du tout:

```bash
python -m holdem.cli.train_blueprint \
  --config configs/blueprint_training_5h_parallel.yaml \
  --time-budget 28800 \
  --snapshot-interval 1200 \
  --buckets assets/abstraction/buckets_mid.pkl \
  --logdir /Volumes/122/Blueprintmid_8h_v3 \
  --tensorboard \
  --num-workers 1  # Mode single-process
```

**Note**: Plus lent mais garanti de fonctionner.

## Surveillance de l'Entraînement

### TensorBoard

Pour suivre la progression en temps réel:

```bash
tensorboard --logdir /Volumes/122/Blueprintmid_8h_v3/tensorboard
```

Puis ouvrez http://localhost:6006 dans votre navigateur.

### Moniteur d'Activité

Vous devriez maintenant voir:
- 6 processus Python actifs (ou le nombre spécifié avec `--num-workers`)
- Utilisation CPU élevée
- Utilisation mémoire stable

## Performance Attendue

Sur Mac M2 avec 6 workers:
- **Vitesse**: ~500-800 itérations/seconde
- **Temps**: 8h de budget = ~14-23 millions d'itérations
- **Comparaison**: 5-7x plus rapide que le mode single-process

## Support

Si vous rencontrez toujours des problèmes:

1. **Vérifier les logs**: Regardez les messages d'erreur détaillés
2. **Tester le multiprocessing**: Exécutez le test de diagnostic
3. **Vérifier les ressources**: RAM, CPU, espace disque
4. **Essayer avec moins de workers**: Commencez avec 2-4 workers

## Fichiers de Documentation

- `PARALLEL_TRAINING_FIX.md` - Description technique complète du fix
- `SECURITY_SUMMARY_PARALLEL_TRAINING_FIX.md` - Analyse de sécurité
- `PARALLEL_TRAINING.md` - Guide complet du training parallèle
- `FIX_NUM_WORKERS.md` - Historique du problème original
